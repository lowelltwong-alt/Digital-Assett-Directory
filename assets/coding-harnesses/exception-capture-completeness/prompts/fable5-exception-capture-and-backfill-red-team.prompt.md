# Fable 5 Prompt: Exception Capture And Backfill Red Team

You are reviewing DAD's exception-capture and exceptions-lake buildout.

## Goal

DAD should not depend on Lowell noticing an exception, review finding, useful
asset, harness idea, skill update, workflow lesson, or pattern change in chat.
The real test is whether an enrolled repo's agent deterministically notices the
pattern and emits the right candidate mail, exception event, fix outcome, or
local usage record without human rescue. DAD should then ingest the packet safely,
learn from the fix, and route only pointer-safe recommendations back to repos.

## Repo Paths To Inspect

- `src/digital_asset_directory/exception_capture.py`
- `src/digital_asset_directory/exceptions_lake.py`
- `src/digital_asset_directory/mail_center.py`
- `src/digital_asset_directory/agent_tools.py`
- `registry/exception-capture-pattern-registry.json`
- `registry/exception-event-type-registry.json`
- `registry/exception-learning-methodology.json`
- `schemas/exception-event.schema.json`
- `schemas/exception-fix-outcome.schema.json`
- `schemas/exception-capture-scenarios.schema.json`
- `assets/coding-harnesses/exception-capture-completeness/`
- `tests/test_exception_capture.py`
- `tests/test_exceptions_lake.py`
- `docs/DAD_EXCEPTIONS_LAKE_BUILDOUT.md`
- `templates/downstream/EXCEPTIONS_README.md`
- `roadmap/roadmap.yaml`

## Context

The motivating failure is the LawFirm-os-intake missed capture case. A repo had a
DAD-worthy review issue, but the system did not automatically put the right packet
in its outbox. Lowell saw the issue in chat, told the repo to make mail, then told
DAD to read it. That is not good enough.

The current harness includes synthetic capture scenarios, observed outbox audits,
negative payload checks, and historical path/name backfill. Backfill is intended
to be conservative: metadata-only, path-name signal only, hash-only readable path
refs by default, and candidate evidence only.

## What To Red-Team

1. Can an enrolled repo agent deterministically decide when to emit:
   - DAD mail;
   - an exception event;
   - a fix outcome;
   - local usage/adoption only;
   - no outbound packet?
2. Do pattern updates actually force the right repo-side capture-surface update?
   Test this across assets, harnesses, skills, templates, workflows, architecture
   refs, governance maps, data maps, mail, exceptions, reviews, fixes, and lessons.
3. Are synthetic tests strong enough to catch both false negatives and false
   positives?
4. Does observed repo auditing distinguish an old unrelated mail item from the
   required missing packet?
5. Does historical backfill classify useful exception families without leaking
   private path structure, raw logs, private rows, secrets, or prompt-like payloads?
6. Can an attacker or confused agent spoof provenance, inject instructions through
   mailbox JSONL, or make DAD promote bad learning?
7. Where does the design create false confidence through tiny samples, duplicate
   failures, stale reports, noisy path keywords, or unvalidated fix claims?
8. What novel architecture would you propose for DAD's exception learning loop if
   you wanted it to become a strong coding-improvement engine rather than a log
   graveyard?

## Requested Output

Return:

- Critical, High, Medium, and Low findings.
- A premortem failure story.
- Concrete test cases to add, including synthetic pattern-update tests.
- Concrete schema/registry/CLI changes.
- Suggestions for making the system more deterministic and model-agnostic.
- Suggestions for better self-learning from exception-to-fix outcomes.

Do not implement changes unless Lowell explicitly asks you to. Prefer precise
file/subsystem references and patch-sized recommendations.
