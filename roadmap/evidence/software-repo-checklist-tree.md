# Software And Repo Checklist Tree Evidence

Status: curated evidence for a reusable workflow asset.

## Decision

Create a compositional checklist tree for software, repository, data, workflow, scoring,
governance, source-scan, and release work.

This records the user's requirement that future agents remember:

- data normalization rules;
- high-risk areas that need closer human review;
- when self red-team, fresh-eyes review, premortem, and A/B comparison are required;
- how these checks combine when a task belongs to multiple categories;
- how to avoid making every small edit overly burdensome.

## Created Assets

- `docs/SOFTWARE_REPO_CHECKLIST_TREE.md`
- `templates/software-repo-checklist-tree.template.md`
- asset pattern: `software_repo_checklist_tree_system`
- reviewed learning rule: `learning-rule:software-repo-work-uses-checklist-tree`

## Intended Use

Future agents should classify task dimensions first, then apply the relevant checklist
branches:

```text
task dimensions + risk tier -> selected checklist branches -> validation + review evidence
```

This is not a replacement for existing rules. It composes:

- `docs/LOAD_BEARING_DECISION_REVIEW.md`;
- `docs/ASSET_USE_PAY_FORWARD_LOOP.md`;
- `docs/DETERMINISTIC_LEARNING_RULES.md`;
- source authority and generated-candidate boundaries.

## Safety Boundary

The checklist tree guides review and implementation. It does not promote generated evidence to
truth, authorize source mutation, remove human gates, or prove that an approach is correct.

For low-risk work, agents should keep the checklist short. For high-risk work, agents should
surface human attention, fresh-eyes review, premortem, rollback, validation, and bounded A/B
comparison when feasible.
