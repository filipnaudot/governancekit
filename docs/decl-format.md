# Writing models (.decl)

A model is a text file with one statement per line. This is the support-ticket model from
[`scenarios/mp.decl`](../scenarios/mp.decl); its rules are explained in [concepts.md](concepts.md).

```
activity verify_identity
bind verify_identity: method
activity view_account
activity approve_refund
bind approve_refund: amount, approver_role, resource
activity issue_refund
bind issue_refund: amount, resource
activity close_ticket
bind close_ticket: status

method: bankid, password, sms
amount: integer between 0 and 50000
approver_role: agent, supervisor
resource: anna, erik, sara
status: resolved, unresolved

Precedence[verify_identity, view_account] | |T.method in (bankid, sms) |0,10,m
Precedence[approve_refund, issue_refund] |A.amount > 10000 |T.approver_role is supervisor and different resource |0,2,d
Response[approve_refund, issue_refund] | |same amount |0,48,h
Existence[close_ticket, 1] |A.status is resolved | |
```

## Line types

| Line | Example | Meaning |
|---|---|---|
| `activity NAME` | `activity view_account` | Declares an activity. Every activity used in a constraint must be declared. |
| `bind ACTIVITY: ATTR, ...` | `bind issue_refund: amount, resource` | The attributes the activity's payload carries. |
| `ATTR: VALUES` | `method: bankid, password, sms` | The values an attribute may take. |
| constraint | `Response[a, b] \| ... \| ... \| ...` | See below. |
| `# ...` | `# refunds` | Comment, also at the end of a line. Empty lines are ignored. |

`bind` and attribute lines are read but **not enforced** yet: payloads are not checked against them. They
document which data the conditions expect.

## Constraint lines

```
Template[A, B] | activation condition | correlation condition | time condition
```

All three `|` are required, even when the conditions are empty: `Response[a, b] | | |`.

- **Template** is one of the [templates](#templates) below. Case, spaces and hyphens are ignored:
  `ChainResponse`, `Chain Response` and `chain response` are the same.
- **Activities**: two for most templates. The templates `Existence`, `Absence`, `Exactly`, `Init` and
  `End` take one activity, and `Existence`, `Absence` and `Exactly` an optional count:
  `Existence[close_ticket, 2]` (at least twice), `Absence[a, 2]` (at most once), `Exactly[a, 3]`.
  The count defaults to 1, so `Absence[a]` means never.
- **Activation condition**: which occurrences of the activation the constraint applies to. Others are
  ignored by it. `Precedence[approve_refund, issue_refund] | A.amount > 10000 | ...` only applies to refunds
  over 10 000.
- **Correlation condition**: which target matches an activation, comparing the two activities' payloads.
- **Time condition**: how far apart activation and target may be.

### Activation and target

Most templates are rules of the form "if the **activation** happens, then something about the
**target**". In conditions, `A.` refers to the activation and `T.` to the target.

The activation is the first activity in the brackets, except for the precedence templates (`Precedence`,
`AlternatePrecedence`, `ChainPrecedence`, `NotPrecedence`, `NotChainPrecedence`), where it is the
second: in `Precedence[approve_refund, issue_refund]` the issue is the activation ("every issue needs an
approval before it") and the approval is the target.

The symmetric templates (`Choice`, `ExclusiveChoice`, `CoExistence`, `Succession`, `AlternateSuccession`,
`ChainSuccession`, `NotCoExistence`, `NotSuccession`, `NotChainSuccession`) work in both directions. There the
activation condition applies to both activities, and the correlation condition always gets the first
activity as `A` and the second as `T`.

## Conditions

Attributes are read from the activity's payload: `A.amount` is the `amount` of the activation, `T.amount`
that of the target (`B.` works as an alias for `T.`). The activation condition can only use `A.`.

| Form | Example | True if |
|---|---|---|
| `is`, `is not` | `A.status is resolved` | the attribute is (not) that text |
| `in`, `not in` | `T.method in (bankid, sms)` | the attribute is (not) one of the texts |
| `=`, `!=`, `<`, `<=`, `>`, `>=` | `A.amount > 10000`, `A.amount <= T.limit` | the comparison holds; the right side is a number, a text or another attribute |
| `same ATTR`, `different ATTR` | `same amount` | `A.amount = T.amount` / `A.amount != T.amount` |
| `and`, `or`, `not`, `( )` | `A.amount > 10000 and not A.vip is yes` | as usual; `not` binds tightest, then `and`, then `or` |
| `true`, `false` | `true` | always / never |

Values:

- **Text** can be written bare, also with spaces (`A.status is on hold`), or quoted when it contains a
  comma, bracket or keyword (`A.note is "a, b"`).
- **Numbers** are compared as numbers with `=`, `<`, etc. `is` and `in` always compare text, so
  `A.count is 1` is false for a payload `{"count": 1}`; write `A.count = 1`.
- **Missing attributes**: a comparison on an attribute the payload doesn't have is false (so `not` of it
  is true).

## Time windows

```
min,max,unit
```

with unit `s` (seconds), `m` (minutes), `h` (hours) or `d` (days). It holds if the target is between `min`
and `max` apart from the activation, in either direction: `0,48,h` is at most 48 hours, `1,2,h` between
one and two hours. The time between two activities is measured from the earlier one's completion to the
later one's begin (see [concepts.md](concepts.md#time)).

## Templates

The 26 templates GovernanceKit supports. *Matching* means satisfying the conditions; "occurs" means completes.

**Existence templates** (one activity)

| Template | Satisfied if |
|---|---|
| `Existence[a, n]` | `a` occurs at least n times (default 1) |
| `Absence[a, n]` | `a` occurs at most n − 1 times (`Absence[a]`: never) |
| `Exactly[a, n]` | `a` occurs exactly n times (default 1) |
| `Init[a]` | the first activity to complete is `a` |
| `End[a]` | the last activity to complete is `a` |

**Choice templates** (symmetric)

| Template | Satisfied if |
|---|---|
| `Choice[a, b]` | at least one of `a` and `b` occurs |
| `ExclusiveChoice[a, b]` | one of `a` and `b` occurs, but not both |

**Relation templates**

| Template | Satisfied if |
|---|---|
| `RespondedExistence[a, b]` | every `a` has a matching `b` somewhere in the trace, before or after it |
| `CoExistence[a, b]` | every `a` has a matching `b` and every `b` a matching `a`, anywhere in the trace |
| `Response[a, b]` | every `a` is followed by a matching `b` |
| `AlternateResponse[a, b]` | every `a` is followed by a matching `b` before the next `a` |
| `ChainResponse[a, b]` | every `a` is immediately followed by a matching `b` |
| `Precedence[a, b]` | every `b` is preceded by a matching `a` |
| `AlternatePrecedence[a, b]` | every `b` is preceded by a matching `a` that came after the previous `b` |
| `ChainPrecedence[a, b]` | every `b` is immediately preceded by a matching `a` |
| `Succession[a, b]` | `Response[a, b]` and `Precedence[a, b]` |
| `AlternateSuccession[a, b]` | `AlternateResponse[a, b]` and `AlternatePrecedence[a, b]`: `a` and `b` alternate |
| `ChainSuccession[a, b]` | `ChainResponse[a, b]` and `ChainPrecedence[a, b]` |

**Negative templates**

| Template | Satisfied if |
|---|---|
| `NotRespondedExistence[a, b]` | no `a` has a matching `b` anywhere in the trace |
| `NotCoExistence[a, b]` | `a` and a matching `b` don't both occur |
| `NotResponse[a, b]` | no `a` is followed by a matching `b` |
| `NotChainResponse[a, b]` | no `a` is immediately followed by a matching `b` |
| `NotPrecedence[a, b]` | no `b` is preceded by a matching `a` |
| `NotChainPrecedence[a, b]` | no `b` is immediately preceded by a matching `a` |
| `NotSuccession[a, b]` | no `a` is followed by a matching `b` |
| `NotChainSuccession[a, b]` | no `a` is immediately followed by a matching `b` |

"Immediately" means nothing else completes in between. Because of that, the chain templates restrict which
activities may run at the same time.

## Limits

- `bind` and attribute lines are not enforced (see [Line types](#line-types)).
- Each constraint is judged on its own, so contradictions between constraints are not detected. With
  `Response[a, b]` and `Absence[b]`, `a` is allowed although it can never be satisfied.
- Some mistakes give unclear errors: a constraint line without all three `|`, or an unknown template name.
  A `#` inside a quoted value starts a comment.
