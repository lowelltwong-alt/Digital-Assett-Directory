# Acceptance Matrix

| Gate | Owner | Checker | Required evidence | Pass condition | Revalidate when |
|---|---|---|---|---|---|
| Launch | campaign owner | independent launch reviewer | signed H-001–H-010 receipt; exact manifest digest | all decisions resolved and static validators pass | any source, scope, authority, adapter, or manifest change |
| P1 baseline | bounded writer | independent checker | regenerated counts, source pointers, missingness, hashes, and hashed operational-eligibility artifact | reproducible; cutoff/source revisions/stable population/rules/reason codes/equation are frozen; unknown is explicit; no value claim | observation source, eligibility mapping, reason-code map, or baseline code changes |
| P1 freeze | campaign owner | independent checker | approved expiry and exception rule | one active build + one bounded pilot; no silent exception | expiry, scope, or owner changes |
| P2 local CI | bounded writer | independent checker | pytest, validate, roadmap outputs | all required commands pass | code, workflow, validator, runtime changes |
| P2 GitHub enforcement | human operator | independent checker | settings/API snapshot, deliberate-failure run, and two immediate pass URLs | required check blocks failure; admin posture matches H-004; two immediate runs pass | protection or workflow changes |
| P2 stability | CI stability observer | independent checker | four naturally scheduled weekly run URLs | all four consecutive runs green on accepted heads; no manual substitution | any accepted-head, workflow, protection, or required-context change |
| P3 new outcomes | bounded writer | independent checker | positive/negative/idempotency tests | 100% membership validation; zero prose sentinels | schema or producer changes |
| P3 legacy data | bounded writer | independent checker | classification report and reconciliation totals | every row joinable, invalid, or unknown; raw retained | migration logic or source ledger changes |
| P3 yield | bounded writer | independent checker | golden fixtures and report | written/reused/promoted match actual event semantics | event enum or report changes |
| P4 worktrees | human lifecycle owner | independent checker | global registry audit | 100% owner/disposition/review or recovery hold | worktree set or registry changes |
| P4 sessions/queues | bounded writer | independent checker | closure, age, exact J-100 operational-baseline digest, and item-level denominator reconciliation | thresholds use frozen Phase 01 eligibility/reason codes and reconciliation equation; no inferred closure | event/session inputs or accepted operational-baseline digest changes |
| P4 daemon truth | bounded writer | independent checker | heartbeat, task status, journal reconciliation | contradictions fail or show unavailable | daemon/journal/task state changes |
| P5A shadow | pilot producer | independent checker | 10 complete envelopes | metrics/joins usable; no success claim | pilot protocol or case set changes |
| P5B comparison | pilot producer | independent checker | 20 atomic child receipts, frozen allocation and analysis population | selected H-005 primary threshold and every guardrail pass; secondary metrics cannot substitute | cohort, binding, metric, runtime, evaluator, or denominator changes |
| P5C value | pilot producer | independent checker + human sample | 40 atomic child receipts, three repos, frozen allocation | selected H-005 primary threshold and every guardrail pass; secondary metrics cannot substitute | cohort, binding, metric, runtime, evaluator, or denominator changes |
| P6 decision | campaign owner | independent checker | decision memo + counterevidence + signed receipt | one allowed decision with follow-on boundary | evidence correction or decision revision |
