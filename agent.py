import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

from handbook import MODEL, PRICES, usd

SENT, GROWS, WRITES = 3_200, 1_000, 200
THINK = 5.5  # seconds per model call
APPROVE = {"file_ticket"}


@dataclass(frozen=True)
class Budget:
    steps: int = 25
    usd: float = 0.50
    seconds: float = 180.0


DEFAULT = Budget()


@dataclass
class Action:
    tool: str
    arg: str = ""


@dataclass
class Run:
    id: str
    steps: list[dict[str, str]] = field(
        default_factory=list
    )
    spent: float = 0.0
    seconds: float = 0.0
    state: str = "running"
    pending: dict[str, str] | None = None


Model = Callable[[Run], Action]
Tool = Callable[[str, str], str]
Tools = dict[str, tuple[Tool, float]]
Store = dict[str, str]


def cost(k: int) -> float:
    p = PRICES[MODEL]
    sent = SENT + GROWS * k
    read = usd(sent, p.input)
    return read + usd(WRITES, p.output)


def over(run: Run, b: Budget) -> str | None:
    k = len(run.steps)
    if k >= b.steps:
        return "steps"
    if run.spent + cost(k) > b.usd:
        return "money"
    if run.seconds >= b.seconds:
        return "time"
    return None


def act(
    run: Run, action: Action, tools: Tools
) -> None:
    tool, seconds = tools[action.tool]
    key = f"{run.id}:{len(run.steps)}"
    result = tool(action.arg, key)
    run.seconds += seconds
    done = asdict(action) | {"got": result}
    run.steps.append(done)


def step(
    run: Run, model: Model, tools: Tools, b: Budget
) -> None:
    if broken := over(run, b):
        run.state = f"stopped: {broken}"
        return
    action = model(run)
    run.spent += cost(len(run.steps))
    run.seconds += THINK
    if action.tool == "done":
        run.state = "done"
    elif action.tool in APPROVE:
        run.state = "waiting"
        run.pending = asdict(action)
    else:
        act(run, action, tools)


def advance(
    run: Run, model: Model, tools: Tools,
    store: Store, b: Budget = DEFAULT,
) -> None:
    while run.state == "running":
        step(run, model, tools, b)
        save(run, store)


def save(run: Run, store: Store) -> None:
    store[run.id] = json.dumps(asdict(run))


def load(run_id: str, store: Store) -> Run:
    return Run(**json.loads(store[run_id]))


def approve(
    run: Run, tools: Tools, store: Store
) -> None:
    run.state = "acting"  # the intent, saved first
    save(run, store)
    finish(run, tools, store)


def finish(
    run: Run, tools: Tools, store: Store
) -> None:
    assert run.pending is not None
    act(run, Action(**run.pending), tools)
    run.state, run.pending = "running", None
    save(run, store)
