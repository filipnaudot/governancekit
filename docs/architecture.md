# Architecture

For contributors to the engine. What the decisions mean is in [concepts.md](concepts.md); this page is
about how they are computed. Paths are relative to `src/governancekit/`.

## Overview

- **`engine/`**: the MP-Declare monitor, standard library only.
- **`server/`**: FastAPI app serving the engine, with agents, authentication and an audit log.
- **`frontend/`**: React admin UI for the server.

A model is built once and shared by its traces; all state that changes lives in each trace's
`TraceMonitor` and its constraint instances.

## Engine

### From .decl text to a model

1. `decl_parser.parse_decl_text` finds each constraint's template, activities and count, and checks the
   conditions against the `bind` and domain lines. It returns these too (`ParsedDecl`), for later
   payload checks.
2. `conditions` compiles the condition fields once into plain functions: `f(A)` for activation, `f(A, T)`
   for correlation and time.
3. Each constraint becomes a frozen `ConstraintDef`; its `source` (the original line) is what `blocking`
   and `violations` report.
4. `MPDeclareModel.build` adds three lookups, so only relevant constraints are asked:
   - `begin_index`: activity → constraints mentioning it that can block it.
   - `finish_index`: activity → all constraints mentioning it.
   - `ordering_constraints`: `Init`, `End`, `Chain*`, `NotChain*`. They depend on what completes first,
     next or last, so they are asked on every begin and finish.

   The groups come from `NEVER_BLOCKING_TEMPLATES` and `ORDERING_TEMPLATES` in `mp_declare_model.py`.

### Begin and finish

`TraceMonitor` (one per trace) holds the constraint instances and `running` (activity → {instance id →
event}).

- **check / begin**: ask `begin_index[activity] + ordering_constraints`. Strictest answer wins (DENIED >
  WAIT > ALLOWED); the non-allowing ones are returned as `blocking`. If allowed, begin adds the event to
  `running` under a new instance id.
- **finish**: removes the activity from `running`. Only if it completed, `on_finish` is called on
  `finish_index[activity] + ordering_constraints`.
- **violations**: every constraint whose `verdict()` isn't satisfied.

### Constraint instances

One class per template in `engine/constraints/`, implementing `ConstraintInstance` (`constraints/base.py`):

- `can_begin(event, running) -> Decision`: read-only.
- `on_finish(event, completed_at)`: record a successful completion.
- `verdict() -> Verdict`: satisfied or violated if the trace ended now.

The shared conventions (timestamps, WAIT vs DENIED, running counterparts) are in the docstrings of
`base.py`.

### Concurrency

`MonitorRegistry` is the thread-safe entry point: one lock per trace, plus a registry lock for adding and
removing models and traces (lock order: trace, then registry). Calls on one trace run one at a time, so
begin's check-and-reserve is atomic; different traces don't wait for each other. `TraceMonitor` itself is
not thread-safe.

### Adding a template

1. Add it to `Template` (`templates.py`).
2. Add a class in `constraints/` and register it in `_BUILDERS` (`constraint_factory.py`).
3. If it never blocks or depends on ordering, add it to the template sets in `mp_declare_model.py`; if
   it's unary or activates on its second activity, to `_UNARY` / `_ACTIVATION_ARG` in `decl_parser.py`.
4. Add `tests/constraints/test_<template>.py`.

## Server

`main.create_app` builds the in-memory `ServerState` (`state.py`) and one router per area: `auth`,
`agents`, `models`, `traces`, `monitors`, `audit`. All runtime calls go through `TraceMonitors`
(`monitors.py`), which checks the agent may use the trace, calls the `MonitorRegistry` and records the
request in the trace's history. When the trace ends, the history moves to the `AuditLog`.

## Design decisions

Keep these unless you mean to change the semantics:

- **begin is an atomic check-and-reserve**, then finish with the instance id. Closes the gap between
  asking and acting.
- **Only completed activities count.** Failed and aborted are the same to the engine (`completed: bool`);
  the caller records the difference.
- **The payload is final at begin**, so finish can't invalidate a decision.
- **Time windows compare the earlier activity's completion with the new one's begin**, so begin can
  decide immediately.
- **WAIT only if a running activity finishing or a time window passing could help**; otherwise DENIED.
- **Each constraint decides on its own**, given the running activities. Simple and sound per constraint,
  but contradictions between constraints aren't detected.
- **One lock per trace, and `TraceMonitor` stays single-threaded**: keeps begin atomic without slowing
  down other traces.
- **The engine uses only the standard library**, so it can be embedded anywhere.
