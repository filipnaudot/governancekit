# Writing models (.decl)

One statement per line. Full example: [`scenarios/mp.decl`](../scenarios/mp.decl).

```
activity approve_refund
activity issue_refund
bind issue_refund: amount, resource       # attributes of the payload (not enforced)
amount: integer between 0 and 50000       # allowed values (not enforced)

Precedence[approve_refund, issue_refund] | A.amount > 10000 | different resource | 0,2,d
```

- `activity NAME`: every activity used in a constraint must be declared.
- `bind` and value lines document the payload; they are parsed but not checked.
- `#` starts a comment.

## Constraint lines

```
Template[activities] | activation condition | correlation condition | time window
```

The example above reads: every `issue_refund` with `amount > 10000` must be preceded by an
`approve_refund` from a different `resource`, at most 2 days earlier.

- **Template**: see [Templates](#templates). Case, spaces and hyphens are ignored.
- **Activities**: two, or one plus an optional count for `Existence`, `Absence`, `Exactly`, `Init`, `End`.
  The count defaults to 1; `Absence[a, n]` means at most n − 1 times.
- **Activation condition**: which occurrences of the activation the constraint applies to.
- **Correlation condition**: which target counts for an activation.
- **Time window**: how far apart activation and target may be.

Leave unused fields empty, but keep all three `|`: `Response[a, b] | | |`.

**Activation and target.** In conditions, `A.` is the activation and `T.` the target. The activation is
the first activity, except in the `*Precedence` templates, where it is the second (`Precedence[a, b]`: every
`b` needs an `a` before it). In symmetric templates (`Choice`, `ExclusiveChoice`, `*CoExistence`,
`*Succession`) the activation condition applies to both activities, and `A.` is the first, `T.` the second.

## Conditions

`A.x` / `T.x` is attribute `x` of the activation / target payload. Activation conditions can only use `A.`.

| Condition | Example |
|---|---|
| equals text | `A.status is resolved`, `A.status is not resolved` |
| one of | `T.method in (bankid, sms)`, `T.method not in (password)` |
| compare | `A.amount > 10000`, `A.amount <= T.limit` (`=`, `!=`, `<`, `<=`, `>`, `>=`) |
| same / different attribute | `same amount` (= `A.amount = T.amount`), `different resource` |
| combine | `and`, `or`, `not`, `( )` |

- `is` and `in` compare text; use `=`, `<`, ... for numbers (`A.count is 1` is false for the number 1).
- Quote text containing commas, brackets or keywords: `A.note is "a, b"`.
- A condition on a missing attribute is false.

## Time windows

`min,max,unit`, unit `s`, `m`, `h` or `d`. `0,48,h` = at most 48 hours apart; `1,2,h` = between 1 and 2
hours. Measured from the earlier activity's completion to the later one's begin.

## Templates

The 26 templates GovernanceKit supports. "Occurs" means completes; "matching" means satisfying the
conditions.

**One activity**

| Template | Satisfied if |
|---|---|
| `Existence[a, n]` | `a` occurs at least n times |
| `Absence[a, n]` | `a` occurs at most n − 1 times |
| `Exactly[a, n]` | `a` occurs exactly n times |
| `Init[a]` | the first activity to complete is `a` |
| `End[a]` | the last activity to complete is `a` |

**Choice**

| Template | Satisfied if |
|---|---|
| `Choice[a, b]` | `a` or `b` occurs |
| `ExclusiveChoice[a, b]` | `a` or `b` occurs, not both |

**Relation**

| Template | Satisfied if |
|---|---|
| `RespondedExistence[a, b]` | every `a` has a matching `b` somewhere in the trace |
| `CoExistence[a, b]` | every `a` has a matching `b` and vice versa |
| `Response[a, b]` | every `a` is followed by a matching `b` |
| `AlternateResponse[a, b]` | every `a` is followed by a matching `b` before the next `a` |
| `ChainResponse[a, b]` | every `a` is directly followed by a matching `b` |
| `Precedence[a, b]` | every `b` is preceded by a matching `a` |
| `AlternatePrecedence[a, b]` | every `b` is preceded by a matching `a` since the previous `b` |
| `ChainPrecedence[a, b]` | every `b` is directly preceded by a matching `a` |
| `Succession[a, b]` | `Response` and `Precedence` |
| `AlternateSuccession[a, b]` | `AlternateResponse` and `AlternatePrecedence` |
| `ChainSuccession[a, b]` | `ChainResponse` and `ChainPrecedence` |

**Negative**

| Template | Satisfied if |
|---|---|
| `NotRespondedExistence[a, b]` | no `a` has a matching `b` in the trace |
| `NotCoExistence[a, b]` | `a` and a matching `b` don't both occur |
| `NotResponse[a, b]` | no `a` is followed by a matching `b` |
| `NotChainResponse[a, b]` | no `a` is directly followed by a matching `b` |
| `NotPrecedence[a, b]` | no `b` is preceded by a matching `a` |
| `NotChainPrecedence[a, b]` | no `b` is directly preceded by a matching `a` |
| `NotSuccession[a, b]` | no `a` is followed by a matching `b` |
| `NotChainSuccession[a, b]` | no `a` is directly followed by a matching `b` |

"Directly" means nothing else completes in between.

## Limits

- Contradictions between constraints are not detected (`Response[a, b]` + `Absence[b]` still allows `a`).
- A line missing a `|` or with an unknown template gives an unclear error.
- `#` inside quoted text starts a comment.
