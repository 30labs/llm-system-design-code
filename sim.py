import random
import statistics
from dataclasses import dataclass, field

from gateway import Call, ProviderError, Reply
from handbook import DAY, FEATURES


@dataclass
class Clock:
    now: float = 0.0  # seconds since midnight


@dataclass(frozen=True)
class Speed:
    queue: float  # median wait, seconds
    prefill: float  # seconds per 1,000 tokens in
    decode: float  # median seconds per token out


LARGE = Speed(0.35, 0.12, 0.02)
SMALL = Speed(0.2, 0.05, 0.008)


@dataclass(frozen=True)
class Failure:
    start: float  # simulated seconds
    end: float
    status: int  # 429, 500, 529; 0 means slow
    share: float  # of the calls in the window


@dataclass
class SimProvider:
    name: str
    clock: Clock
    speeds: dict[str, Speed]  # by model name
    failures: list[Failure] = field(
        default_factory=list
    )
    seed: int = 7
    cache_min: int = 1_024  # shortest cached prefix
    cache_ttl: float = 300.0  # seconds
    rng: random.Random = field(init=False)
    # prefix key: when it was last used
    warm: dict[str, float] = field(
        default_factory=dict, init=False
    )

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)

    def send(self, call: Call) -> Reply:
        return simulate(self, call)


TYPICAL = {f.name: f.output for f in FEATURES}


def simulate(p: SimProvider, call: Call) -> Reply:
    now = p.clock.now
    live = [
        f for f in p.failures
        if f.start <= now < f.end
    ]
    failed = None
    if live and p.rng.random() < live[0].share:
        failed = live[0]
    if failed is not None and failed.status:
        after = p.rng.uniform(0.05, 0.3)
        status = failed.status
        wait = 2.0 if status == 429 else None
        raise ProviderError(status, after, wait)
    slow = 30.0 if failed is not None else 1.0

    ln = p.rng.lognormvariate
    long = call.prefix >= p.cache_min
    cacheable = call.cache and long
    hit = cacheable and cached(p, call)
    read = call.prefix if hit else 0
    write = 0
    if cacheable and not hit:
        write = call.prefix
    fresh = call.prefix + call.tokens - read
    typical = TYPICAL.get(
        call.feature, call.max_tokens // 2
    )
    drawn = round(typical * ln(0, 0.5))
    out = max(1, min(call.max_tokens, drawn))
    stop = "end_turn"
    if out == call.max_tokens:
        stop = "max_tokens"
    speed = p.speeds[call.model]
    queue = speed.queue * ln(0, 0.6)
    # a cached token takes a tenth of the time
    work = fresh + read / 10
    prefill = speed.prefill * work / 1000
    tpot = speed.decode * ln(0, 0.25)
    ttft = (queue + prefill + tpot) * slow
    total = ttft + (out - 1) * tpot * slow
    return Reply(
        call.model, fresh - write, read, write,
        out, stop, ttft, total,
    )


def cached(p: SimProvider, call: Call) -> bool:
    """Is the prefix warm? Marks it used."""
    key = f"{call.model}:{call.feature}"
    last = p.warm.get(key)
    p.warm[key] = p.clock.now
    if last is None:
        return False
    return p.clock.now - last < p.cache_ttl


def arrivals(
    per_day: int, seed: int
) -> list[float]:
    """Call times over a day, busy hours busier."""
    rng = random.Random(seed)
    times: list[float] = []
    for h, share in enumerate(DAY):
        rate = per_day * share / 3600
        t = h * 3600 + rng.expovariate(rate)
        while t < (h + 1) * 3600:
            times.append(t)
            t += rng.expovariate(rate)
    return times


def pct(values: list[float], p: int) -> float:
    """The p-th percentile, p from 1 to 99."""
    cuts = statistics.quantiles(
        values, n=100, method="inclusive"
    )
    return cuts[p - 1]
