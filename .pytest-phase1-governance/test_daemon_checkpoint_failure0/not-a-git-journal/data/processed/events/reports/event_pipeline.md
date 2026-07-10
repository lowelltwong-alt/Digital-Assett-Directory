# DAD Event Pipeline Report

Generated: 2026-07-10T17:12:02.163109+00:00

- Events: 0
- Response states: 0
- Actionable notices without response state: 0
- Event log: `processed/events/event_log.jsonl`
- Response state: `processed/events/response_state.jsonl`
- Quarantine: `processed/events/quarantine`

## Boundary

DAD pipeline events are append-only candidate metadata. They do not override source repo authority, satisfy human gates, approve public release, or authorize writes outside repo-local event/mail adapters.
