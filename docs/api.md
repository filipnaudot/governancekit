# HTTP API

The service runs the engine behind an HTTP API, by default on http://localhost:8000 (see the
[README](../README.md#run-as-a-service) to start it). The interactive docs at http://localhost:8000/docs list
every endpoint with its request and response fields.

The API is at an early stage and will change. State is kept in memory and lost when the server restarts.

## What it offers

- **Management**, for an admin: register agents, add models, and follow the running traces and the audit
  log.
- **Runtime**, for agents: start a trace on a model, check, begin and finish activities on it, and end
  it to get the verdict. Several agents can work on one trace, and several activities can run at once.
- **Audit log**: every accepted request on a trace is recorded (who, when, which activity, which decision), also
  after the trace has ended.

## Main endpoints

| Endpoint | Does |
|---|---|
| `POST /models` | Add a model, as `.decl` text (see [decl-format.md](decl-format.md)); with `validate_payloads`, events that don't fit it get 422 |
| `POST /traces` | Start a trace on a model |
| `POST /traces/{trace_id}/check` | Decision for an activity, without reserving it |
| `POST /traces/{trace_id}/activities` | Begin an activity: the decision, and an instance ID if allowed |
| `POST /traces/{trace_id}/activities/{instance_id}/finish` | Finish an activity as `completed`, `failed` or `aborted` |
| `POST /traces/{trace_id}/end` | End the trace; returns whether it is conformant and its violations |
| `GET /monitors` | The running traces, with their running activities and current violations |
| `GET /audit` | The audit log |

The decisions and when each is given are explained in [concepts.md](concepts.md).

[`scenarios/agent.sh`](../scenarios/agent.sh) wraps the API in shell functions, and the scenario scripts
next to it use them to play out whole support tickets.
