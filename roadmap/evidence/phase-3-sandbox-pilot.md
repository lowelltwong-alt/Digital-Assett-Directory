# Phase 3 Sandbox Downstream Governance Pilot

Status: verified for sandbox-only Phase 3 gates.

Date: 2026-06-26

## Scope

Phase 3 was tested in a disposable sandbox repository only:

```text
C:\Users\lowel\AppData\Local\Temp\dad-downstream-pilot-20260626132722
```

No active repository, Mock Trial repository, LawFirm OS repository, Logos
repository, source repository, or GitHub repository was mutated.

The downstream pilot candidate pack was generated first:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend downstream-pilots --limit 10
```

Result:

- repository assets considered: `143`
- candidate repositories: `142`
- active/changing repositories excluded: `1`
- output: `processed/reports/downstream_pilot_candidates.md`

The sandbox was selected instead of any active candidate repository.

## Sandbox Installation

The sandbox was scaffolded through the DAD CLI and wired to the hub:

```powershell
$sandbox = 'C:\Users\lowel\AppData\Local\Temp\dad-downstream-pilot-20260626132722'
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli agent new --repo $sandbox --name "DAD Downstream Pilot" --hub .
git -C $sandbox init
git -C $sandbox config core.hooksPath .githooks
python -m digital_asset_directory.cli agent install-learning-loop --repo $sandbox --mode files-only
```

Created sandbox governance files:

- `README.md`
- `.gitignore`
- `AGENTS.md`
- `CLAUDE.md`
- `.digital-asset-directory.yml`
- `.githooks/pre-push`
- `.githooks/pre-push.ps1`
- `DIGITAL_ASSET_DIRECTORY_HANDOFF.md`
- `.digital-asset-directory/learning/README.md`
- `.digital-asset-directory/learning/context-tags.yaml`
- `.digital-asset-directory/learning/events.jsonl`

`git config core.hooksPath` returned:

```text
.githooks
```

## Learning Loop Events

Four repo-local learning events were captured as data-only JSONL records:

- `before_work`
- `during_failure`
- `after_work`
- `review`

The sandbox event log contains `4` events:

```text
.digital-asset-directory/learning/events.jsonl
```

Every event includes the safety confirmation that it is data only and does not
request code execution, credential access, source mutation, dependency
installation, or automatic promotion.

## Pre-Push Enforcement Review

A sandbox preflight opened a downstream work session:

```powershell
python -m digital_asset_directory.cli agent preflight --repo $sandbox --hub . --agent codex --task "Phase 3 sandbox enforcement test"
```

Session:

```text
dad:session:a9ea2728-e2da-4f2a-933a-6e4cd6b791f5
```

Before postflight, enforcement failed closed:

```powershell
python -m digital_asset_directory.cli agent enforce --repo $sandbox --hub .
```

Result:

```text
exit code: 2
Open AI work session(s) require postflight handoff: dad:session:a9ea2728-e2da-4f2a-933a-6e4cd6b791f5
```

After postflight, enforcement passed:

```powershell
python -m digital_asset_directory.cli agent postflight --session dad:session:a9ea2728-e2da-4f2a-933a-6e4cd6b791f5 --repo $sandbox --hub . --summary "Phase 3 sandbox enforcement test completed; postflight clears pre-push gate."
python -m digital_asset_directory.cli agent enforce --repo $sandbox --hub .
```

Result:

```text
exit code: 0
No open Digital Asset Directory agent sessions for this repository.
```

## Lessons Arrive In Central Hub

The sandbox postflight wrote a central hub handoff and lesson:

```text
handoff_id: dad:handoff:b4167661-497c-52f8-9359-3a5b25cecb07
lesson_id: dad:lesson:053149a2-2a2e-51a8-accc-c5a8e9ddabfe
```

Lesson routes were rebuilt:

```powershell
python -m digital_asset_directory.cli lesson reindex --hub .
```

Result:

```text
lessons_indexed: 100
by_repo_dir: raw/lessons/by-repo
by_capability_dir: raw/lessons/by-capability
```

## Bypass And Failure Behavior

Tested failure mode:

- Open AI work session exists in the sandbox.
- Enforcement blocks push/enforce path until postflight exists.

Reviewed bypass policy:

- `docs/DOWNSTREAM_REPO_GOVERNANCE.md` says emergency bypass must be explicit,
  logged, and reviewed.
- This pilot did not silently disable hooks.
- The sandbox kept `core.hooksPath=.githooks`.

## Risk-Tier And Context Bounds

Risk tier: high.

Reason: downstream governance hooks and roadmap gate evidence can affect future
agent behavior and downstream repositories.

Mitigations:

- sandbox-only pilot;
- no active repo mutation;
- no GitHub scanning;
- no generated candidate promoted to source truth;
- explicit preflight/midflight/postflight;
- enforcement tested both before and after postflight;
- bypass policy recorded;
- fresh-eyes Claude review requested before treating this as robust.

Applies when:

- testing DAD downstream governance in a disposable sandbox;
- proving that preflight/postflight enforcement blocks and clears correctly;
- proving files-only repo learning events can be captured as data.

Does not apply when:

- selecting an active downstream production pilot;
- installing hooks in Mock Trial, LawFirm OS, Logos, or other active repos;
- claiming all downstream repos are ready;
- bypassing the human gate for future active repo installation.

Danger if misapplied:

- sandbox success could be overgeneralized to active repositories;
- temp sandbox files could be mistaken for canonical portfolio assets;
- hooks could be installed too broadly without human pilot selection.

## Gate Mapping

- `phase-3-pilot-repositories-selected`: verified by selecting the disposable
  sandbox path instead of an active repo.
- `phase-3-pre-push-enforcement-reviewed`: verified by enforcement failing
  before postflight and passing after postflight.
- `phase-3-lessons-arrive-central-hub`: verified by central handoff and lesson
  IDs plus lesson route reindex.
- `phase-3-bypass-failure-tested`: verified by fail-closed enforcement behavior
  and reviewed bypass policy.

## Claude Fresh-Eyes Prompt

Use this prompt to have Claude red-team this phase before using Phase 3 outside
the sandbox:

```text
You are doing a fresh-eyes red-team review of Phase 3 downstream governance for
the Digital Asset Directory repo at:
C:\Users\lowel\OneDrive\Desktop\Git Projects\04_Digital_Assett_Directory

Read first:
1. AGENTS.md
2. AI_FRONT_DOOR.md
3. MACHINE_NAVIGATION_MANIFEST.json
4. roadmap/roadmap.yaml
5. roadmap/gate-evidence.json
6. docs/DOWNSTREAM_REPO_GOVERNANCE.md
7. docs/LOAD_BEARING_DECISION_REVIEW.md
8. roadmap/evidence/phase-3-sandbox-pilot.md

Task:
Red-team whether Phase 3 was correctly verified as sandbox-only downstream
governance evidence. Check the gate logic, commands, enforcement behavior,
learning-loop capture, central lesson/handoff evidence, bypass policy, and
whether the evidence is overclaiming anything.

Pay special attention to:
- Did Codex mutate only the temp sandbox and not active repos?
- Is the pilot selection gate valid when the selected repo is disposable?
- Did pre-push enforcement actually fail closed before postflight and pass after?
- Did lessons/handoffs arrive in the central hub, or only repo-local event files?
- Are repo-local events safely data-only?
- Is any generated output being treated as source truth?
- Is gate-evidence.json too permissive or correctly scoped?
- Should Phase 3 be marked complete, or only sandbox-pilot verified?
- What false positives, false negatives, missing tests, or hidden risks remain?
- What would you require before installing governance into an active repo?

Output a report with:
1. Verdict: pass / conditional / fail.
2. Findings ordered by severity with file/line references where possible.
3. Any gate that should not be considered verified.
4. Any missing validation command or evidence.
5. Premortem: how this could fail when moved from sandbox to active repos.
6. Recommended fixes before active-pilot installation.
7. Whether you agree with the current Phase 3 scope and gate records.

Do not edit files unless explicitly asked. Do not mutate active repos. Do not
run GitHub scans. Treat the sandbox path as disposable evidence, not portfolio
truth.
```
