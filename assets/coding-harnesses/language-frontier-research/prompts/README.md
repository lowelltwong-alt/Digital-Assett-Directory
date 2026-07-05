# Prompts

Use this checklist prompt when another agent evaluates a new language-frontier
idea:

```text
Review this Python, Rust, mixed-language, or future-language discovery for DAD.

Return:
- source ID or URL and whether it matches a trusted source pattern;
- safe summary without copied docs or code;
- why it may improve AI coding;
- where it applies;
- where it does not apply;
- proof surface and validation command;
- target DAD asset, tactic, or harness;
- rejection reason if it is hype, unsafe, private-source, benchmark-only, or too
  broad.

Do not promote the idea. Keep it candidate-only unless reviewed local evidence
exists.
```

For scheduled or deeper research refreshes, use
`language-frontier-refresh.prompt.md`. It asks for a trusted-source match,
proof surface, local falsification idea, AI-overlooked pattern, and target DAD
surface. The prompt is pointer-only by design: it screens candidates into DAD
without copying external docs, code, benchmark tables, private rows, raw logs,
or long source blobs.

For a scarce-credit Fable 5 audit of the July 2026 DAD buildout, start with
`processed/fable5/deep-dives/2026-07-04-dad-last-48h/fable5-master-prompt.md`.
It ranks exception capture, mail, Rust rollout, navigation drift, and frontier
research risks, then asks Fable to solve the hardest problems and delegate
mechanical fixes to Codex.
