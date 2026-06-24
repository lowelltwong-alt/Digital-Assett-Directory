# Phase 1 First Inventory Evidence

Evidence date: 2026-06-24

## Human Authorization

The user authorized the following phase-1 gate posture:

- Current local source scope is approved for the first inventory.
- GitHub scanning is deferred.
- Phase 1 remains `awaiting_human_gate`.
- A tracked roadmap evidence file should record the current gate review.

## Reviewed Source Scope

The active local configuration for the first bounded inventory is `config/sources.local.yaml`.
That file is intentionally ignored by Git because it is machine-local configuration.

Approved current scope:

- Enabled source: `git-projects`
- Source path: `C:\Users\lowel\OneDrive\Desktop\Git Projects`
- Path alias: `git-projects`
- Whole-drive scanning: disabled
- GitHub scanning: disabled

Sensitive or noisy sibling folders remain excluded from the current scope, including:

- `00_LawFirm_OS/**`
- `01_Knowledge_Vaults/**`
- `02_Other_Git_Projects/**`
- `03_World_View/**`
- `90_AI_Tooling_And_Temp/**`
- `99_Archive/**`
- `_shared/**`
- `lawfirm-skills-merge-workspace/**`

The local configuration also excludes dependency/build/generated/secret-like paths, including `.git`, virtual environments, `node_modules`, build outputs, `.env*`, credential/secret patterns, private keys, this repo's private local config, and this repo's generated `raw/`, `processed/`, and `state/` layers.

## Inventory Evidence

The first bounded local-only scan completed successfully.

- Scan ID: `dad:scan:df83aed4-fc71-4da8-8029-e83184b0863e`
- Status: `complete`
- Assets: 108
- Edges: 119
- Alerts: 97
- Errors: none
- Source files mutated: `false`
- Raw observation file: `raw/local/dad-scan-df83aed4-fc71-4da8-8029-e83184b0863e.jsonl`

Required phase-1 output files exist:

- `processed/catalog/assets.jsonl`
- `processed/graph/graph.json`
- `processed/reports/scan_summary.md`
- `processed/alerts/alert_inbox.md`

These outputs remain generated candidate evidence. They do not promote candidate tags, scores, alerts, synergies, or graph edges to reviewed truth.

## GitHub Deferral

GitHub inventory is deferred.

- `GITHUB_TOKEN` was not set during review.
- The GitHub source is disabled in `config/sources.local.yaml`.
- No GitHub scan should run until a fine-grained read-only token scope is explicitly approved.

## Roadmap Status

Phase 1 should remain `awaiting_human_gate`.

This evidence records approval of the current local scope and explicit deferral of GitHub scanning, but it does not claim that the broader local portfolio or GitHub repositories have been inventoried.

## Remaining Review Work

- Review alert volume and calibrate false positives before acting on recommendations.
- Decide whether to authorize additional sibling folders for later bounded scans.
- Decide whether to create and approve a fine-grained read-only `GITHUB_TOKEN` for a bounded GitHub inventory.
