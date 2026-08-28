# Copy/Paste Goal Prompt

Use the prompt below to create a durable Codex goal for this campaign.

```text
Goal: Execute the DAD High-Value Recovery Campaign to an evidence-backed
scale, narrow, retire, or re-audit decision.

Start at docs/campaigns/dad-high-value-recovery/README.md and follow every file
and job packet in its declared order. Treat campaign.md as the human authority
contract and campaign.json as the machine dependency contract.

First turn only: perform workspace lifecycle validation, create or resume one
registered governed worktree, run DAD preflight, bind current source and job
digests into a proposed launch-manifest revision, run both static validators,
and present every unresolved human decision. Do not implement a campaign job
until I explicitly approve that exact launch revision or its digest.

After launch approval, complete one job at a time. Before each job, verify its
dependencies, input digests, authority, lease, exact write paths, budget, and
checker independence. Run the job's deterministic checks and independent gate,
and write only the job's privacy-safe declared outputs. The producer must first
freeze a canonical producer-attempt digest; a distinct checker writes and binds
its own pass-or-challenge record. Never infer a pass from missing data, and do
not confuse checker acceptance of faithful evidence with a favorable outcome.
At J-500, bind every enumerated pilot child slot to an exact case digest and
the accepted binding-table digest. Materialize each child packet in memory,
lease one child case at a time, and permit only its unique case-envelope output;
never execute a 10-, 20-, or 40-case cohort under one lease or select a success
metric after outcomes. Before a parent aggregate, produce a complete closure
that accounts for every started, unstarted, and withdrawn slot and proves no
active lease or unreconciled effect remains.

On blocked or stale authority, stop. On an accepted terminal or inconclusive
pilot outcome, stop that branch, complete its closure, and select only the exact
declared Phase 06 route. The controller and shell adapter may project that route
but may not dispatch or write navigation. Require a separately leased
`campaign-navigation-writer` and distinct `independent-checker` to update
07_EVIDENCE_INDEX.md and handoff.md; permit 08_SUPERSESSION_AND_ARCHIVE_MAP.md
only after signed J-600. Reject missing, stale, mismatched, partial,
projection-only, or unaccepted navigation evidence. Bind J-600 to exactly the
selected predecessor, its closure and checker digests, the route receipt, and
that route's permitted decisions.

Do not publish, push, merge, deploy, change GitHub settings, enroll or mutate a
downstream repository, install a plugin, activate recurring automation, access
secrets, delete or move a worktree, delete or rewrite raw observations, clean a
branch, or perform a destructive lifecycle action without my separate exact
approval for that effect. A campaign goal and a phase approval do not imply any
of those permissions.

Preserve source authority, all unrelated user changes, and immutable evidence.
Do not create a new operating system, outcome ledger, queue, dashboard, radar,
registry family, schema family, agent family, or command if an existing DAD
surface can be repaired or composed. Synthetic evidence cannot satisfy the
real-task value gate.

Do not declare the goal complete until Phase 06 has a human-signed decision,
all required acceptance evidence is present and independently checked, DAD
postflight is recorded, and the governed worktree has an exact lifecycle
disposition. If evidence does not justify scale, narrow or retire the system as
specified instead of extending the build.
```

## What this prompt authorizes

The prompt asks an agent to prepare and, after an exact launch approval, execute
bounded local campaign work. It deliberately leaves external effects and
destructive actions behind separate human gates.

## Recommended launch reply

After reviewing the proposed manifest and human decisions, use language this
specific:

```text
I approve launch of campaign dad-high-value-recovery-v1 revision <revision>
with manifest digest <digest>, owner <name>, expiry <date>, primary metric
<metric>, and the approved repositories/effects listed in the signed launch
receipt. No other external or destructive effects are authorized.
```
