# GovernanceKit

Runtime governance for AI agents. Before an agent performs an action, GovernanceKit checks it against a
process model and answers whether it may go ahead. The model is written in **MP-Declare**: constraints
such as "an account may only be viewed after the customer's identity was verified by BankID or SMS in the
last 10 minutes", or "a refund over 10 000 needs a supervisor's approval, by someone other than the one
issuing it". The agent is stopped *before* it breaks a rule, not told afterwards.

Use it as a Python library inside your own agent code, or run it as a service (HTTP API + web frontend)
that your agents call.

## How it works

Each run of an agent (a support ticket, a conversation, ...) is a **trace**, monitored against one model.
For every activity the agent wants to perform:

1. **check** (optional): the agent asks whether the activity may begin, without changing anything.
2. **begin**: the agent says the activity is about to start. The answer is a decision:
   - `ALLOWED`: go ahead. The activity is now running and gets an instance id.
   - `WAIT`: not now, but it may become allowed later (e.g. once another running activity finishes).
   - `DENIED`: it would permanently violate the model. Don't perform it.
3. **finish**: when an allowed activity is done, the agent reports whether it completed. Only completed
   activities count towards the constraints.

Several activities may run at the same time on one trace. When the trace ends, GovernanceKit reports
which constraints were violated, if any (e.g. a required activity that never happened).
GovernanceKit only decides; the agent does the waiting and retrying.

## Example model

```
activity verify_identity
activity view_account
Precedence[verify_identity, view_account] | | T.method in (bankid, sms) | 0,10,m
```

`view_account` may only begin if `verify_identity` completed before it, with a `method` of `bankid` or
`sms`, at most 10 minutes earlier. The full support-ticket model is in
[`scenarios/mp.decl`](scenarios/mp.decl); the syntax is described in [docs/decl-format.md](docs/decl-format.md).

## Getting started

Requires Python 3.11 or newer. Clone the repository and create a virtual environment:

```sh
git clone git@github.com:filipnaudot/governancekit.git
cd governancekit
python3 -m venv .venv
source .venv/bin/activate
```

### Use as a library

The engine (`governancekit.engine`) has no dependencies outside the standard library.

```sh
pip install -e .
```

```python
from governancekit.engine import Event, MonitorRegistry

MODEL = """
activity verify_identity
activity view_account
Precedence[verify_identity, view_account] | | T.method in (bankid, sms) | 0,10,m
"""

registry = MonitorRegistry()
registry.add_model("support", MODEL)
registry.start_monitor("support", "ticket-42")

# Nobody has verified the customer's identity yet
decision, _, blocking = registry.begin_event("ticket-42", Event.now("view_account"))
print(decision, blocking)  # Decision.DENIED ['Precedence[verify_identity, view_account] | ...']

# Verify the identity: allowed, so perform it and report that it completed
decision, iid, _ = registry.begin_event(
    "ticket-42", Event.now("verify_identity", {"method": "bankid"})
)
print(decision)  # Decision.ALLOWED
registry.finish_event("ticket-42", iid, completed=True)

# Now viewing the account is allowed
decision, iid, _ = registry.begin_event("ticket-42", Event.now("view_account"))
print(decision)  # Decision.ALLOWED
registry.finish_event("ticket-42", iid, completed=True)

print(registry.violations("ticket-42"))  # [] - nothing violated
registry.end_monitor("ticket-42")
```

`MonitorRegistry` is thread-safe and can monitor many traces at once. See its docstrings in
[`src/governancekit/engine/monitor_registry.py`](src/governancekit/engine/monitor_registry.py).

### Run as a service

The service runs the engine behind an HTTP API with authentication and an audit log, plus a web frontend
to manage models, agents and traces. It needs [Docker](https://docs.docker.com/get-docker/):

```sh
cp .env.example .env   # set GK_ADMIN_SECRET and GK_JWT_SECRET
docker compose up --build
```

- API and its interactive docs: http://localhost:8000/docs
- Frontend: http://localhost:3000 (log in as `admin` with `GK_ADMIN_SECRET`)

If the secrets are left empty, the API generates them at startup and prints the admin secret in its logs
(`docker compose logs api`). State is kept in memory and lost when the API restarts.

To see it in action, run one of the scenarios while the service is up, and follow it in the frontend's
Monitors tab:

```sh
./scenarios/demo.sh          # one agent works through a refund ticket
./scenarios/multi_agent.sh   # several agents on one ticket
./scenarios/multi_trace.sh   # several tickets at the same time
```

The API is described in [docs/api.md](docs/api.md).

## Development

```sh
pip install -e ".[dev]"
pytest                    # all tests except benchmarks
pytest -m benchmark       # benchmarks
```

To run the API and the frontend from the working tree with hot reload (frontend on
http://localhost:5173):

```sh
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

## Repository layout

```
src/governancekit/
  engine/        the MP-Declare monitor (standard library only)
    constraints/ one class per Declare template
  server/        FastAPI app: auth, agents, models, traces, monitors, audit log
frontend/        React + Vite web frontend
scenarios/       example models and shell scripts that act as agents against the API
tests/           pytest tests; tests/constraints/ has one file per template
```

## Documentation

- [docs/concepts.md](docs/concepts.md): traces, activities, decisions and how time is handled
- [docs/decl-format.md](docs/decl-format.md): writing models, conditions and the supported templates
- [docs/api.md](docs/api.md): what the HTTP API offers and its main endpoints
- [docs/architecture.md](docs/architecture.md): how the engine and server are put together

## License

Apache License 2.0, see [LICENSE](LICENSE).
