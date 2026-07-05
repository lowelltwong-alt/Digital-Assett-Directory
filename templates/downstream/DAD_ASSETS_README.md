# DAD Repo-Local Digital Asset Memory

This directory is the source repo's local memory for digital assets that may matter to DAD or to future agents working in this repo.

Rows in `index.jsonl` are candidate asset cards. They are metadata pointers only: paths, short summaries, tags, hashes, validation commands, source refs, and review notes. Do not copy private rows, credentials, raw logs, large generated outputs, full source files, hidden reasoning, or source-authority decisions into this directory.

## Standard Paths

- `.digital-asset/assets/index.jsonl` records source-owned candidate digital assets.
- `.digital-asset/assets/adoption.jsonl` records local decisions to use, watch, defer, reject, or retire DAD assets.
- `.digital-asset/learning/events.jsonl` records source-owned learning events.
- `.digital-asset/mail/outbox.jsonl` sends candidate summaries to DAD when local policy allows.

## Fractal Placement

Use layers 1-9 for stable placement: identity, object, claim, relationship, validation, retrieval, fractal address, artifact evidence, and learning adaptation.

Layer 9 is DAD's learning/adaptation layer. Use it for what changed, what worked, what failed, what should be reused, and what should be checked next time. If this repo has a local address model that uses layer 9 for orchestration/workflow, label that as a source-repo variant and point to the local authority.

Keep layer values compact. Use IDs, paths, hashes, tags, and refs. Put long workflow details in a workflow card or source doc and point to it.

## When To Add A Row

Add a row when the repo creates or discovers a reusable workflow, schema, validator, prompt, harness, research packet, governance map, data map, coding trick, exception/fix pattern, or architecture reference that future agents should not have to rediscover.

Mail to DAD is still candidate-only. DAD may read this directory during approved scans, but local source authority stays in this repo.
