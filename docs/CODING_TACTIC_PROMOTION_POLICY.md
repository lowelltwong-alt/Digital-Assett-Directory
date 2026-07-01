# Coding Tactic Promotion Policy

Status: candidate governance policy for moving coding tactics from radar
entries to durable DAD guidance.

## States

`registry/coding-tactics-radar.json` separates:

- `status`: candidate, reviewed, promoted, rejected, deprecated;
- `review_status`: generated_candidate, candidate, reviewed, rejected;
- `promotion_status`: not_promoted, eligible_for_review, promoted_to_profile,
  blocked, rejected.

Generated candidates do not become doctrine because they exist in the radar.

## Promotion Requirements

A tactic can become reviewed guidance only when it has:

- applicability and non-applicability notes;
- danger-if-misapplied notes;
- source evidence;
- minimal example and counterexample paths;
- verification commands;
- at least one observable use or review note, unless it is a security baseline
  sourced from official docs;
- human review when it changes future-agent defaults, public/security posture,
  schemas, templates, or downstream behavior.

## Feedback

Use:

```text
templates/tactic-use-feedback.template.json
schemas/tactic-use-feedback.schema.json
```

Feedback is candidate evidence. It must separate:

- helped because;
- failed because;
- reuse when;
- avoid when;
- evidence;
- safety confirmation.

Do not include secrets, credentials, private rows, or large raw source content.

## Rejection And Deprecation

Reject or deprecate a tactic when:

- it encourages cleverness without clear benefit;
- it conflicts with official language/tool guidance;
- it repeatedly fails local validation;
- it is too broad to apply safely;
- it cannot be verified in target contexts;
- a better tactic replaces it.

## Human Gates

Require human review before promotion when the tactic affects:

- source authority;
- public/private movement;
- security posture;
- CI/hooks/automation;
- shared schemas, registries, or templates;
- route defaults that future agents inherit.
