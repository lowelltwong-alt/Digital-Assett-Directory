# Cross-Vendor Review Policy

Status: candidate process guidance until locally adopted.
Scope: docs and process only. This file does not install bots, change branch
protection, or alter GitHub App / connector settings.

## Rule

When both vendors are available, the reviewer's vendor should differ from the
author's vendor:

- Claude-authored material should receive an OpenAI/Codex review lane.
- Codex-authored material should receive a Claude review lane before merge.
- Same-vendor review is allowed only when the other vendor is unavailable; say
  why in the PR declaration.

## PR declaration

Every material PR should declare:

```text
cross-vendor review: yes | no | why
```

- `yes` means a different-vendor review was obtained or is in progress.
- `no` is incomplete for merge-ready material work unless `why` records a
  concrete unavailability or human waiver.
- `why` is required whenever the answer is not a plain `yes`.

## Review-lane checklist

Use `review-lane:cross-vendor-review` as a checklist (or subagent when available)
for material coding, architecture, governance, schema, or cross-repo work:

1. Identify author vendor.
2. Prefer a different-vendor reviewer.
3. Answer or fix every review finding before merge.
4. If author and reviewer disagree after one reply round, escalate one tier.
5. Persistent disagreement at sol / sonnet-high stops for a human; Claude Fable
   arbitration requires a separate named human approval.

## Deterministic backstop

`required_conversation_resolution` on the protected branch remains the fail-closed
backstop for unanswered review threads. Agents must not disable or weaken it.

## Human-owned settings (do not change from agents)

These remain Lowell-owned. Agents may list them; agents must not modify them:

- Codex GitHub connector review configuration
- Branch protection rules, including required checks and conversation resolution
- Bot / GitHub App installations and permissions
- Global IDE hooks, plugins, or notification settings that auto-dispatch review

## Authority boundary

This policy is advice and process documentation only. It does not authorize
dispatch, merge, bot installation, branch-protection edits, or Fable use.
