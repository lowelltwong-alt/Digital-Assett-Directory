# Template Library Governance

Status: tracked template registry plus deterministic dependency checks.

DAD templates are reusable architecture assets. They can seed front doors,
checklists, governance blocks, handoffs, lessons, feedback, and downstream repo
scaffolds. They are not just files; each registered template must declare what it
depends on and what depends on it.

## Command

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli templates check
```

The command validates `registry/template-registry.json` and writes:

```text
processed/reports/template_library.md
processed/reports/template_library.json
```

## Deterministic Enforcement

Validation checks:

- registered template paths exist;
- template IDs are unique;
- direct template dependencies reference registered templates;
- declared `dependent_template_ids` match computed reverse dependencies;
- template-to-contract dependency paths are reported when missing;
- review-due dates are surfaced in the generated report.

## Upgrade Boundary

Template improvement starts as review guidance. A template can recommend an
upgrade, but DAD must not silently rewrite templates or downstream repos.

Allowed v1 behavior:

- detect stale templates by `next_review_due_at`;
- show direct and reverse dependencies;
- list contracts that should trigger review;
- produce generated update-review reports;
- fail validation on broken template graph metadata.

Deferred behavior:

- scheduled automatic patching;
- cross-repo template propagation;
- downstream repo rewrites;
- hook updates without explicit human approval.

## Dependency Model

Template records track:

- template-to-template dependencies;
- reverse dependents, enforced against computed dependencies;
- docs, schemas, registries, scripts, or rules the template relies on;
- upgrade triggers;
- review cadence;
- update policy;
- validation commands.

This lets future agents ask both questions:

- "What does this template depend on?"
- "What will be affected if this template changes?"
