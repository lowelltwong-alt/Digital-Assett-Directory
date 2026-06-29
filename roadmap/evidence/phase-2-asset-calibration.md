# Phase 2 Asset Calibration Evidence

Human-reviewed asset score calibration evidence. Generated scores remain heuristics and do not become source-repository truth.

- Generated at: `2026-06-25T20:40:09.451932+00:00`
- Source review file: `processed/calibration/asset_rating_template.jsonl`
- Reviewers: Lowell
- Template records: **100**
- Reviewed records: **100**
- Calibration gate complete: **True**
- Score rating counts: `{'about_right': 54, 'too_high': 18, 'too_low': 28}`
- Value band counts: `{'medium': 50, 'low': 50}`
- False positive notes: **18**
- False negative notes: **28**
- Weight change notes: **100**

## Authority Boundary

- Human labels calibrate the catalog scoring model.
- They do not mutate source repositories.
- They do not promote generated metadata, alerts, synergies, or scores to truth.

## False Positive Notes

- `asset-review-003` `dad:asset:fe5c4789-5aed-5d9e-a050-ae4ea25b27be` `bug_report`: False positive: metadata-only/archive/template/pinned or duplicated workflow wrapper received medium from freshness/provenance/type signals without enough direct content, usage, or canonical-source evidence.
- `asset-review-005` `dad:asset:fd8919ff-7f36-5b36-a5d1-e98bffbfd527` `documentation_request`: False positive: metadata-only/archive/template/pinned or duplicated workflow wrapper received medium from freshness/provenance/type signals without enough direct content, usage, or canonical-source evidence.
- `asset-review-012` `dad:asset:fa275343-6814-557f-8831-6203c2880446` `CODEOWNERS`: False positive: metadata-only/archive/template/pinned or duplicated workflow wrapper received medium from freshness/provenance/type signals without enough direct content, usage, or canonical-source evidence.
- `asset-review-016` `dad:asset:f4c0198f-f55b-5540-a179-a3a19b950648` `workflow_escalation_example`: False positive: metadata-only/archive/template/pinned or duplicated workflow wrapper received medium from freshness/provenance/type signals without enough direct content, usage, or canonical-source evidence.
- `asset-review-018` `dad:asset:f2c07ce6-596d-5b74-aeab-c71e5a8baecd` `main-canonical-ruleset`: False positive: metadata-only/archive/template/pinned or duplicated workflow wrapper received medium from freshness/provenance/type signals without enough direct content, usage, or canonical-source evidence.
- `asset-review-023` `dad:asset:f0eb9f24-5a3e-54b4-aa40-d0580dfeaa1e` `repo-drift-check`: False positive: metadata-only/archive/template/pinned or duplicated workflow wrapper received medium from freshness/provenance/type signals without enough direct content, usage, or canonical-source evidence.
- `asset-review-028` `dad:asset:f02c1fdf-d83f-5d77-808c-bf1c142dda31` `validate-external-alignment`: False positive: metadata-only/archive/template/pinned or duplicated workflow wrapper received medium from freshness/provenance/type signals without enough direct content, usage, or canonical-source evidence.
- `asset-review-030` `dad:asset:ef47e9d4-0822-5ec3-b3de-c11afdea4493` `pull_request_template`: False positive: metadata-only/archive/template/pinned or duplicated workflow wrapper received medium from freshness/provenance/type signals without enough direct content, usage, or canonical-source evidence.
- `asset-review-031` `dad:asset:ef1fdff3-e841-56e1-9e0a-f91975257e6e` `validate-talent-intelligence-extension`: False positive: metadata-only/archive/template/pinned or duplicated workflow wrapper received medium from freshness/provenance/type signals without enough direct content, usage, or canonical-source evidence.
- `asset-review-032` `dad:asset:ee3d897a-f95e-57b5-bf36-f19de98983c5` `phase5-validate-object-sets`: False positive: metadata-only/archive/template/pinned or duplicated workflow wrapper received medium from freshness/provenance/type signals without enough direct content, usage, or canonical-source evidence.

## False Negative Notes

- `asset-review-051` `dad:asset:0274ec4a-b4bc-5070-b870-065f19a66409` `cli`: False negative: readable substantive source code stayed low because the calibration sample is metadata-only and did not use code content, module role, tests, or runtime position as direct evidence.
- `asset-review-052` `dad:asset:02a285b9-e4c3-5b9f-ad4e-1262a2c9275d` `grounding`: False negative: readable substantive source code stayed low because the calibration sample is metadata-only and did not use code content, module role, tests, or runtime position as direct evidence.
- `asset-review-053` `dad:asset:08547e7d-c8f8-5e88-9643-aa477d8647cc` `export_schemas`: False negative: readable substantive source code stayed low because the calibration sample is metadata-only and did not use code content, module role, tests, or runtime position as direct evidence.
- `asset-review-054` `dad:asset:0df63828-97ef-5274-b0e5-d1aa74d0bf25` `contract_loader`: False negative: readable substantive source code stayed low because the calibration sample is metadata-only and did not use code content, module role, tests, or runtime position as direct evidence.
- `asset-review-055` `dad:asset:10d89df3-cd2c-5e94-810e-7302f34439ff` `bundle`: False negative: readable substantive source code stayed low because the calibration sample is metadata-only and did not use code content, module role, tests, or runtime position as direct evidence.
- `asset-review-056` `dad:asset:1466a1bc-f36f-5581-b154-abfd765ec270` `registry`: False negative: readable substantive source code stayed low because the calibration sample is metadata-only and did not use code content, module role, tests, or runtime position as direct evidence.
- `asset-review-057` `dad:asset:157dfba5-3ebf-5d36-a8c5-b39c8d7b38c7` `evidence_packet_admission`: False negative: readable substantive source code stayed low because the calibration sample is metadata-only and did not use code content, module role, tests, or runtime position as direct evidence.
- `asset-review-059` `dad:asset:1e74e170-6ac8-5359-bb0a-f93022b2fa3c` `segmenter`: False negative: readable substantive source code stayed low because the calibration sample is metadata-only and did not use code content, module role, tests, or runtime position as direct evidence.
- `asset-review-060` `dad:asset:24409fb4-66bf-5133-9b5f-132764bcfa6c` `admission_validator`: False negative: readable substantive source code stayed low because the calibration sample is metadata-only and did not use code content, module role, tests, or runtime position as direct evidence.
- `asset-review-061` `dad:asset:2548c2cd-be2c-5f5d-a3d9-de59fcc90c5b` `validation_gateway`: False negative: readable substantive source code stayed low because the calibration sample is metadata-only and did not use code content, module role, tests, or runtime position as direct evidence.

## Weight Change Notes

- `asset-review-001` `dad:asset:ff0a3ccc-5588-50ce-9f14-1371e6dad882` `validate-external-alignment`: Keep current band unless future usage, tests, or content extraction show stronger direct current value.
- `asset-review-002` `dad:asset:feccb255-e22a-5bd0-a14d-9723c32fefd3` `shacl`: Keep current band unless future usage, tests, or content extraction show stronger direct current value.
- `asset-review-003` `dad:asset:fe5c4789-5aed-5d9e-a050-ae4ea25b27be` `bug_report`: Reduce medium-band eligibility for metadata-only workflow/template/archive/pinned assets; require extracted content, executed validation evidence, usage evidence, or canonical-source status before freshness/provenance can carry a workflow to medium.
- `asset-review-004` `dad:asset:fda03720-6fdf-5580-a577-9a755a097bde` `phase3-graph-partitions`: Keep current band unless future usage, tests, or content extraction show stronger direct current value.
- `asset-review-005` `dad:asset:fd8919ff-7f36-5b36-a5d1-e98bffbfd527` `documentation_request`: Reduce medium-band eligibility for metadata-only workflow/template/archive/pinned assets; require extracted content, executed validation evidence, usage evidence, or canonical-source status before freshness/provenance can carry a workflow to medium.
- `asset-review-006` `dad:asset:fd013623-7647-5281-aa95-609007524360` `chunking_workflow`: Keep current band unless future usage, tests, or content extraction show stronger direct current value.
- `asset-review-007` `dad:asset:fc8e6d84-d486-59e7-b7a4-e695bed28fff` `validate-talent-intelligence-extension`: Keep current band unless future usage, tests, or content extraction show stronger direct current value.
- `asset-review-008` `dad:asset:fbb1be23-fe86-53db-8918-9d0acfeca282` `main-canonical-ruleset`: Keep current band unless future usage, tests, or content extraction show stronger direct current value.
- `asset-review-009` `dad:asset:fb895ebe-33b8-524e-a048-0e746bbd0d60` `phase3-provenance-minimum`: Keep current band unless future usage, tests, or content extraction show stronger direct current value.
- `asset-review-010` `dad:asset:fa929392-8f78-5ea6-98cc-e96c9764d1bb` `WORKFLOW_ATLAS_BOUNDARY`: Keep current band unless future usage, tests, or content extraction show stronger direct current value.

## Remaining Risks

- Calibration reflects this review set and should be revisited after broader scans.
- GitHub inventory remains deferred until separately approved.
