import random
from collections import deque
from dataclasses import dataclass

from gateway import (
    Call,
    Provider,
    ProviderError,
    Reply,
)
from sim import Clock

RETRYABLE = {
    408, 409, 429, 500, 502, 503, 504, 529
}


def backoff(rng: random.Random, n: int) -> float:
    return rng.uniform(0, min(8.0, 0.5 * 2**n))


@dataclass
class Retry:
    inner: Provider
    clock: Clock
    tries: int = 3
    budget: float = 10.0
    deadline: float = 600.0
    timeout: float = 600.0
    seed: int = 5

    def __post_init__(self) -> None:
        self.name = self.inner.name
        self.rng = random.Random(self.seed)
        self.requests = self.retries = 0

    def send(self, call: Call) -> Reply:
        self.requests += 1
        start, n = self.clock.now, 0
        while True:
            try:
                return attempt(self, call, start)
            except ProviderError as e:
                n += 1
                wait = pause(self, e, n, start)
            self.clock.now += wait


def pause(
    r: Retry, e: ProviderError, n: int, start: float
) -> float:
    if e.status not in RETRYABLE or n >= r.tries:
        raise e
    if r.retries >= r.budget * r.requests:
        raise e
    wait = e.retry_after
    if wait is None:
        wait = backoff(r.rng, n - 1)
    if r.clock.now + wait - start >= r.deadline:
        raise e
    r.retries += 1
    return wait


def attempt(
    r: Retry, call: Call, start: float
) -> Reply:
    left = r.deadline - (r.clock.now - start)
    limit = min(r.timeout, left)
    try:
        reply = r.inner.send(call)
    except ProviderError as e:
        r.clock.now += e.after
        e.after = 0.0
        raise
    if reply.ttft > limit:
        r.clock.now += limit
        raise ProviderError(408)
    return reply


@dataclass
class Breaker:
    inner: Provider
    clock: Clock
    calls: int = 20
    rate: float = 0.8
    cooldown: float = 30.0

    def __post_init__(self) -> None:
        self.name = self.inner.name
        self.recent = deque[bool](
            maxlen=self.calls
        )
        self.opened: float | None = None

    def send(self, call: Call) -> Reply:
        now, opened = self.clock.now, self.opened
        if opened is not None:
            if now - opened < self.cooldown:
                raise Open(self.name)
            self.opened = now  # half open: a probe
        try:
            reply = self.inner.send(call)
        except ProviderError:
            judge(self, True)
            raise
        judge(self, False)
        return reply


class Open(Exception):
    pass


def judge(b: Breaker, failed: bool) -> None:
    b.recent.append(failed)
    share = sum(b.recent) / b.calls
    if not failed and b.opened is not None:
        b.opened = None  # the probe worked: close
        b.recent.clear()
    elif failed and share >= b.rate:
        b.opened = b.clock.now
