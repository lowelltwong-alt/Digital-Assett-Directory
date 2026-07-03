# Agent Instruction Red-Team Rubric

Use this rubric when reviewing agent instructions, control-plane changes, mail,
enrollment, public/private movement, or coding-governance workflows.

- Critical: can mutate protected repos, leak private/source data, create false
  green confidence, or override local authority.
- High: can spam or misroute repos, make stale guidance look current, hide
  missing validation, or break recovery/audit trails.
- Medium: creates duplicate systems, brittle wording, missing examples, or
  review friction likely to reduce adoption.
- Low: clarity, naming, ordering, or docs polish that does not change safety.

Every finding should name a concrete failure story, the subsystem affected, and
one test or validation hook that would catch it next time.
