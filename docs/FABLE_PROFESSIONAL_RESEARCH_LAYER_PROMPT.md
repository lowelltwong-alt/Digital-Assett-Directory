# Fable Prompt: Professional Research Layer For DAD

You are reviewing DAD's professional research layer. DAD is the Digital Asset
Directory: a local-first library/control plane for many repos. It stores
candidate assets, harnesses, agent skills, exceptions, lessons, repo mail,
usage traces, and source-aware research pointers. Repos keep local authority.

## Your Role

Act like a high-leverage research architect for AI-assisted software
engineering. Do not implement changes. Improve the design with ideas Codex may
miss: algorithms, role routing, frontier-source detection, novelty filters,
coding-harness design, graph structure, and tests.

## Read These First

- `AI_FRONT_DOOR.md`
- `AGENTS.md`
- `AI_TABLE_OF_CONTENTS.md`
- `docs/DAD_PROFESSIONAL_RESEARCH_LAYER.md`
- `docs/RESEARCH_INTAKE_PIPELINE.md`
- `docs/HARNESS_DISCOVERY_RADAR.md`
- `docs/CODING_HARNESS_LIBRARY.md`
- `docs/DAD_EXCEPTIONS_LAKE_BUILDOUT.md`
- `docs/FABLE_HARD_ISSUE_LOOKUP_AND_SOLUTION_LINEAGE_PROMPT.md`
- `registry/trusted-source-registry.json`
- `registry/preflight-profile-router.json`
- `registry/dad-offerings-registry.json`
- `registry/harness-discovery-methodology.json`
- `assets/coding-harnesses/language-frontier-research/`
- `processed/fable5/deep-dives/2026-07-04-dad-last-48h/fable5-master-prompt.md`

## Design Goal

DAD should make every future coding agent better by doing this early:

1. Search DAD first for known fixes, assets, lessons, exception outcomes,
   harnesses, skills, language playbooks, and non-negotiables.
2. If DAD lacks a good answer, run bounded professional research against
   reviewed public sources.
3. Capture the researched fix or insight back into DAD as pointer-only,
   provenance-rich candidate knowledge.
4. Escalate high-signal coding discoveries quickly while separating noise,
   hype, leaks, and non-reproducible claims.
5. Optimize professional methods for AI coding and AI code reading, not human
   meeting rituals.

## What To Improve

Please red-team and improve:

- The role lanes: DAD lookup, professional-method scout, real-world-fix scout,
  frontier-AI scout, harness/skill distiller, lesson/pattern scout, and noise
  filter.
- The algorithm for deciding when a problem is easy local work versus hard
  enough to require DAD lookup, professional research, or exception capture.
- The algorithm for deciding whether a research source is high-signal, noisy,
  dangerous, or merely interesting.
- How DAD should detect the next "harnesses are huge" moment from official docs,
  high-signal blogs, white papers, GitHub codebases, and model/tooling releases.
- How DAD should adapt human methods like Scrum, SRE, architecture review, KCS,
  security review, and test strategy into AI-first gates, context packs,
  validation commands, and learning records.
- How researched fixes should become exception/fix outcome records and later
  appear in hard-issue lookup without creating sprawl.
- How DAD should represent solution families, derivative fixes, deltas, and
  context-specific variants in a graph.
- How to test this system with synthetic updates and adversarial examples.

## Constraints

- Do not recommend copying leaked, proprietary, private, credential, raw log,
  stack trace, source blob, or long third-party content into DAD.
- Treat high-signal as "worth investigating," not "proven true."
- Keep DAD local-first and candidate-only unless a named human/review gate
  promotes something.
- Repos decide whether to adopt DAD suggestions.
- Public-facing repo movement needs private/public provenance and human release
  gates.
- Prefer small composable workflow patterns, executable evals, and traceable
  source pointers over broad process ceremony.

## Output Format

Return:

Critical:
- Issue, risk, and concrete fix.

High:
- Issue, risk, and concrete fix.

Medium:
- Issue, risk, and concrete fix.

Low:
- Issue, risk, and concrete fix.

Best New Ideas:
- Name, why it matters, how DAD would build it, expected tests.

Algorithm Suggestions:
- Pseudocode or scoring/routing rules for hard-issue detection, source
  evaluation, high-signal escalation, novelty/delta detection, and graph links.

Harness Suggestions:
- Harness name, inputs, outputs, evals, failure modes, promotion gate.

Premortem:
- Tell the likely failure story where this system becomes noisy, leaks data,
  misses a frontier shift, or teaches agents the wrong lesson.

Do not implement changes.
