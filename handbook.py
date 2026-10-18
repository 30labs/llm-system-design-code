from typing import NamedTuple

ENGINEERS = 5_000


class Feature(NamedTuple):
    name: str
    calls: int  # model calls a day it runs
    days: int  # days it runs in a month
    prefix: int  # instructions and tools
    context: int  # retrieved sections, code
    history: int  # earlier turns sent again
    fresh: int  # the question or the alert
    output: int  # tokens the model writes
    seconds: float  # one call, start to end
    waits: bool  # does a person wait for it?


FEATURES = [
    Feature(
        "chat", 16_000, 21, 1_500, 1_800,
        1_400, 40, 280, 7.0, True,
    ),
    Feature(
        "editor", 40_000, 21, 1_500, 2_100,
        0, 30, 120, 3.5, True,
    ),
    Feature(
        "incident", 2_000, 21, 1_500, 1_800,
        0, 900, 300, 7.5, True,
    ),
    Feature(
        "agent", 4_800, 21, 2_500, 600,
        4_000, 100, 200, 5.5, False,
    ),
    Feature(
        "nightly", 3_000, 30, 800, 1_200,
        0, 0, 60, 2.0, False,
    ),
]


# share of a working day's calls in each hour
DAY = [
    0.002, 0.002, 0.002, 0.002, 0.002, 0.002,
    0.002, 0.020, 0.050, 0.100, 0.140, 0.120,
    0.060, 0.090, 0.120, 0.110, 0.080, 0.050,
    0.020, 0.010, 0.004, 0.004, 0.004, 0.004,
]


def input_tokens(f: Feature) -> int:
    return (
        f.prefix + f.context + f.history + f.fresh
    )


class Price(NamedTuple):
    input: float  # US$ per million tokens
    output: float
    cache_write: float  # 5-minute lifetime
    cache_read: float
    batch_input: float
    batch_output: float


# Anthropic's pricing page, read 2026-09-27
PRICES = {
    "claude-sonnet-5": Price(
        2.00, 10.00, 2.50, 0.20, 1.00, 5.00
    ),
    "claude-haiku-4-5": Price(
        1.00, 5.00, 1.25, 0.10, 0.50, 2.50
    ),
}
MODEL = "claude-sonnet-5"
# the small, fast tier, as of September 2026
SMALL_MODEL = "claude-haiku-4-5"


def usd(tokens: float, per_million: float) -> float:
    return tokens * per_million / 1_000_000
