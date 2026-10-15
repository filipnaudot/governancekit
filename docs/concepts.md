# Concepts

This page explains how GovernanceKit decides whether an agent may perform an activity. The examples use
the support-ticket model in [`scenarios/mp.decl`](../scenarios/mp.decl):

```
Precedence[verify_identity, view_account] | | T.method in (bankid, sms) | 0,10,m
Precedence[approve_refund, issue_refund] | A.amount > 10000 | T.approver_role is supervisor and different resource | 0,2,d
Response[approve_refund, issue_refund] | | same amount | 0,48,h
Existence[close_ticket, 1] | A.status is resolved | |
```

1. An account may only be viewed after the identity was verified by BankID or SMS, at most 10 minutes ago.
2. A refund over 10 000 needs an approval by a supervisor other than the one issuing it, at most 2 days ago.
3. Every approved refund must be issued with the same amount within 48 hours.
4. The ticket must be closed as resolved.

## Background: Declare and MP-Declare

Most process models are flowcharts: they list every allowed path. **Declare** works the other way round:
a model is a set of constraints, and everything that doesn't break one is allowed. That suits agents,
whose steps are not known in advance. Each constraint is an instance of a *template* such as
`Precedence[A, B]` ("B only after A") or `Response[A, B]` ("every A is eventually followed by B").

**MP-Declare** (multi-perspective Declare) adds data and time to the templates: conditions on the
activities' attributes (`A.amount > 10000`, `same amount`) and time windows (`0,48,h`). The syntax is
described in [decl-format.md](decl-format.md).

Further reading: C. Di Ciccio, M. Montali: [*Declarative Process Specifications: Reasoning, Discovery,
Monitoring*](https://doi.org/10.1007/978-3-031-08848-3_4), in *Process Mining Handbook*, LNBIP 448,
Springer, 2022, pp. 108–152 (open access). An introduction to Declare, including monitoring running
processes for violations and the multi-perspective extensions.

## Models, traces and activities

- A **model** is a set of constraints, written in a `.decl` file.
- A **trace** is one run of the process: one support ticket, one conversation. Each trace is monitored
  against one model, and one model can be used by many traces at the same time.
- An **activity** is something an agent does in a trace, such as `view_account`. It has a name, a time
  and a **payload** of attributes (`{"amount": 20000, "resource": "erik"}`) that the conditions can use.

## Check, begin and finish

An agent uses three operations on a trace:

- **check**: may this activity begin now? Returns a decision, but changes nothing. Useful to ask before
  preparing an activity; the answer can be outdated by the time the agent acts.
- **begin**: the activity is about to start. Returns the same decision as check, and if it is allowed the
  activity is now **running** and gets an instance id.
- **finish**: the running activity is done. The agent reports whether it **completed**, or failed or was
  aborted.

The payload is final at begin: the activity is judged on the attributes it begins with.

## Decisions: ALLOWED, WAIT and DENIED

check and begin answer with one of three decisions:

- **ALLOWED**: the activity may begin. Whatever the running activities do (complete, fail, in any
  order), this one completing can't permanently break the model.
- **WAIT**: not now, but it may become allowed without the agent doing anything else, because:
  - a running activity may still finish in a way that allows it. If a supervisor's
    `approve_refund` is running, an `issue_refund` over 10 000 by someone else gets WAIT: if the approval
    completes, the refund is allowed.
  - a time window hasn't opened yet. With a window of `1,2,h`, an activity 30 minutes after its
    predecessor gets WAIT; after 1 hour it is allowed.
- **DENIED**: performing it now would permanently violate the model. With no approval completed or
  running, `issue_refund` over 10 000 is DENIED. Something else would have to happen first (an approval),
  which is up to the agent.

Along with the decision comes the list of constraints that didn't allow it (`blocking`), so the agent
can tell why.

A model's constraints are asked separately and the strictest answer wins: one DENIED makes the activity
DENIED, otherwise one WAIT makes it WAIT.

## Several activities at once

Several activities may run at the same time on one trace, for example when several agents work on one
ticket. A decision takes the running activities into account: as long as the supervisor's approval is
running, a refund that depends on it gets WAIT, while a refund issued by the supervisors themselves is
DENIED, since the four-eyes rule can't be met however the approval ends.

## Only completed activities count

Only an activity that **completed** counts towards the constraints. If the approval fails or is aborted
it is simply forgotten, and the refund that waited on it becomes DENIED.

**Order** means completion order: an activity "happened before" another if it completed before the other
began.

## Time

Time conditions compare the **completion** time of the earlier activity with the **begin** time of the
later one. For constraint 1, `view_account` must begin at most 10 minutes after `verify_identity`
completed.

When a window has passed, the obligation can no longer be met. If no refund was issued within 48 hours of
the approval, constraint 3 is violated, and a late `issue_refund` is DENIED, since constraint 2's 2-day
window has passed too.

## Ending a trace: violations

Some constraints can only be judged at the end: `Existence[close_ticket]` is not violated by any single
activity, only by a trace that ends without one. At any time, the trace's **violations** are the
constraints that would be violated if it ended now. During the ticket this includes obligations not met
*yet*, such as the close; when the trace ends it is the final verdict, and a trace without violations is
**conformant**.

A trace can't end while activities are still running, unless they are explicitly aborted. Running
activities never count towards violations.

## What the engine leaves to the caller

The engine (`governancekit.engine`) only decides. It doesn't wait, queue or retry: on WAIT the agent
decides when to ask again. It has no timeouts: an activity that never finishes keeps running until the
caller finishes or aborts it. And each constraint keeps only the state it needs to decide, not a full
record of the trace.

The service (`governancekit.server`) adds what an agent platform needs around that: authentication, which
agents may work on which trace, and an **audit log** with the full history of every trace: who checked,
began and finished which activity, when, and with which decision.
