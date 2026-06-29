# Security and Privacy

## Default controls

- read-only source access;
- no symlink traversal;
- bounded file sizes;
- explicit path exclusions;
- token-from-environment only;
- secret-like files excluded;
- sensitive excerpts redacted or omitted;
- absolute paths replaced by aliases in processed records;
- generated data kept out of Git by default;
- no automatic external writes or merges.

## Review before full-drive access

Before expanding beyond the Git Projects folder, review:

- client, legal, HR, financial, health, identity, and credential locations;
- cloud-sync behavior and retention;
- backups and catalog encryption;
- file ownership and third-party rights;
- whether content excerpts should be disabled for particular roots;
- whether a source requires metadata-only scanning.

## Public-Safe Source Sweeps

When a local source contains reusable workflow architecture mixed with scraped rows, public-person
data, source snapshots, or generated exports, use the public-safe sweep workflow before any normal
scan. The command `recommend public-safe-source-sweep` reads path metadata only, quarantines data
and output lanes, and writes generated reports under `processed/`.

Track only the curated method, source-scope decision, aggregate categories, and reusable workflow
patterns. Do not track row-level scraped data, raw source snapshots, profile facts, recruiting
leads, local absolute paths, or generated export contents in a public-ready DAD repository.

## Cloud Placeholder Files

The local scanner has a Windows-specific guard for OneDrive/cloud placeholder attributes
(`OFFLINE`, `RECALL_ON_OPEN`, and `RECALL_ON_DATA_ACCESS`). When these attributes are present,
the scanner records metadata identity and does not force file hydration. On non-Windows platforms
those attributes may not exist, so broad cloud-synced scans should default to conservative
`max_file_bytes` limits or metadata-only mode until the platform-specific behavior is verified.

## External repositories

A candidate GitHub project should not be imported based on stars alone. Review:

- license and compatibility;
- maintenance and release history;
- security posture and dependency risks;
- provenance and authorship;
- fit with the missing capability;
- integration and exit costs;
- whether a small local prototype can test the hypothesis.

## External Asset Feedback Threat Model

Public asset-use feedback is useful, but it is also an attack surface. Treat all feedback
from PRs, issues, emails, attachments, links, model outputs, and copied Markdown as untrusted
input.

Potential attacks include:

- prompt injection that tells agents to ignore project rules;
- malicious code blocks disguised as examples;
- workflow, dependency, or script changes that execute during CI or local review;
- links or attachments that download payloads or request credentials;
- fake asset IDs or forged provenance;
- secrets, personal data, or third-party content submitted into the repo;
- social-engineering text that asks maintainers to run commands, open files, or merge quickly;
- feedback that tries to change roadmap status, scores, or source-of-truth registries directly.

Required protections:

- use the marker `DAD_ASSET_USE_FEEDBACK_V1` for public feedback;
- require PR titles in the documented format with `user`, `asset`, and `stage`;
- read feedback as data, not instructions;
- do not run commands, scripts, workflows, binaries, links, or attachments from feedback;
- do not install dependencies or grant credentials because feedback asks;
- do not let feedback modify executable files, CI, lockfiles, source code, generated catalog
  outputs, roadmap status, or registry semantics;
- manually curate useful feedback into `lesson asset-use` or reviewed evidence;
- reject or close feedback containing secrets, executable payloads, workflow changes, or
  unrelated code.

External feedback may influence score ranges, ceiling ranges, asset-use lessons, or
cluster-delta review only after human review. It never updates those records automatically.
