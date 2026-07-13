# DAD Cockpit Control Plane — Design

Status: candidate design (medium-risk load-bearing decision; human review required
before implementation of scoring or schema changes).
Risk tier: medium — this defines UI information architecture, one new schema, and a
scoring methodology that future agents will inherit. It changes no runtime behavior
by itself, every piece ships behind existing DAD gates, and rollback is "delete the
generated site." Reviewed under `docs/LOAD_BEARING_DECISION_REVIEW.md` (self
premortem included below).
Methodology introduced: `dad.cockpit-pertinence.v0` (heuristic until reviewed).

## 1. Problem

The portfolio is 31 projects, ~121 worktrees, ~211 branches, built heavily in
parallel. A page-per-repo (or page-per-worktree) UI means dozens of clicks to answer
the three questions that actually matter each session:

1. What is going on?
2. What needs my attention right now?
3. What is high risk and what is high leverage?

Each repo also runs **multiple concurrent projects inside one repo** (examples:
the mock-trial repo carries the podcast, the NITA-PDF quality loop, and the growing
simulator; the intake repo carries the path to real intake, the synthetic-intake-agent
idea, and public-data validation via CourtListener / Enron-style corpora). Git alone
cannot see those; the UI must.

## 2. What already exists (build on it, don't rebuild)

| Signal | Source | Status |
|---|---|---|
| Attention queue with priority, reasons, next action | `~/.dad/data/processed/reports/portfolio_attention.json` (`dad.portfolio_attention.v1`), rendered to `portfolio_attention.html` (the page previously served at 127.0.0.1:4173) | working, but **its generator is not tracked in this repo — locate and re-home it into `src/digital_asset_directory/` as step one** |
| Daemon health, follow-through issues (131), journal status | `daemon-heartbeat.json`, `daily_review_queue.md/json` | working |
| Mail volumes, quarantine, release-required counts | `mail_center.json` | working |
| Enrollment roster + waves + visibility | `asset-dir enroll discover` / `enroll status` | working |
| Roadmap phases + gate evidence | `roadmap/roadmap.yaml`, `roadmap/gate-evidence.json` | working |
| Repo-local asset memory | `asset-dir dad repo-assets` | working |

The cockpit is therefore mostly a **join + rank + render** problem, plus one new
contract (missions) and one new methodology (pertinence).

## 3. Information architecture — three layers, feed-first

Design rule: **the cockpit is a ranked feed, not a menu.** Pages exist for every
repo, but you arrive at them through signals, not by browsing. Invariant: any
worktree is ≤ 2 clicks from the cockpit. A command palette (Ctrl+K fuzzy jump to
repo/track/branch) covers the rest.

### Layer 1 — Cockpit (one page, "the glass")

Zones, top to bottom:

1. **Now** — top 3–7 items across the whole portfolio ranked by pertinence
   (§5). Each card: repo, track, why (reason codes in plain words), suggested next
   action, one deep link.
2. **Waiting on you** — items blocked *only* on a human decision (gate evidence,
   mail release decisions, enrollment approvals, weight-set approvals). These are
   the highest-leverage minutes of the day: agents and daemons idle until they are
   answered, so they outrank almost everything.
3. **Risk board** — public-facing exposure, data-classification gates (e.g. real
   client data currently `blocked`), conflicted/diverged worktrees, quarantined
   mail, stale governance surfaces.
4. **Leverage board** — what unblocks the most downstream work: roadmap gates with
   many dependents, missions within one milestone of a payoff, assets requested by
   several repos.
5. **Mission strip** — one row per active mission across all repos: goal, phase,
   milestone proximity, last evidence date. This is where "mock trial podcast",
   "NITA parity loop", "simulator", "real-intake path", "synthetic intake agent",
   "public-data validation" each get exactly one row.
6. **Portfolio pulse** — daemon freshness, mail digest age, follow-through issue
   count, scan coverage. Small; green when boring.

### Layer 2 — Repo page (one per enrolled repo)

Header: mission statement, visibility/wave, data classification, authority notes.
Body:

- **Tracks** — the projects inside the repo. Each track card: goal, current state,
  next milestone, latest evidence link, open experiments + budget consumed,
  blockers, and the attention items scoped to it.
- **Worktree & branch map** — grouped **by track**, not alphabetically. Mapping via
  rules in the missions file (branch patterns / path globs → track) with manual
  override; unmapped branches land in an "unassigned" bucket that is itself an
  attention signal.
- **Gates & roadmap** — repo-relevant phases and what evidence each gate still needs.
- **Mail** — inbox/outbox/quarantine for this repo, release-required items flagged.

### Layer 3 — Track drill-down (in place, no navigation)

A track card expands inline: experiment history (e.g. NITA loop run N: output
graded vs Lowell-baseline), linked worktrees/sessions, decision log. No separate
page = no click tax.

## 4. Repo mission contract — `dad.repo-missions.v1`

New schema `schemas/repo-missions.schema.json`; instance lives in each enrolled repo
at `.digital-asset/portfolio/missions.json`, delivered/updated through the normal
enrollment + mail gates (never by direct DAD write).

```jsonc
{
  "schema_version": "dad.repo-missions.v1",
  "repo_ref": "dad://repo/mock-trial-4-26",
  "mission": "Trial-advocacy training system: simulator, podcast, and NITA-grade output loops.",
  "tracks": [
    {
      "track_id": "podcast",
      "goal": "Produce and publish the mock-trial podcast.",
      "milestones": [{ "id": "ep-pipeline", "title": "Repeatable episode pipeline", "status": "in_progress" }],
      "map_rules": { "branch_patterns": ["podcast/*"], "path_globs": ["podcast/**"] }
    },
    {
      "track_id": "nita-parity-loop",
      "goal": "Loop the original NITA PDF until generated output grades at parity with Lowell's own work.",
      "experiments": [{
        "id": "nita-run",
        "metric": "grader_parity_score",
        "baseline": "lowell-manual-output",
        "budget": { "unit": "usd", "limit": 50, "period": "monthly" }
      }],
      "map_rules": { "branch_patterns": ["nita/*", "*pdf-loop*"] }
    },
    {
      "track_id": "simulator",
      "goal": "Grow the trial simulator.",
      "map_rules": { "branch_patterns": ["sim/*", "simulator/*"] }
    }
  ]
}
```

Intake repo equivalent: tracks `real-intake-path` (carries the real-client-data
gate, currently blocked — the track card must show that gate, not hide it),
`synthetic-intake-agent` (public data → synthetic intake documents, tested to an
explicit budget), `public-data-validation` (CourtListener / Enron-style corpora,
shared with mock-trial — cross-repo tracks may declare `shared_with` refs).

Track state, experiment results, and budget consumption flow back as **metadata-only
status packets through the repo outbox** (existing mail channel; no new write path,
no payloads, no client data).

## 5. Pertinence methodology — `dad.cockpit-pertinence.v0`

Per `learning-rule:calculated-score-requires-methodology`: formula, inputs,
thresholds, uncertainty, and version are explicit. **All v0 weights are heuristic
and marked as such in the UI until a human reviews them.**

```
pertinence = clamp(0, 100,
    0.40 * urgency      // existing attention priority (0–100) from portfolio_attention v1,
                        // plus +10 if a declared milestone is within 7 days
  + 0.30 * risk         // 0–100: conflicted worktree 40; public_facing repo with pending
                        // unreleased private-origin mail 30; diverged_from_upstream 15;
                        // data-classification gate touched 25; quarantined mail for repo 10 (capped)
  + 0.30 * leverage     // 0–100: human-gate-only blocker 40; roadmap gate with N dependents
                        // min(10*N, 30); mission milestone ≤ 1 step away 20; asset requested
                        // by ≥2 repos 10 (capped)
) * decay
decay = 1.0 if signal fresh; 0.9 if underlying report > 26h old (matches daemon
        stale_after_hours); item never hidden by decay.
```

- **Ties**: higher risk term wins, then older `last_activity_at`, then project name A→Z.
- **Missing signals**: contribute 0 and set a visible `signal_missing` flag on the
  card — never imputed.
- **Separate fields stay separate**: urgency, risk, leverage, and pertinence are all
  shown; the composite never replaces its inputs (same discipline as
  current-score vs ceiling in `docs/ASSET_VALUE_MODEL.md`).

### 5.1 Adaptivity — how "what matters" changes over time, deterministically

The user's key requirement: the cockpit must learn what is pertinent as the
portfolio changes, without becoming an opaque ranker.

1. Every cockpit interaction is an **append-only event**: `acted` (deep link
   followed / command copied), `snoozed(duration)`, `dismissed(reason)`, `ignored`
   (rendered in Now N times with no interaction).
2. Weekly, the daemon recomputes **per-reason-class weight multipliers** with fixed
   rules — not ML:
   - a reason class `ignored` ≥ 5 consecutive times → multiplier ×0.8 (floor 0.4);
   - a reason class `acted` within 24h of surfacing → ×1.1 (cap 1.5);
   - `dismissed` with reason "not relevant" ×0.7; `snoozed` leaves weight unchanged
     (snooze is scheduling, not judgment);
   - new reason classes start at 1.0 with a 2-week probation boost (+0.1) so new
     signal types get seen before they can be buried.
3. Each recompute emits a **versioned weight set + changelog diff**
   (`dad.cockpit-weights.vN`) and lands in "Waiting on you" for one-click approval.
   Scores are always reproducible from (data snapshot, weight-set version).
4. Demotion never hides: the full queue always shows every item with its current
   multiplier, so a down-weighted class is inspectable, not invisible.

Non-applicability note (per `learning-rule:context-bound-lessons-need-non-applicability`):
this adaptivity rule set applies to *cockpit surfacing order only*. It must not be
reused to rank asset value, calibration labels, or graph edges — ignoring a UI card
is weak evidence about the underlying asset, and treating it as strong evidence
would corrupt calibration. Danger if misapplied: silent value-score drift from
attention fatigue.

## 6. Delivery architecture

Local-only, read-only, no external network — consistent with DAD authority
boundaries.

- **Phase A (static, ~the current 4173 experience, multiplied):**
  `asset-dir dashboard build` joins the sources in §2 (+ missions files) into
  `~/.dad/data/processed/dashboard/` — `index.html` (cockpit), `repo/<slug>.html`,
  and a single `data.json`. `asset-dir dashboard serve --port 4173` = stdlib
  `http.server`, localhost bind only. Daemon cycle re-runs `build`.
  First implementation step: **find and re-home the existing untracked
  portfolio_attention generator** into `src/digital_asset_directory/portfolio_attention.py`
  with tests, then extend it.
- **Phase B (live-ish):** small local server with SSE refresh after each daemon
  cycle; command palette; per-repo pages rendered from `data.json` client-side so
  build stays O(1) pages.
- **Phase C (adaptive):** interaction-event capture (local POST → append-only
  journal), weekly weight recompute + approval flow (§5.1).

UI **never executes actions**. Every suggested next action renders the exact CLI
command with a copy button. The dashboard is a pane of glass over candidate
metadata; authority boundaries stay where they are.

## 7. Premortem (medium-risk gate)

- *Cockpit becomes a second source of truth.* Mitigation: every number links to the
  generating report; `data.json` records source paths + generated_at; banner repeats
  the authority boundary.
- *Missions files rot.* Mitigation: missions freshness joins the existing weekly
  freshness checks; a stale missions file is itself an attention item ("this repo's
  stated goals are N weeks old").
- *Adaptive weights bury something important.* Mitigation: floors, probation boost,
  human-approved weight sets, full queue never hides items.
- *Scoring formula gets silently edited.* Mitigation: methodology version in every
  payload; tests pin the formula; changes require a new version + changelog.
- *Two dashboards diverge (old portfolio_attention.html vs cockpit).* Mitigation:
  cockpit **replaces** the old HTML render; the JSON contract stays and is consumed,
  not duplicated.
- Rejected alternatives: (a) full web app with DB — overkill, new attack surface,
  violates local-simplicity; (b) pure per-repo pages without a ranked cockpit —
  reproduces the click-fatigue problem this design exists to kill; (c) LLM-ranked
  feed — non-deterministic, unauditable, conflicts with score-methodology rule.

## 8. Build order

1. Re-home + test the portfolio_attention generator (unblocks everything).
2. `repo-missions` schema + missions files for DAD, mock-trial, intake (three real
   examples above) + validation in `asset-dir validate`.
3. `asset-dir dashboard build/serve` Phase A (cockpit + repo pages, static
   pertinence v0 with weights all 1.0 multipliers).
4. Track-scoped worktree mapping + mail/gate joins on repo pages.
5. Phase B liveness + command palette.
6. Phase C interaction events + weekly weight recompute + approval flow.

Each step is narrow, reversible, and independently shippable.
