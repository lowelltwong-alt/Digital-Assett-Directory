---
name: dad-harness-engineering-ops
description: Design, select, evaluate, shadow, maintain, supersede, and retire provider-neutral agent harnesses with immutable revisions, typed safe commands, runtime-fit evidence, independent checking, rollback, and human activation.
---

# DAD Harness Engineering Ops

Use this family when a reusable agent, workflow, model route, or local runtime
needs an execution harness or when an existing harness may be stale.

1. Search DAD's harness, skill, workflow, family, and runtime registries.
2. Define the harness contract independently from provider/model names.
3. Record one immutable revision with applicability, runtime requirements,
   positive, negative, recovery, privacy, cost, and rollback evidence.
4. Use `argv[]`, `shell=false`, an allowlisted working directory, explicit
   environment keys, effect class, tool capabilities, and a bounded timeout.
5. Route by exact runtime capabilities and task tags. A match is a candidate,
   not permission to execute.
6. Run shadow and bounded fixture evaluations. Use a separate checker route.
7. Promote, supersede, or retire only with human approval and consumer/blast
   radius evidence. Never let a sentinel rewrite or activate a harness.

The registry is deny-execute. Real delivery remains controlled by an exact
autonomy lease and an outer executor. Research is delta-only and pointer-first;
unchanged cycles use zero model tokens.
