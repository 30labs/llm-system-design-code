from dataclasses import dataclass, field
from typing import Protocol

from handbook import PRICES, usd


@dataclass(frozen=True)
class Call:
    feature: str  # chat, editor, incident ...
    user: str
    model: str
    prefix: int  # tokens the same on every call
    tokens: int  # every other input token
    max_tokens: int
    cache: bool = False  # mark the prefix cached


@dataclass(frozen=True)
class Reply:
    model: str
    input: int  # input billed at the full price
    cache_read: int  # input read from the cache
    cache_write: int  # input written to it
    output: int
    stop: str  # "end_turn" or "max_tokens"
    ttft: float  # seconds to the first token
    seconds: float  # seconds to the last token


class ProviderError(Exception):
    def __init__(
        self,
        status: int,
        after: float = 0.0,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(f"HTTP {status}")
        self.status = status
        self.after = after  # seconds until it came
        self.retry_after = retry_after


class Provider(Protocol):
    name: str

    def send(self, call: Call) -> Reply: ...


def cost(reply: Reply) -> float:
    p = PRICES[reply.model]
    return (
        usd(reply.input, p.input)
        + usd(reply.cache_read, p.cache_read)
        + usd(reply.cache_write, p.cache_write)
        + usd(reply.output, p.output)
    )


@dataclass(frozen=True)
class Entry:
    feature: str
    user: str
    provider: str
    reply: Reply
    usd: float


class OverBudget(Exception):
    pass


@dataclass
class Gateway:
    providers: dict[str, Provider]  # by model
    # US$ a day each feature may spend
    limits: dict[str, float] = field(
        default_factory=dict
    )
    log: list[Entry] = field(default_factory=list)
    spent: dict[str, float] = field(
        default_factory=dict
    )

    def send(self, call: Call) -> Reply:
        return through(self, call)


def through(g: Gateway, call: Call) -> Reply:
    spent = g.spent.get(call.feature, 0.0)
    limit = g.limits.get(call.feature)
    if limit is not None and spent >= limit:
        raise OverBudget(call.feature)
    provider = g.providers[call.model]
    reply = provider.send(call)
    price = cost(reply)
    g.spent[call.feature] = spent + price
    entry = Entry(
        call.feature, call.user,
        provider.name, reply, price,
    )
    g.log.append(entry)
    return reply
