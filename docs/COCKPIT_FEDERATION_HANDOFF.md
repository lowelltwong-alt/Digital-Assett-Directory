# Cockpit Federation — Build Handoff (Copilot · Codex · Albert)

Status: handoff / build brief. Extends `docs/COCKPIT_CONTROL_PLANE_DESIGN.md`.
Author: Claude (design). Owner to route: Lowell.
Risk tier: medium — defines a cross-repo dashboard contract that multiple agents and
repos will inherit. Changes no runtime behavior on its own; every install lands
behind existing DAD enrollment/mail gates. Rollback = delete generated sites.

## 0. What changed from the first design

The first design put one central builder (`asset-dir dashboard build`) that read every
repo and rendered a single site. Lowell's directive changes the **topology** to
federated and sovereign:

> Each repo should have its own dashboard. The DAD cockpit connects to those plus
> the one already designed. A repo's local dashboard must still be visible if the
> dashboard is split off from DAD.

That last sentence is the load-bearing requirement. It maps directly onto the
sovereignty lifecycle (`incubating → dad_governed_child → … → fully_detached`): a
repo's dashboard has to keep working after the repo detaches from the DAD hub.
So dashboards are **owned locally and federated upward**, never owned centrally.

## 1. Three tiers, connected by summaries — not by internals

```
┌────────────────────────────────────────────────────────────┐
│  TIER 2 · DAD COCKPIT              (Copilot builds — WP-A)  │
│  federates every summary + the portfolio_attention feed     │
│  the "glass" already mocked up; now it CONNECTS, not reads  │
└───────────────▲───────────────────────────▲────────────────┘
                │ reads summary.json         │ reads summary.json
      ┌─────────┴──────────┐        ┌─────────┴───────────────┐
      │ TIER 1 · GROUP     │        │ (standalone repos with  │
      │ Logos dashboard    │        │  no group, e.g. DAD,    │
      │ (Codex — WP-B)     │        │  intake, talent-intel)  │
      │ federates 4 Logos  │        └─────────┬───────────────┘
      │ repos' summaries   │                  │
      └──▲────▲────▲───▲───┘                  │
         │    │    │   │ reads summary.json    │
   ┌─────┴┐ ┌─┴─┐ ┌┴──┐ ┌┴────┐        ┌───────┴────────────────┐
   │scrip-│ │bnd│ │doc│ │gov  │        │ TIER 0 · REPO-LOCAL     │
   │ture  │ │lit│ │gen│ │arch │        │ Albert dashboard         │
   └──────┘ └───┘ └───┘ └─────┘        │ (reference — WP-C)       │
   each = TIER 0 repo-local dashboard  │ standalone, offline-safe │
                                       └──────────────────────────┘
```

**The only wire between tiers is a published summary file.** Cut it and the lower
tier is unaffected — that is what "split off and still visible" means, mechanically.

- **Tier 0 — repo-local dashboard.** Lives inside the repo. Depends ONLY on local
  git + the repo's own `.digital-asset/` data. No import of the DAD hub package at
  runtime. Runs with `python -m repo_dashboard serve` (or equivalent) from a clean
  checkout with the hub absent. Publishes `dad.dashboard-summary.v1` (§3).
- **Tier 1 — group dashboard.** Federates a family of related repos by reading their
  published summaries. Logos is the first group. A group dashboard is itself a Tier-0
  dashboard that also aggregates children, and publishes its own rolled-up summary.
- **Tier 2 — DAD cockpit.** What's already designed and mocked. Now it *connects to*
  Tier-1/Tier-0 summaries plus the central `portfolio_attention.json` feed, instead
  of reading each repo's internals. If a summary is missing (repo detached, offline,
  or never installed), the cockpit shows the repo as `unfederated` — not an error.

## 2. Authority — who may write where (read this before building)

DAD may not write dashboards into other repos. Per `AGENTS.md`, DAD writes broadly
only during `enroll apply` / `update-apply` with a reviewed approval ID; normal
operation writes only to `.digital-asset/mail/**`. Therefore:

- **The Tier-0 dashboard code that lands inside a repo is installed by that repo's own
  agent, or through the enrollment gate — never by DAD reaching in.** Copilot builds
  the reusable *template*; the repo adopts it locally.
- **Logos repos are read-only / protected from DAD's side.** From `enroll discover`:
  `logos-boundary-literature`, `logos-doctrine-genealogy` (wave
  `logos-llos-v1-read-only`), `logos-governance-architecture` (wave
  `wave-2026-07-01-protected-logos`, apply not allowed) — only
  `logos-scripture-graph` has a contract. Codex builds the Logos dashboard **working
  inside the Logos repos directly**, honoring those read-only waves; it does not
  authorize DAD to push into them.
- **Albert** (`Albert-Trial-Simulation-System`, internal, wave
  `wave-2026-07-01-internal-apps`, has contract) is the pilot: its local dashboard
  lives *inside Albert* and is built there.
- Summaries flow **up** as metadata-only candidate evidence (like DAD mail). No raw
  source, secrets, or client payloads cross a tier boundary. Intake stays
  synthetic-only while the real-client-data gate is `blocked`.

## 3. The connection contract — `dad.dashboard-summary.v1`

One schema, published by every dashboard at a well-known local path:
`<repo>/.digital-asset/portfolio/dashboard-summary.json`. This is the entire API
between tiers. Keep it small, metadata-only, and stable.

```jsonc
{
  "schema_version": "dad.dashboard-summary.v1",
  "repo_ref": "dad://repo/mock-trial-4-26",
  "display_name": "Albert-Trial-Simulation-System",
  "generated_at": "2026-07-12T00:00:00Z",
  "sovereignty_state": "dad_governed_child",   // maps to the lifecycle in memory
  "visibility": "internal",                      // internal | private | public
  "standalone": true,                            // true = renders with no hub present
  "health": { "status": "ok", "attention_items": 2, "top_pertinence": 79 },
  "gates_blocked_on_human": 0,
  "tracks": [                                    // from dad.repo-missions.v1
    { "track_id": "nita-parity-loop", "state": "run 7 · 0.81", "milestone_distance": "2 runs",
      "attention": 1, "pertinence": 79 }
  ],
  "risk": { "conflicted_worktrees": 0, "public_exposure": 0, "data_gate": "none" },
  "leverage": { "milestones_one_step_away": 1 },
  "children": [],                                // group dashboards list child repo_refs here
  "source_reports": ["portfolio_attention.json", ".digital-asset/portfolio/missions.json"],
  "authority_note": "Metadata-only candidate evidence. Reading this never authorizes a write to this repo."
}
```

Rules:
- The upper tier reads **only** this file. It must never reach into a child repo's git
  or internals. That isolation is what preserves sovereignty.
- Pertinence stays `dad.cockpit-pertinence.v0` (design §5), still heuristic-until-
  reviewed; each dashboard reports its inputs (`urgency`/`risk`/`leverage`) so a
  federating tier can re-rank without inventing a second formula.
- `standalone: true` is a promise the Tier-0 dashboard must be able to keep: verified
  by the acceptance test in §5.

## 4. Work packages

### WP-A — DAD cockpit federation + local-dashboard template  → **Copilot**
1. **Depends on:** re-homing the untracked `portfolio_attention` generator into
   `src/digital_asset_directory/` with tests (already flagged as build step 1;
   a task chip exists). WP-A cannot ship until that lands.
2. Build the reusable **Tier-0 local dashboard template** — a self-contained generator
   a repo vendors (no DAD-hub import at runtime): reads local git + local
   `.digital-asset/`, renders `index.html` + per-track drill-downs, and writes
   `dashboard-summary.json`. This is the artifact Albert and every other repo adopt.
3. Build `asset-dir dashboard federate`: discover published summaries across enrolled
   repos, merge with the central `portfolio_attention.json`, render the cockpit
   (§1 Tier 2) with a live/`unfederated`/`stale` status per repo, and deep-link each
   card to that repo's own local dashboard. Localhost bind only; daemon re-runs it.
4. Cockpit must degrade gracefully: a missing/old summary → `unfederated`/`stale`
   badge, never a crash. The mock at
   `docs/COCKPIT_CONTROL_PLANE_DESIGN.md` + the published artifact are the visual spec.

### WP-B — Logos group dashboard  → **Codex**
1. Working **inside the Logos repos** (respect read-only/protected waves; do not
   request DAD write access to them), stand up a Tier-1 group dashboard that
   federates the Logos family summaries: `logos-scripture-graph` (note: 43 worktrees /
   58 branches — pagination and track-grouping matter most here),
   `logos-boundary-literature`, `logos-doctrine-genealogy`,
   `logos-governance-architecture`.
2. Each Logos repo publishes a Tier-0 `dashboard-summary.v1`; the group dashboard
   rolls them into one summary with `children: [...]` and its own health/risk/leverage.
3. The group dashboard is itself standalone (`standalone: true`) — it must render for
   the Logos family even if DAD is absent. It publishes upward for the DAD cockpit.
4. Reuse the WP-A template once available; until then, stub against the §3 schema so
   the contract, not the implementation, is the integration point.

### WP-C — Albert reference local dashboard (inside Albert)  → **Albert repo**
1. Adopt the WP-A Tier-0 template inside `Albert-Trial-Simulation-System`. This is the
   **pilot** that proves the standalone/sovereign contract end to end.
2. Wire it to Albert's three tracks (`nita-parity-loop`, `simulator`, `podcast`) via a
   `dad.repo-missions.v1` missions file (design §4 has the exact example).
3. Ship the §5 standalone acceptance test in Albert's own CI so "split off and still
   visible" is enforced, not assumed.

## 5. Acceptance test for "split off and still visible" (all Tier-0/1 dashboards)

Non-negotiable, because it is the whole point:

```
# from a checkout with the DAD hub deliberately absent from PYTHONPATH / disk:
$ unset DAD_HUB PYTHONPATH
$ <repo-dashboard> build && <repo-dashboard> serve --port 0
# expected: renders local attention, tracks, and health with zero hub imports;
# dashboard-summary.json is written; no network; no error about a missing hub.
```

If a dashboard imports the DAD hub package, calls the central CLI, or reads
`~/.dad/**` at runtime, it fails this test and violates the sovereignty requirement.
The hub is a *federator that reads summaries*, never a *runtime dependency of the
children*.

## 6. Build order & dependencies

1. Re-home `portfolio_attention` generator (unblocks WP-A) — task chip open.
2. WP-A step 2: Tier-0 template + `dad.dashboard-summary.v1` schema + §5 test.
3. WP-C: Albert adopts the template (first real Tier-0 dashboard, proves the contract).
4. WP-A step 3: `dashboard federate` cockpit connects Albert's summary → the glass.
5. WP-B: Logos group dashboard (Tier-0 per repo → Tier-1 group → cockpit).
6. Roll the template to remaining repos (intake next — carries the blocked data gate).

Each step is independently shippable and reversible.

## 7. Open decisions for Lowell (flag, don't guess)

- **Group membership beyond Logos.** Should the LawFirm-OS repos (orchestrator,
  intake, semantic-substrate, skills-registry, exceptions-lake, talent-intel) form a
  second Tier-1 group with its own dashboard, or federate individually into the
  cockpit? Default assumption if unanswered: individual Tier-0 → cockpit, add a group
  later if the LawFirm family grows a shared story.
- **Where the cockpit itself is served.** Same localhost `4173` slot the old
  `portfolio_attention.html` used, or a new port so both can run during migration?
  Default: reuse `4173`, since the cockpit replaces that page.
- **Summary transport.** Read summaries directly from each repo's working copy on
  disk (simplest, all local), or route them through DAD mail as candidate evidence
  (more governed, survives repos moving)? Default: direct on-disk read for local
  federation; mail only when a repo is remote.

## 8. How this is being routed

- This doc + `docs/COCKPIT_CONTROL_PLANE_DESIGN.md` + the mockup artifact are the spec
  the receiving agents read from the repo.
- A DAD postflight handoff record is written for this session (the durable, agent-
  agnostic channel Codex and other runtimes pick up).
- Task chips are queued for WP-A (Copilot) and WP-B (Codex). Nothing is auto-sent into
  Albert or the Logos repos — installing a dashboard inside another repo is that
  repo's local decision, per the authority boundary in §2.
