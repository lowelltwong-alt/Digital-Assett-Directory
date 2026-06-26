# Phase 5 Alerting And Research Radar Evidence

Status: complete under a conservative manual/local-only alerting and research
radar boundary.

Date: 2026-06-26

## Boundary Decision

Phase 5 does not approve scheduled scans, external missing-part research
automation, GitHub scanning, notification delivery, external code import, or
autonomous promotion.

The approved Phase 5 surface is:

- manual local CLI runs;
- generated local reports under `processed/`;
- generated candidate records under ignored processed paths;
- human review before any source mutation, code reuse, alert-channel expansion,
  or roadmap consequence.

Any later email/Slack/GitHub notification channel, scheduled scan, external
search provider, or autonomous research worker remains a new human gate.

## Gate Coverage

| Gate | Status | Evidence |
|---|---|---|
| `phase-5-alert-channels-approved` | Verified for local generated reports only | `roadmap/evidence/background-connection-radar-v1-implementation.md`, `docs/BACKGROUND_CONNECTION_RADAR.md`, `src/digital_asset_directory/readiness.py` |
| `phase-5-rate-limits-source-terms-reviewed` | Verified for zero scheduled external calls and source-terms gates before future external research | `docs/SECURITY_AND_PRIVACY.md`, `docs/PUBLIC_SAFE_SOURCE_SWEEPS.md`, `docs/DATA_FLOW.md` |
| `phase-5-external-code-review-gates-active` | Verified | `AGENTS.md`, `registry/design-authority.json`, `docs/SECURITY_AND_PRIVACY.md`, `docs/SOFTWARE_REPO_CHECKLIST_TREE.md` |
| `phase-5-no-autonomous-merge-promotion` | Verified | `AGENTS.md`, `AI_FRONT_DOOR.md`, `docs/ROADMAP_EXECUTION.md`, `roadmap/evidence/background-connection-radar-v1-implementation.md` |

## Implemented Manual Radar

The manual Background Connection Radar v1 is the Phase 5 local radar slice.

Command:

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli recommend background-connections --attention recent --cold older --limit 50 --escalation-budget 5 --tau 0.70 --max-hops 2 --reserve-cold 2
```

Recorded behavior:

- reads the existing catalog and graph outputs only;
- does not rescan local sources;
- does not call GitHub;
- does not call external models;
- does not run as a daemon;
- does not mutate scanned source repositories;
- writes generated outputs under `processed/`;
- uses gate-before-score escalation with safety, evidence, and authority gates.

The real-catalog smoke run produced many generated candidates but zero
escalation packets at `tau=0.70`, which is an acceptable conservative result.
The threshold should be calibrated later rather than weakened during roadmap
closure.

## Alert Channel Decision

Approved alert channel for this phase:

```text
manual CLI command -> processed generated report -> human review
```

Not approved:

- email, Slack, desktop, or webhook delivery;
- scheduled scans;
- scheduled external research;
- GitHub issue/PR creation;
- automatic graph promotion;
- automatic score changes.

## Source Terms And Rate Limits

Because external research automation is not enabled, the active external rate
limit is effectively zero scheduled external calls. Future external research
must record:

- query and source;
- license or source terms;
- provenance;
- freshness;
- security and compatibility review;
- review status.

Public-safe source sweeps remain the default for mixed private/public workflow
folders. Row-level private data, scraped people data, generated exports, source
snapshots, and sensitive files remain out of tracked public-ready evidence.

## External Code And Promotion Controls

External code cannot be merged or reused merely because a radar, proposal, or
research command finds it. Review must cover license, provenance, security,
compatibility, source authority, and human approval.

Generated candidates cannot:

- mutate source repos;
- mark roadmap phases complete by themselves;
- rewrite source truth;
- auto-merge;
- become reviewed graph truth without a separate review decision.

## Red-Team And Premortem

Failure mode: future agents treat "alert channel approved" as permission to
start scheduled notifications.

Mitigation: the only approved channel is local generated reports. New delivery
channels require a new human gate.

Failure mode: external research quietly expands into network scraping or
GitHub scanning.

Mitigation: the active rate limit is zero scheduled external calls, GitHub
scanning remains deferred, and external research must record source terms and
review status.

Failure mode: a high-scoring candidate connection causes source mutation or
code import.

Mitigation: candidate records are ignored generated outputs, gate-before-score
blocks unsafe escalation, and external code review gates remain active.

Failure mode: alerts become noise or repeat stale/duplicate families.

Mitigation: radar v1 dedupes by endpoint family before budget allocation and
uses cold reserve plus hard compute caps.

## Result

Phase 5 is complete as a manual local radar and generated-report alert boundary.
It does not authorize scheduled scans, external research automation, external
notifications, GitHub scanning, external code import, or autonomous promotion.
