# Data Flow

## Scan flow

```text
source configuration
-> local/GitHub adapter
-> file/repo metadata + bounded content excerpt
-> redaction and exclusion checks
-> stable ID + revision ID
-> raw scan JSONL
-> catalog upsert
-> candidate graph edges
-> value and freshness update
-> radars
-> reports and alerts
-> source hash verification
```

## AI build-learning flow

```text
agent preflight
-> task context pack
-> bounded work
-> validation
-> postflight handoff
-> lesson record
-> repeated-pattern detection
-> candidate skill/agent recommendation
-> human review
```

## New-idea activation flow

```text
new idea or asset
-> query terms / tags / capabilities / outcomes
-> retrieve active and dormant assets
-> identify needs newly covered
-> score pair and bundle synergies
-> alert with evidence, assumptions, missing parts, and next experiment
```

## External missing-part flow

```text
unsatisfied need
-> explicit research command
-> GitHub repository search
-> metadata-only candidate list
-> license/freshness/security review
-> local prototype or rejection
-> lesson and evaluation evidence
-> governed reuse decision
```
