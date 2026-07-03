# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `LawFirm-os-skills-registry`

| Field | Value |
|---|---|
| Rust status | `medium_high_after_dad` |
| Priority | `5` |
| Plane | skill supply chain / security scanner |
| Confidence | high |
| Risk | medium: rule severity must remain governed; scanner must not approve skills. |

## Why

Static skill scanning, quarantine, secret/network/shell/prompt-injection rulepacks benefit from deterministic fast scanners.

## First Rust slice

tools/skill_static_scanner: path, secret, shell/network/browser/tool declaration, encoded payload, rulepack safety checks.

## Keep in Python / non-Rust

Semantic malicious-intent analysis, scoring policy, approvals, install gates, skill factory drafts.

## CI posture

PR static scanner unit tests + corpus fixtures; long malicious-fixture suite nightly/manual.

## Preparation checklist

- Confirm stable input and output artifacts.
- Define JSON/JSONL schema before implementation.
- Add tiny fixture before large fixture.
- Add no-mutation test if source files are scanned.
- Add Python validator/adapter before changing production workflow.
- Add PR CI before long CI.
- Add long CI only after smoke is stable.
- Record what Rust is not authorized to decide.
