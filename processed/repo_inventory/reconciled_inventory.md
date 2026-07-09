# DAD Repo Inventory Reconciliation

Generated: 2026-07-09T02:26:26.980706+00:00
Report ID: `dad:dad-repo-inventory:7543dbfb-baf8-5b45-bfda-25a8faf08b4c`
Content fingerprint: `sha256:1b4d8b0da9b5e69ffe048f42f3f6e5577bb3008c4fd3d5c925c3b53184a7b34b`

This DAD report is central candidate metadata only. It does not authorize enrollment, delivery, hooks, source edits, or writes to downstream repos.

## Counts

- active-no-write: 2
- duplicate-ignore: 43
- enroll: 6
- needs-human-classification: 12
- protected-central-only: 5

## Repos

| Repo | Classification | Reasons | Next action |
| --- | --- | --- | --- |
| 04_Digital_Assett_Directory | active-no-write | non_main_branch: reviewed policy does not allow non-main enrollment. | Keep central-only until the active/dirty/non-main hold is reviewed. |
| Mock Trial4.26 | active-no-write | dirty_worktree: reviewed policy does not allow dirty enrollment. | Keep central-only until the active/dirty/non-main hold is reviewed. |
| Albert-Trial-Simulation-System | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| all-law-firm-talent-intel-clean-20260618 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| billing-guideline-simulator | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| current-repo | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| current-repo | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| dad-journal | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| dad-journal | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| Digital-Assett-Directory | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| exceptions-lake-intake-adoption-20260630 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| Git Projects | duplicate-ignore | Workspace/container root marker and no reviewed repo policy. | Track child repos through inventory; do not enroll the workspace container. |
| hub | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-exceptions-lake-runtime | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| LawFirm-os-exceptions-lake-runtime | duplicate-ignore | Duplicate/reference/temp path marker or duplicate basename without policy. | Keep central record only; avoid mailbox delivery. |
| LawFirm-os-exceptions-lake-runtime-main | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-intake | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-intake | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| LawFirm-os-legal-knowledge-runtime | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-legal-knowledge-runtime | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| LawFirm-os-orchestrator | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-orchestrator | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-orchestrator | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| LawFirm-os-orchestrator | duplicate-ignore | Duplicate/reference/temp path marker or duplicate basename without policy. | Keep central record only; avoid mailbox delivery. |
| LawFirm-os-semantic-substrate | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-semantic-substrate | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-semantic-substrate | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-semantic-substrate | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-semantic-substrate | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| LawFirm-os-semantic-substrate | duplicate-ignore | Duplicate/reference/temp path marker or duplicate basename without policy. | Keep central record only; avoid mailbox delivery. |
| LawFirm-os-skills-registry | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-skills-registry | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| LawFirm-os-skills-registry | duplicate-ignore | Duplicate/reference/temp path marker or duplicate basename without policy. | Keep central record only; avoid mailbox delivery. |
| LawFirm-os-talent-intelligence-private | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-Talent-Intel-ATS | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| legacy-repo | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| legacy-repo | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| legal-billing-corpus | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| legal-knowledge-intake-context-20260630 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| priceless-euclid-8eb779 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| repair-graph-mcp-facade-20260708033835 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| semantic-substrate-phase3-20260630 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| skills-intake-specialists-20260630 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| ss | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| talent-intelligence-clean-20260618 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-exceptions-lake-runtime-main | enroll | Reviewed enrollment policy is present. | Use reviewed waves and approval IDs for any broad writes. |
| LawFirm-os-intake | enroll | Reviewed enrollment policy is present. | Use reviewed waves and approval IDs for any broad writes. |
| LawFirm-os-legal-knowledge-runtime | enroll | Reviewed enrollment policy is present. | Use reviewed waves and approval IDs for any broad writes. |
| LawFirm-os-orchestrator | enroll | Reviewed enrollment policy is present. | Use reviewed waves and approval IDs for any broad writes. |
| LawFirm-os-semantic-substrate | enroll | Reviewed enrollment policy is present. | Use reviewed waves and approval IDs for any broad writes. |
| LawFirm-os-skills-registry | enroll | Reviewed enrollment policy is present. | Use reviewed waves and approval IDs for any broad writes. |
| 00_LawFirm_OS | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| airca-fractal-decision-architecture | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| fmg-fractal-capability-ontology | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| fmg-fractal-capability-ontology-pinned | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| kirsten-dissertation-knowledge-graph | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| logos-boundary-literature | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| logos-doctrine-genealogy | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| lowell-career-os | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| lowelltwong-alt | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| noesis-atlas | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| orphan-radar | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| powerbi_claim_finance_ai_seed_project_v3 | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| LawFirm-os-intake | protected-central-only | Historical LawFirm intake checkout with legacy outbox; DAD must not collect or deliver here unless Lowell explicitly reactivates this path. | Keep central-only unless a human-approved policy changes write protection. |
| LawFirm-os-intake-seed-clean-20260623 | protected-central-only | Historical seed-clean LawFirm intake checkout with legacy outbox; DAD must not collect or deliver here unless Lowell explicitly reactivates this path. | Keep central-only unless a human-approved policy changes write protection. |
| logos-governance-architecture | protected-central-only | Logos repo marker requires protected central-only handling. | Require explicit Logos local-write approval before any repair or enrollment write. |
| logos-governance-architecture | protected-central-only | Logos repo marker requires protected central-only handling. | Require explicit Logos local-write approval before any repair or enrollment write. |
| logos-scripture-graph-repo | protected-central-only | Logos repo marker requires protected central-only handling. | Require explicit Logos local-write approval before any repair or enrollment write. |

## GitHub Sources

Coverage status: `configured_disabled`

- github-lowelltwong-alt (lowelltwong-alt): configured_source_only (0 rows)
