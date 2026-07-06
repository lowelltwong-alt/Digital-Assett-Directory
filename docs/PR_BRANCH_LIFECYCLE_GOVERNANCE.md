# PR And Branch Lifecycle Governance

Status: reviewed DAD lesson and repo-facing governance pattern.

Use this when work is ready for a pull request, a pull request is open, or a
branch has meaningful changes that could become conflict debt if it sits.

## Lesson

PR-ready work must not become an unowned holding pen. When many branches or PRs
are created during active buildout, every one needs a status, owner, next
action, and escalation clock. Otherwise useful work turns into stale generated
evidence, merge conflicts, duplicate fixes, and false confidence about what is
actually shipped.

This lesson applies to DAD and to enrolled repos. It is not a mandate to create
process for tiny local edits. It activates when work is staged for a PR, when an
actual PR exists, or when a branch is intentionally kept after the current work
session.

## Required State

Track these fields in PR descriptions, handoffs, repo outbox mail, or a local
ledger that the repo already uses:

- `repo_id`
- `branch`
- `base_branch`
- `pr_url` or `pr_state` if no PR exists yet
- `intent`
- `owner_or_next_reviewer`
- `status`: `drafting`, `ready_for_pr`, `pr_open`, `blocked`, `merged`,
  `superseded`, `abandoned`, or `needs_human_decision`
- `last_reviewed_at`
- `next_action`
- `escalate_after`
- `validation_refs`
- `supersedes_or_depends_on`

If the branch touches generated evidence, manifests, roadmap status, registry
semantics, source-boundary policy, public/private release behavior, or
cross-repo governance, the next action must include a freshness check before
merge.

## Escalation Clocks

Default clocks are intentionally simple:

- Same active build session: resolve, PR, or record why the branch stays open.
- More than 24 hours with `ready_for_pr` and no PR: warn in handoff or DAD mail.
- More than 72 hours with an open PR and no next action: request human attention.
- More than 7 days without merge, rejection, or supersession: escalate as
  `needs_human_decision`.

Repos may use stricter clocks. Protected, public-facing, release, schema,
governance, or generated-evidence changes should escalate earlier.

## Deterministic Checks

Before merging or deleting stale work, collect metadata-only evidence:

```text
gh pr list --state open --json number,title,headRefName,baseRefName,updatedAt,url
git branch -vv --all
git rev-list --left-right --count <base>...<branch>
git cherry -v <base> <branch>
git merge-tree --write-tree <base> <branch>
git status --short --branch
```

Use `git cherry -v` and focused file inspection to decide whether a branch is
already patch-equivalent to the base. Use `git merge-tree` only as conflict
evidence; it does not prove semantic safety. Generated reports must be
regenerated or verified fresh before they are trusted.

## DAD Mail Pattern

Send DAD a candidate governance packet when:

- a PR-ready branch is left open at handoff;
- an open PR has no owner, next action, or escalation date;
- a branch is superseded, patch-equivalent, conflict-heavy, or duplicate;
- generated evidence on a branch is stale relative to source methodology;
- several agents are building in parallel and branch/PR queue risk is rising.

Do not send source blobs, private rows, secrets, raw logs, hidden reasoning, or
full diffs. Send metadata, commit IDs, PR URLs, paths, validation command names,
hashes, and short summaries.

## Postflight

Every material postflight should answer:

- Did this work create or update a PR-ready branch?
- If yes, is it merged, pushed as a PR, superseded, abandoned, or escalated?
- What is the next action and who or what is responsible?
- When should a human be alerted if it is still stuck?

Leaving this implicit is the failure mode.
