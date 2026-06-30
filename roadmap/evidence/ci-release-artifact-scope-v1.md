# CI And Release Artifact Scope V1

## Summary

This change adds a metadata-only scope command for CI, release, changelog, QA,
build-log, and dependency-manifest artifacts:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend ci-release-scope --limit 200 --per-repo-limit 12
```

The command writes generated outputs only:

```text
processed/reports/ci_release_artifact_scope.md
processed/reports/ci_release_artifact_scope.json
processed/reports/ci_release_artifact_approval_prompt.md
```

## Why

CI and release artifacts can contain high-value lessons about validation order,
late stabilizers, repeated failures, dependency changes, compatibility promises,
and release gates. They are also noisy and can contain sensitive text. DAD needs
a scope-and-approval layer before any content read.

## Boundaries

- Uses existing catalog metadata and logical paths only.
- Does not read source file contents.
- Does not recurse through source filesystems.
- Does not call GitHub, CI services, package registries, models, or embeddings.
- Does not mutate source repositories or install hooks.
- Does not synthesize lessons from artifact content yet.

## Context

Applies when a future agent needs to decide which CI/release artifacts might
contain reusable lessons before requesting a bounded content pass.

Does not apply when the task is to run CI, fetch remote CI logs, or read artifact
content without a separate approval gate.

Danger if misapplied: generated artifact scope can be mistaken for permission to
read logs or release files. It is only routing evidence.

## Red-Team

- False positives: filenames such as `release` or `version` can be unrelated to
  actual release evidence.
- False negatives: CI behavior may live in scripts that do not look like CI
  files from metadata alone.
- Privacy risk: CI logs and artifacts may contain secrets, private paths, or
  external identities.
- Noise risk: generated logs can overwhelm durable lessons unless later
  extraction is capped, redacted, and reviewed.

## Acceptance Status

Implemented as generated candidate infrastructure. No roadmap phase is marked
complete by this evidence.
