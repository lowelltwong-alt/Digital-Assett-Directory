# Public-Safe Mail Completion Audit

Date: 2026-06-30

Status: implemented and verified against the public-safe mail provenance plan
and the fresh-eyes red-team findings. DAD mail remains candidate-only transport.
Mailbox JSONL is operational state, not source authority.

## Plan Requirements

| Requirement | Current evidence | Status |
| --- | --- | --- |
| Mail records carry source provenance and public release envelopes. | `MailMessageRecord.source_provenance`, `MailMessageRecord.public_release`, and `schemas/mail-message.schema.json`. | Done |
| Reviewed mail repo policy defines canonical path, alias, visibility, public-facing status, mail enablement, and delivery permission. | `MailRepoPolicy`, `load_config()`, `config/sources.example.yaml`, and active local `config/sources.local.yaml`. | Done |
| `--repo all` uses reviewed policy, not dynamic discovery. | `_discover_mail_repos()` returns only enabled `cfg.mail_repos`; `mail discover-repos` is read-only. | Done |
| Private, internal, restricted, or unknown origins to public-facing targets require human release. | `_public_release_envelope()`, `release_mail()`, `deliver_mail()`, and tests for private-to-public hold/approve/reject. | Done |
| Agent review is triage and does not satisfy human release. | `MailDecisionRecord.decision_actor_type`, `human_verified`, `review_status`, and digest tests. | Done |
| Sensitive content screening covers credentials and likely PII without claiming proof of safety. | Expanded `SECRET_PATTERNS`; docs call this best-effort credential/PII screening. | Done |
| Public-facing delivery allows only short metadata-like content. | `_public_payload_violations()` checks payload, evidence, and suggested actions. | Done |
| Malformed JSONL is quarantined while valid rows continue. | `_read_jsonl_with_errors()`, `_quarantine_jsonl_errors()`, malformed-row tests. | Done |
| Invalid UTF-8 does not break digest. | Byte-level JSONL parsing and invalid-UTF-8 digest regression test. | Done |
| Stale locks recover and active locks are reported per record. | `_jsonl_lock()` plus stale/active lock tests. | Done |
| Central quarantine/release logs and mail reports summarize holds and private-origin packets. | `processed/mail/quarantine/`, `processed/mail/releases/`, `write_mail_center_report()`. | Done |
| Repo-local mailbox files stay lightweight and candidate-only. | `mail_readme_text()`, `.digital-asset/mail/.gitignore`, downstream template updates. | Done |

## Red-Team Findings

| Finding | Resolution evidence | Status |
| --- | --- | --- |
| Source-authored `public_release` could spoof human approval. | `_public_release_envelope()` no longer preserves incoming approved/rejected status; approval is applied only from `_release_decisions()`. Regression: `test_source_authored_public_release_approval_is_not_trusted`. | Fixed |
| Explicit `--repo` delivery bypassed reviewed target policy. | CLI calls `deliver_mail(..., require_target_policy=True)`. Regression: `test_strict_delivery_requires_reviewed_target_policy_for_explicit_paths`. | Fixed |
| Public-safe screening ignored evidence and suggested actions. | `_public_payload_violations()` checks payload, evidence, and suggested actions. Regression: `test_public_safe_payload_policy_rejects_raw_evidence_to_public_target`. | Fixed |
| Agent triage could block later human review for the same decision. | Decision IDs include actor type. Regression: `test_agent_review_is_triage_not_human_review`. | Fixed |
| Invalid UTF-8 JSONL crashed digest. | `_read_jsonl_with_errors()` reads bytes and records invalid UTF-8 warnings by hash. Regression: `test_digest_tolerates_invalid_utf8_rows_and_updates_last_checked`. | Fixed |

## Live Test Evidence

- Logos Scripture Graph received a `workflow_suggestion` about a Rust
  first-pass/shadow layer after a public-release hold and explicit human
  release.
- Mock Trial 4.26 received a `governance_notice` about mail behavior during
  repo rename, split, or copy.
- Active local `config/sources.local.yaml` now includes reviewed mail entries
  for DAD, Logos Scripture Graph, and Mock Trial 4.26.

## Verification

- `python -m pytest tests\test_mail_center.py -q`: 31 passed.
- `python -m pytest`: 305 passed after the final discovery regression.
- `python -m digital_asset_directory.cli validate`: valid.
- `python -m digital_asset_directory.cli templates validate`: valid.
- `python -m digital_asset_directory.cli roadmap check --no-update`: passed.
- `python -m ruff check ...`: passed for focused files.

## Remaining Operational Notes

- `config/sources.local.yaml` is ignored local policy, not a tracked public
  artifact.
- `docs/TAXONOMY_RECOMMENDATION_INBOX.md` remains an untracked candidate input
  and was not folded into this patch.
- Mail packets are still suggestions only; target repos decide whether to adopt
  anything through their own governance.
