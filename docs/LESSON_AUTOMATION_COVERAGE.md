# Lesson Automation Coverage

This report path exists so future agents can start with what has not been scanned
or instrumented yet, instead of repeating broad passes.

## Command

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-coverage --limit 50
```

The command writes generated candidate outputs only:

```text
processed/reports/lesson_automation_coverage.md
processed/reports/lesson_automation_coverage.json
processed/reports/scan_coverage_cycle.md
processed/reports/scan_coverage_cycle.json
processed/learning/scan_cycle_events.jsonl
```

## What It Checks

- current catalog assets and repository boundaries;
- latest scan summary metadata;
- local and GitHub source configuration metadata;
- presence of generated reports that indicate prior signal-family work;
- repo-level surfaces visible in the catalog, such as AI front doors, TOCs,
  learning-loop files, and governance dependency maps.

## What It Does Not Check

- source file contents;
- fresh filesystem recursion;
- GitHub PR or issue APIs;
- CI logs or remote artifacts;
- model or embedding calls;
- downstream repo writes.

## Scan-Cycle Log

`processed/reports/scan_coverage_cycle.md` is the handoff surface for the next
agent. It records:

- what this pass checked;
- what was intentionally skipped;
- which signal families are next in the cycle;
- which next steps require human approval;
- stop conditions for broad scans, external APIs, and downstream repo mutation.

`processed/learning/scan_cycle_events.jsonl` is the append-only generated event
trail. It records each coverage run as a `ScanCycleEventRecord`, including the
checked inputs, intentionally skipped inputs, signal-family statuses,
recommended next signal families, gated families, and context boundaries.

Use the log as a routing aid, not as proof that a repo has no value. A missing
surface means DAD has not observed it yet.

## Repo Completion Dashboard

After scope reports exist, generate the per-repo blocker view:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend repo-completion-dashboard --limit 100
```

This writes:

```text
processed/reports/repo_completion_dashboard.md
processed/reports/repo_completion_dashboard.json
```

The dashboard reports deterministic status labels for each cataloged repo, such
as `blocked_by_content_read_gate`, `blocked_by_source_repo_governance_gate`, or
`metadata_completion_ready_for_human_review`. It uses observed catalog surfaces
and generated scope/decision outputs only. It does not read source content,
approve decisions, install learning loops, write governance maps, call GitHub,
call models, or mark phases complete.

Generate the ordered wave plan after the dashboard:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend repo-completion-waves --dashboard-limit 500 --per-wave-repo-limit 25
```

This writes:

```text
processed/reports/repo_completion_wave_plan.md
processed/reports/repo_completion_wave_plan.json
```

The wave plan turns blocker labels into an execution order with proof gates:
content-read approval, lesson synthesis, repo learning-loop installation,
governance-map adoption, AI navigation and validation review, then final
metadata-ready human review. It is still generated guidance only.

## Next-Action Queue

After scope reports exist, generate one consolidated queue before choosing the
next human-gated action:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-next-actions --limit 25
```

This writes:

```text
processed/reports/lesson_automation_next_actions.md
processed/reports/lesson_automation_next_actions.json
processed/reports/lesson_automation_next_actions_approval_prompt.md
```

The queue reads only generated scope reports and `scan_coverage_cycle.json`. It
does not rescan, read source file contents, call GitHub, call models, mutate
source repos, install hooks, or mark roadmap phases complete.

It uses this review-routing formula:

```text
priority_score = 100 * (0.30*scope_readiness + 0.25*lesson_yield + 0.20*safety_margin + 0.15*approval_specificity + 0.10*cycle_urgency)
```

The score is only a way to order human review. It does not authorize content
reads, API calls, source-repo file writes, governance adoption, or promotion.

## Decision Template

Before running a gated action from the next-action queue, create or inspect the
decision template:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-decision-template --limit 25
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-decision-queue --status pending --limit 10
```

This writes:

```text
processed/learning/lesson_automation_action_decisions.jsonl
processed/reports/lesson_automation_decision_template.md
processed/reports/lesson_automation_decision_template.json
```

Pending rows are not approvals. Apply a decision only after Lowell has approved
the exact action and scope:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-decision-label `
  --sample-id lesson-automation-decision-001 `
  --reviewer Lowell `
  --decision approve `
  --approval-id "<human-approval-id>" `
  --repo-key "<approved-repo-key>" `
  --category "<approved-category>" `
  --allow-content-read `
  --max-bytes-per-file 20000 `
  --max-files 10 `
  --rationale "<why this bounded action is approved>"
```

The label command fails closed:

- content-read approvals require `--allow-content-read`, positive byte/file
  caps, a repo/category/path selector, and redaction;
- source-repo write approvals require `--allow-source-mutation` plus a repo
  selector;
- external API approvals require `--allow-external-api`,
  `--token-scope-note`, and `--privacy-boundary-note`;
- model-call approvals require `--allow-model-call` and a privacy-boundary
  note;
- defer/reject decisions require rationale or notes.

## Approval Packet

Before applying any pending decision label, generate the approval packet:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-approval-packet
```

This writes:

```text
processed/reports/lesson_automation_approval_packet.md
processed/reports/lesson_automation_approval_packet.json
```

The packet prepares exact `lesson-automation-decision-label` commands for human
review. It does not apply labels, approve rows, execute commands, read source
contents, mutate source repos, call GitHub, call models, or mark roadmap phases
complete.

The default recommendation is conservative: bounded content extraction can be
suggested for approval when a generated scope exists, while source-repo writes,
governance adoption, external APIs, and missing extractors are suggested for
deferral unless Lowell explicitly chooses exact scope and permissions.

## Execution Plan

After one or more decision rows are reviewed and approved, generate the
execution plan:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-execution-plan
```

This writes:

```text
processed/reports/lesson_automation_execution_plan.md
processed/reports/lesson_automation_execution_plan.json
```

The plan does not execute commands. It converts reviewed `approve` rows into
exact command text or manual source-repo next steps, and reports zero runnable
entries while all decisions remain pending, deferred, or rejected.

For `priority_content_extracts`, the plan can produce a bounded
`priority-content-extract` command using only the approved repo keys,
categories, approval id, scope file, byte cap, and file cap from the decision
record. For source-repo writes or governance-map adoption, it keeps the work as
manual next steps unless the approved decision supplies exact repo paths and
mutation permission.

## Context Boundaries

Applies when:

- an agent is choosing the next repo or signal family to inspect;
- the user wants new work to begin with unscanned or uninstrumented areas;
- a future task needs to avoid redoing broad scans.

Does not apply when:

- the user explicitly authorizes a fresh broad source scan;
- a target repo is outside the approved source scope;
- the job is to inspect one named repo directly.

Danger if misapplied:

- generated gaps can be mistaken for negative evidence;
- a future agent may install learning-loop files without per-repo approval;
- metadata-only evidence may hide existing docs, tests, or governance files.

## Review Cycle

Default order:

1. catalog metadata and repo boundaries;
2. priority content extracts for approved front doors, schemas, docs, tests, and
   governance files;
3. repo-local learning events;
4. cross-repo governance maps and mirrors;
5. bounded local git history and worktree archaeology;
6. CI logs, release notes, and changelogs;
7. GitHub PR, issue, and review metadata;
8. private-source workflow sweeps without row import.

Each step remains gated by source scope, privacy, and mutation rules.

## Repo Learning Loop Install Scope

Before installing repo-local learning files into any source repo, generate a
selection and approval scope:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend repo-learning-loop-scope --limit 50
```

This writes:

```text
processed/reports/repo_learning_loop_install_scope.md
processed/reports/repo_learning_loop_install_scope.json
processed/reports/repo_learning_loop_install_approval_prompt.md
```

The command does not install anything. It ranks candidate repos using:

```text
priority_score = 100 * (0.35*learning_gap + 0.20*ai_navigation_readiness + 0.15*validation_readiness + 0.15*governance_readiness + 0.10*configured_source_path + 0.05*low_noise_bonus)
```

The score is only review routing. It does not prove repo value or authorize
mutation.

After this scope exists, `recommend lesson-automation-coverage` marks
`repo_learning_events` as `installation_scope_ready`. A later installation still
requires explicit repo selection and uses files-only mode:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli agent install-learning-loop --repo "<repo-path>" --mode files-only
```

## Governance Map Adoption Scope

Before writing governance dependency maps, child mirrors, validators, tests, or
PR disclosure sections into source repos, generate a metadata-only approval
scope:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend governance-map-scope --limit 50
```

This writes:

```text
processed/reports/governance_map_adoption_scope.md
processed/reports/governance_map_adoption_scope.json
processed/reports/governance_map_adoption_approval_prompt.md
```

The command does not install the cross-repo governance dependency-map template,
read source file contents, recurse through source filesystems, call GitHub, call
models, or mutate source repos. It only ranks candidate repos and families from
cataloged logical paths and existing generated metadata.

It uses this review-routing formula:

```text
priority_score = 100 * (0.25*family_size_signal + 0.25*governance_gap + 0.20*downstream_likelihood + 0.15*ai_navigation_readiness + 0.10*validation_readiness + 0.05*configured_source_path)
```

The score does not prove authority, value, or approval. After this scope exists,
`recommend lesson-automation-coverage` marks `governance_map_adoption` as
`adoption_scope_ready` unless maps or mirrors are already observed.

## CI And Release Artifact Scope

Before reading CI logs, release notes, changelogs, QA reports, dependency locks,
or build artifacts, generate a metadata-only approval scope:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend ci-release-scope --limit 200 --per-repo-limit 12
```

This writes:

```text
processed/reports/ci_release_artifact_scope.md
processed/reports/ci_release_artifact_scope.json
processed/reports/ci_release_artifact_approval_prompt.md
```

The command does not read artifact contents, recurse through source
filesystems, call GitHub, call CI services, call models, or mutate source repos.
It only lists candidate artifacts already present in the catalog:

- CI workflow configuration;
- release notes and changelogs;
- QA, validation, and verification reports;
- build and test log artifacts;
- dependency lock and version manifests.

After this scope exists, `recommend lesson-automation-coverage` marks
`ci_and_release_artifacts` as `scoped_not_extracted`. A later content pass still
requires human approval, byte caps, secret redaction, and generated-output-only
storage.

## Priority Content Scope

Before a bounded content extract pass, generate an approval scope from catalog
metadata:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-scope --limit 200 --per-repo-limit 12
```

This writes:

```text
processed/reports/priority_content_extract_scope.md
processed/reports/priority_content_extract_scope.json
processed/reports/priority_content_extract_approval_prompt.md
```

The scope command still does not read source file contents. It only lists
candidate paths already present in the catalog and classifies them into
human-review categories:

- AI navigation and repo contracts;
- schemas, contracts, and registries;
- validators, tests, and quality gates;
- governance, security, and privacy boundaries;
- learning loops and pay-forward surfaces;
- workflows, dataflow, and normalization.

After this scope exists, `recommend lesson-automation-coverage` marks
`priority_content_extracts` as `scoped_not_extracted`. Human approval is still
required before any content is read.

## Bounded Priority Content Extract

After human approval, use the fail-closed extractor:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-extract `
  --approval-id "<human-approval-id>" `
  --repo-key "git-projects/00_lawfirm_os/lawfirm-os-orchestrator" `
  --category ai_navigation `
  --category schemas_contracts `
  --max-bytes-per-file 20000 `
  --limit 50
```

The extractor refuses to run without:

- an approval id;
- at least one repo key;
- at least one category;
- a positive byte cap.

It writes generated outputs only:

```text
processed/learning/priority_content_observations.jsonl
processed/reports/priority_content_extract_report.md
processed/reports/priority_content_extract_report.json
```

The extractor reads only candidate paths from the generated scope file, resolves
them under configured local source roots, caps bytes per file, redacts
secret-like text, and keeps all observations as `generated_candidate` evidence.
After observations exist, `recommend lesson-automation-coverage` marks
`priority_content_extracts` as `extracted_candidate_observations_present`.

## Priority Content Lesson Candidates

After generated observations exist, synthesize context-bound lesson candidates:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-lessons --min-observations 1 --limit 100
```

This writes:

```text
processed/learning/priority_content_lesson_candidates.jsonl
processed/reports/priority_content_lesson_candidates.md
processed/reports/priority_content_lesson_candidates.json
```

The synthesis command consumes generated observations only. It does not read
source repos. Every candidate uses the existing `CounterfactualLessonRecord`
contract and must include:

- `applies_when`;
- `does_not_apply_when`;
- `danger_if_misapplied`;
- `counterfactual_better_order`;
- `source_events`;
- `context_tags`;
- `review_status="generated_candidate"`.

After lesson candidates exist, `recommend lesson-automation-coverage` marks
`priority_content_extracts` as `lesson_candidates_synthesized`. Human review is
still required before any candidate becomes a deterministic learning rule or
preflight default.

## Priority Content Lesson Review

Generate a human review template:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-lesson-review-template --sample-size 100
```

Review candidates in small batches:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-lesson-review-queue --status pending --limit 10
```

Apply only human-approved labels:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-lesson-review-label `
  --sample-id priority-content-lesson-review-001 `
  --reviewer Lowell `
  --applicability valid_context `
  --usefulness useful `
  --safety safe `
  --actionability actionable `
  --decision accept_for_review_use `
  --promotion-blocker-note "Needs separate promotion gate."
```

Summarize without promotion:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-lesson-review-summary
```

Review labels are not deterministic learning rules. The promotion gate remains
separate and must not silently convert accepted review-use examples into
preflight defaults.

## Learning Rule Promotion Candidates

After priority content lesson candidates have been reviewed, package accepted
review-use labels into generated promotion candidates:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-lesson-promotion-candidates --limit 100
```

This writes:

```text
processed/learning/learning_rule_promotion_candidates.jsonl
processed/reports/learning_rule_promotion_candidates.md
processed/reports/learning_rule_promotion_candidates.json
```

Promotion candidates are still not reviewed learning rules. They carry a
proposed `LearningRuleRecord`, blockers, required human gates, and
`registry_mutated=false`. A separate human-approved registry edit is required
before any candidate can affect preflight or midflight behavior.
