# Fable Review Prompt: Hard-Issue Lookup And Solution Lineage

You are reviewing DAD's hard-issue lookup and solution-lineage design.

Goal:
DAD should help Codex, Claude, Cursor, Fable, and future coding agents recognize
when a problem is easy/local versus hard/reuse-worthy; search DAD for prior
exception fixes before improvising; and, after the fix, record only the useful
solution delta so DAD learns without creating sprawl.

Current architecture:

- DAD is the local-first hub and source of reusable assets, coding harnesses,
  mail, repo enrollment, exception events, fix outcomes, and context packs.
- Exceptions live in `processed/exceptions/lake/events.jsonl`.
- Fix outcomes live in `processed/exceptions/fix-outcomes/outcomes.jsonl`.
- The downstream repo exception guide is
  `templates/downstream/EXCEPTIONS_README.md`.
- The buildout design is `docs/DAD_EXCEPTIONS_LAKE_BUILDOUT.md`.
- The CLI now has `asset-dir exceptions hard-issue-lookup`.
- `asset-dir agent preflight` and `asset-dir agent midflight` may surface a
  compact hard-issue lookup in the context pack when observable work signals
  suggest a non-obvious failure.

Non-negotiables:

- Do not rely on hidden chain-of-thought. Use observable signals only: task text,
  command argv/exit, retries, validation gaps, user corrections, stale reports,
  permission errors, safe summaries, and postflight outcomes.
- DAD evidence is candidate-only until reviewed locally.
- Private/internal/restricted/unknown-origin fix details cannot flow to
  public-facing repos without human release.
- Do not copy raw logs, stack traces, diffs, private rows, source files, hidden
  reasoning, or prompt-injection-like payloads.
- Avoid fake confidence. Broad event-type matches are related patterns, not
  direct recommendations.

Please improve the design:

1. Propose the best algorithm for classifying:
   - `easy_local_fix`
   - `known_template_or_common_fix`
   - `hard_issue_lookup_required`
   - `new_exception_and_fix_outcome_required`
   - `solution_lineage_review`
2. Propose a novelty/delta model for solution families:
   - duplicate
   - parameterized variant
   - context delta
   - derivative solution
   - genuinely new pattern candidate
   - dangerous/noise
3. Design the graph structure connecting:
   - exception events
   - validated fixes
   - repo context
   - DAD assets/harnesses/templates
   - commands and validation refs
   - parent solution and solution delta
4. Recommend how to store only the useful delta from a second/third solution
   while still making future reuse easy.
5. Identify false positives and false negatives:
   - hard issue missed and no lookup happened;
   - easy issue over-routed into DAD ceremony;
   - private fix leaked to public repo;
   - broad event type produced a misleading fix;
   - a novel solution was collapsed into duplicate;
   - a duplicate solution caused knowledge sprawl.
6. Design tests and synthetic fixtures that prove agents:
   - search DAD early/often during hard issues;
   - do not search for trivial local fixes;
   - emit exception/fix packets without Lowell rescuing the case from chat;
   - update behavior when DAD's capture patterns change;
   - record postflight solution deltas with parent/child lineage.
7. Compare this against professional patterns such as SRE postmortem systems and
   Knowledge-Centered Service. Recommend what DAD should copy, improve, or
   reject.

Return:

- Critical / High / Medium / Low findings.
- A revised algorithm with deterministic features and thresholds.
- A proposed schema for `solution_delta` records.
- A minimal graph model.
- A test plan with at least 12 synthetic cases.
- Any unique, non-standard design you would build if you were optimizing DAD for
  AI coding agents rather than a human-only knowledge base.

Do not implement changes. Be concrete enough that Codex can implement your
recommendations in a follow-up PR.
