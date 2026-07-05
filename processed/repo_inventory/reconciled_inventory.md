# DAD Repo Inventory Reconciliation

Generated: 2026-07-05T18:28:31.307660+00:00
Report ID: `dad:dad-repo-inventory:f40d5ea9-3419-569f-b580-cbce46e4bdbb`
Content fingerprint: `sha256:ad19db79068bd8e6bfd640321e759fca9c392ffe123ac0029a45dfc892ce3636`

This DAD report is central candidate metadata only. It does not authorize enrollment, delivery, hooks, source edits, or writes to downstream repos.

## Counts

- active-no-write: 8
- duplicate-ignore: 26
- needs-human-classification: 11
- protected-central-only: 3

## Repos

| Repo | Classification | Reasons | Next action |
| --- | --- | --- | --- |
| 04_Digital_Assett_Directory | active-no-write | dirty_worktree: reviewed policy does not allow dirty enrollment. | Keep central-only until the active/dirty/non-main hold is reviewed. |
| LawFirm-os-exceptions-lake-runtime-main | active-no-write | dirty_worktree: reviewed policy does not allow dirty enrollment.; non_main_branch: reviewed policy does not allow non-main enrollment. | Keep central-only until the active/dirty/non-main hold is reviewed. |
| LawFirm-os-intake | active-no-write | dirty_worktree: reviewed policy does not allow dirty enrollment.; non_main_branch: reviewed policy does not allow non-main enrollment. | Keep central-only until the active/dirty/non-main hold is reviewed. |
| LawFirm-os-legal-knowledge-runtime | active-no-write | dirty_worktree: reviewed policy does not allow dirty enrollment.; non_main_branch: reviewed policy does not allow non-main enrollment. | Keep central-only until the active/dirty/non-main hold is reviewed. |
| LawFirm-os-orchestrator | active-no-write | dirty_worktree: reviewed policy does not allow dirty enrollment.; non_main_branch: reviewed policy does not allow non-main enrollment. | Keep central-only until the active/dirty/non-main hold is reviewed. |
| LawFirm-os-semantic-substrate | active-no-write | dirty_worktree: reviewed policy does not allow dirty enrollment.; non_main_branch: reviewed policy does not allow non-main enrollment. | Keep central-only until the active/dirty/non-main hold is reviewed. |
| LawFirm-os-skills-registry | active-no-write | dirty_worktree: reviewed policy does not allow dirty enrollment.; non_main_branch: reviewed policy does not allow non-main enrollment. | Keep central-only until the active/dirty/non-main hold is reviewed. |
| Mock Trial4.26 | active-no-write | dirty_worktree: reviewed policy does not allow dirty enrollment.; non_main_branch: reviewed policy does not allow non-main enrollment. | Keep central-only until the active/dirty/non-main hold is reviewed. |
| all-law-firm-talent-intel-clean-20260618 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| exceptions-lake-intake-adoption-20260630 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| Git Projects | duplicate-ignore | Workspace/container root marker and no reviewed repo policy. | Track child repos through inventory; do not enroll the workspace container. |
| LawFirm-os-exceptions-lake-runtime | duplicate-ignore | Duplicate/reference/temp path marker or duplicate basename without policy. | Keep central record only; avoid mailbox delivery. |
| LawFirm-os-exceptions-lake-runtime-main | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-intake | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-intake-seed-clean-20260623 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-legal-knowledge-runtime | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-orchestrator | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-orchestrator | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-orchestrator | duplicate-ignore | Duplicate/reference/temp path marker or duplicate basename without policy. | Keep central record only; avoid mailbox delivery. |
| LawFirm-os-semantic-substrate | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-semantic-substrate | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-semantic-substrate | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-semantic-substrate | duplicate-ignore | Duplicate/reference/temp path marker or duplicate basename without policy. | Keep central record only; avoid mailbox delivery. |
| LawFirm-os-skills-registry | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-skills-registry | duplicate-ignore | Duplicate/reference/temp path marker or duplicate basename without policy. | Keep central record only; avoid mailbox delivery. |
| LawFirm-os-talent-intelligence-private | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-Talent-Intel-ATS | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| legal-billing-corpus | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| legal-knowledge-intake-context-20260630 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| priceless-euclid-8eb779 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| semantic-substrate-phase3-20260630 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| skills-intake-specialists-20260630 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| ss | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| talent-intelligence-clean-20260618 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| 00_LawFirm_OS | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| airca-fractal-decision-architecture | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| fmg-fractal-capability-ontology | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| fmg-fractal-capability-ontology-pinned | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| kirsten-dissertation-knowledge-graph | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| logos-boundary-literature | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| lowell-career-os | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| lowelltwong-alt | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| noesis-atlas | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| orphan-radar | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| powerbi_claim_finance_ai_seed_project_v3 | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| logos-governance-architecture | protected-central-only | Logos repo marker requires protected central-only handling. | Require explicit Logos local-write approval before any repair or enrollment write. |
| logos-governance-architecture | protected-central-only | Logos repo marker requires protected central-only handling. | Require explicit Logos local-write approval before any repair or enrollment write. |
| logos-scripture-graph-repo | protected-central-only | Logos repo marker requires protected central-only handling. | Require explicit Logos local-write approval before any repair or enrollment write. |

## GitHub Sources

Coverage status: `configured_disabled`

- github-lowelltwong-alt (lowelltwong-alt): configured_source_only (0 rows)
