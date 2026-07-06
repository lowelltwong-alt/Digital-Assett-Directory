# DAD Repo Inventory Reconciliation

Generated: 2026-07-06T02:25:30.370556+00:00
Report ID: `dad:dad-repo-inventory:279ac239-2dd1-570b-a02e-d450996bc977`
Content fingerprint: `sha256:d12b7b3be1c12a3dee39c80460a97ecadd0f6f84d566e664bd1f0818fca5eaa8`

This DAD report is central candidate metadata only. It does not authorize enrollment, delivery, hooks, source edits, or writes to downstream repos.

## Counts

- active-no-write: 1
- duplicate-ignore: 62
- needs-human-classification: 13
- protected-central-only: 3

## Repos

| Repo | Classification | Reasons | Next action |
| --- | --- | --- | --- |
| dad-dadm1-compose-input-safety | active-no-write | dirty_worktree: reviewed policy does not allow dirty enrollment.; non_main_branch: reviewed policy does not allow non-main enrollment. | Keep central-only until the active/dirty/non-main hold is reviewed. |
| all-law-firm-talent-intel-clean-20260618 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| exceptions-lake-intake-adoption-20260630 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| Git Projects | duplicate-ignore | Workspace/container root marker and no reviewed repo policy. | Track child repos through inventory; do not enroll the workspace container. |
| LawFirm-os-exceptions-lake-runtime | duplicate-ignore | Duplicate/reference/temp path marker or duplicate basename without policy. | Keep central record only; avoid mailbox delivery. |
| LawFirm-os-exceptions-lake-runtime-main | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-exceptions-lake-runtime-main | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-intake | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-intake | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-intake-seed-clean-20260623 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-legal-knowledge-runtime | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-legal-knowledge-runtime | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-orchestrator | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-orchestrator | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-orchestrator | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-orchestrator | duplicate-ignore | Duplicate/reference/temp path marker or duplicate basename without policy. | Keep central record only; avoid mailbox delivery. |
| LawFirm-os-semantic-substrate | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-semantic-substrate | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-semantic-substrate | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-semantic-substrate | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| LawFirm-os-semantic-substrate | duplicate-ignore | Duplicate/reference/temp path marker or duplicate basename without policy. | Keep central record only; avoid mailbox delivery. |
| LawFirm-os-skills-registry | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
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
| synthetic-public-backfill | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-backfill | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-backfill | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-clean | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-clean | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-clean | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-confirmed-backfill | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-confirmed-backfill | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-confirmed-backfill | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-demo-case-small-sample | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-demo-case-small-sample | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-demo-case-small-sample | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-hard-review-small-sample | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-hard-review-small-sample | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-hard-review-small-sample | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-invalid-fix | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-invalid-fix | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-invalid-fix | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-mixed | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-mixed | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-mixed | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-semantic-lineage-small-sample | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-semantic-lineage-small-sample | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-semantic-lineage-small-sample | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-small-sample | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-small-sample | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-public-small-sample | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-unknown-origin | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-unknown-origin | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| synthetic-unknown-origin | duplicate-ignore | Duplicate DAD contract repo_id appears in more than one local repo path. | Review lineage before choosing one canonical enrolled repo. |
| talent-intelligence-clean-20260618 | duplicate-ignore | Nested Git repo discovered inside another local Git root. | Review nested repo lineage before enrollment or delivery. |
| 00_LawFirm_OS | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| 04_Digital_Assett_Directory | needs-human-classification | Existing DAD contract found without reviewed policy match. | Reconcile the existing contract into reviewed policy before updates. |
| airca-fractal-decision-architecture | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| fmg-fractal-capability-ontology | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| fmg-fractal-capability-ontology-pinned | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| kirsten-dissertation-knowledge-graph | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| logos-boundary-literature | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| lowell-career-os | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| lowelltwong-alt | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| Mock Trial4.26 | needs-human-classification | Mock Trial/Albert marker; not Logos-protected by default. | Treat as an active normal repo unless policy says otherwise. |
| noesis-atlas | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| orphan-radar | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| powerbi_claim_finance_ai_seed_project_v3 | needs-human-classification | No reviewed policy or special classification marker. | Add to reviewed policy or explicitly ignore before DAD delivery/enrollment. |
| logos-governance-architecture | protected-central-only | Logos repo marker requires protected central-only handling. | Require explicit Logos local-write approval before any repair or enrollment write. |
| logos-governance-architecture | protected-central-only | Logos repo marker requires protected central-only handling. | Require explicit Logos local-write approval before any repair or enrollment write. |
| logos-scripture-graph-repo | protected-central-only | Logos repo marker requires protected central-only handling. | Require explicit Logos local-write approval before any repair or enrollment write. |

## GitHub Sources

Coverage status: `configured_disabled`

- github-lowelltwong-alt (lowelltwong-alt): configured_source_only (0 rows)
