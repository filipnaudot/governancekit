# Concepts

## Declare and MP-Declare

A **Declare** model is a set of constraints; anything that breaks none of them is allowed. Each constraint
instantiates a template, e.g. `Precedence[A, B]` (B only after A). **MP-Declare** adds conditions on
activity data and time windows. Syntax: [decl-format.md](decl-format.md).

Further reading: C. Di Ciccio, M. Montali: [*Declarative Process Specifications: Reasoning, Discovery,
Monitoring*](https://doi.org/10.1007/978-3-031-08848-3_4), in *Process Mining Handbook*, LNBIP 448,
Springer, 2022, pp. 108–152.

## Models, traces and activities

- **Model**: a set of constraints, written in a `.decl` file.
- **Trace**: one run of the process (e.g. one support ticket), monitored against one model.
- **Activity**: something an agent does in a trace. It has a name, a timestamp and a payload of attributes
  used by the conditions.

## Operations

- **check**: returns the decision for an activity; changes nothing.
- **begin**: returns the same decision; if allowed, the activity is running and gets an instance id.
- **finish**: ends a running activity as completed, failed or aborted.

The payload is final at begin.

## Decisions

- **ALLOWED**: the activity may begin. However the running activities end, it completing can't
  permanently violate the model.
- **WAIT**: not now, but a running activity finishing or a time window opening could make it allowed.
- **DENIED**: it would permanently violate the model unless other activities happen first.

Each constraint answers separately; the strictest answer wins (DENIED > WAIT > ALLOWED). The constraints
that didn't allow it are returned as `blocking`.

## Rules

- Several activities may run at once on one trace; decisions take them into account.
- Only completed activities count. Failed and aborted ones are ignored.
- Order is completion order.
- Time conditions compare the earlier activity's completion time with the later one's begin time.
- An obligation whose time window has passed no longer blocks other activities; it is reported as a
  violation.

## Violations

**Violations** are the constraints that would be violated if the trace ended now. Mid-trace this includes
obligations not met yet; at the end it is the final verdict. A trace without violations is
**conformant**. A trace can't end while activities run, unless they are aborted. Running activities don't
count.

## Engine and service

The engine only decides: it doesn't wait, retry or time out activities, and keeps no history. The service
adds authentication, agent access per trace, and an audit log of every request.
