# Template Library Governance V1 Evidence

Date: 2026-06-29

## Status

Implemented as tracked template metadata plus deterministic validation and
generated reporting.

## What Shipped

- `TemplateRecord` model and JSON Schema.
- `registry/template-registry.json` seed registry.
- `asset-dir templates check` generated dependency/update report.
- `asset-dir templates validate` no-write validation command.
- Main `validate` now checks template path existence, duplicate IDs, missing
  dependencies, and reverse-dependency mismatch.

## Dependency Rule

Every registered template declares:

- `depends_on_template_ids`;
- `dependent_template_ids`;
- `depends_on_contracts`;
- upgrade triggers;
- review cadence;
- deterministic update rule;
- validation commands.

Reverse dependencies are computed and compared to declarations. Broken
dependency metadata is a validation failure.

## Automation Boundary

V1 is recommend-only. DAD may flag due templates and dependency impacts, but it
must not silently rewrite templates, install hooks, or update downstream repos.

Future automatic improvement requires a separate human-approved patcher with:

- rollback;
- fresh-eyes review for load-bearing template changes;
- downstream impact report;
- public/private boundary review;
- tests for each affected template family.

## Reusable Lesson

Templates are architecture assets. They need dependencies in both directions so
future agents can safely answer what a template relies on and what will change
if it is upgraded.
