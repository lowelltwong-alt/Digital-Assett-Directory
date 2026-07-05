# Codex Delegation Template

Use this when Fable finds an issue that Codex should implement.

```json
{
  "delegation_id": "dad:fable-delegation:<short-id>",
  "severity": "critical|high|medium|low",
  "owner": "codex",
  "issue": "",
  "why_it_matters": "",
  "evidence_paths": [],
  "suggested_files_to_edit": [],
  "patch_hint": "",
  "tests_to_add_or_update": [],
  "validation_commands": [],
  "must_not_change": [],
  "fable_fix_dependency": "",
  "risk_if_skipped": ""
}
```

Rules:

- Keep each delegation small and independently testable.
- Include exact paths and expected behavior.
- State how the Codex fix should respect any Fable-authored architecture or
  algorithm change.
- Never ask Codex to copy private content, bypass public-release gates, or
  mutate protected repos without approval.
