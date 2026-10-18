# LLM System Design: code

The shared Python modules that the examples in *LLM System Design* (30labs) import. The book prints
`handbook.py`, `gateway.py`, `reliability.py` and `agent.py` in its chapters; `sim.py`, the simulated
provider chapter 3 describes, is only here.

Put these files beside an example's code and run it with Python 3.12 or later. They use the
standard library only.

- `handbook.py`: the running example's features, traffic and prices (chapter 1)
- `gateway.py`: the gateway every model call goes through (chapter 2)
- `sim.py`: the simulated provider, with a seeded clock and log-normal latencies (chapter 3)
- `reliability.py`: retries and the circuit breaker (chapter 6)
- `agent.py`: the ticket agent (chapter 9)
