You are working in the user's local Git Projects workspace with DAD present.

## Goal

Use DAD as the execution hub to roll out managed asset pointers, mailboxes, and preflight profile bindings across the approved repos in `rollout/rollout_targets.json`.

## Rules

1. Read DAD's `AI_FRONT_DOOR.md`, `AGENTS.md`, `registry/source-of-truth.json`, `registry/design-authority.json`, and `docs/MAIL_CENTER.md` first.
2. Read each target repo's own front door/README/AGENTS/authority files before modifying that repo.
3. Do not copy full DAD assets into repos unless the target policy explicitly says `vendored_snapshot` or `local_extension`.
4. Preserve existing repo-local instructions and only update DAD managed blocks between markers.
5. Do not install hooks unless `allow_hooks=true` and a human explicitly approves.
6. Do not modify append-only runtime/evidence data.
7. Do not claim completion unless checks run and pass.

## Execution order

1. Validate the rollout target file.
2. Apply wave 0 DAD setup.
3. Apply wave 1 core LawFirm OS pointers.
4. Stop and report before waves 2+ unless explicitly approved.

## Final report

Report repos changed, files changed, commands run, tests run/not run, assumptions, unknowns, risks, and next recommended wave.
