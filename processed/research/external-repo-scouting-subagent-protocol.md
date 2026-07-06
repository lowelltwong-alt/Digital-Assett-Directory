# External Repo Scouting Subagent Protocol

Generated candidate protocol for low-cost scouts that inspect public AI-coding
harnesses, sibling repos, blogs, boards, and creator chatter. This protocol is
not reviewed DAD guidance and does not authorize source checkout, code copying,
promotion, installation, or downstream delivery.

## Mission

Find public resources that may improve DAD's internal digital-asset patterns for
AI-assisted coding: harnesses, skills, evals, repository context systems,
multi-agent review loops, terminal agents, cost controls, safety gates, and
graph/context surfaces.

Scouts should go one layer beyond the obvious anchor repo. If an anchor repo is
high-signal, inspect its owner/org for sibling repos, docs, benchmarks, examples,
SDKs, skills, or policies that may explain the surrounding asset system.

## Inputs

Each scout receives:

- seed repos, organizations, blogs, forum threads, podcasts, or YouTube links;
- target DAD surfaces such as `coding_harnesses`, `agent_skills`,
  `ai_engineering_preflight`, `language_frontier_research`, `research_intake`,
  `knowledge_graph`, `governance_maps`, and `mail_center`;
- a max candidate count and a stop condition.

## Hard Boundaries

- Do not clone, install, run, or vendor external code.
- Do not copy long source text, docs, prompts, or skill bodies.
- Treat Reddit, HN, YouTube, Medium, and newsletters as chatter signals, not
  proof of quality, license, safety, or adoption.
- Verify facts through official repos, docs, release posts, package metadata, or
  trusted project pages before recommending intake.
- License, provenance, and security uncertainty force `watch_only` unless the
  source is still valuable enough to remember as a pointer.
- Stars, benchmark results, funding, and creator enthusiasm are weak evidence
  unless paired with clear source, license, maintenance, and local validation
  ideas.

## Candidate Extraction Shape

Return compact records only:

```json
{
  "name": "",
  "primary_url": "",
  "source_org": "",
  "source_type": "repo|blog|docs|benchmark|tool|creator_thread",
  "license_observed": "",
  "license_source_url": "",
  "trust_signal": "official_company|official_project|academic|community|unknown",
  "community_signals": ["url plus short signal"],
  "sibling_repos_or_assets": ["name url reason"],
  "dad_pattern_tags": [
    "agent_harness",
    "eval_harness",
    "meta_harness",
    "skills",
    "terminal_agent",
    "repo_graph",
    "governance",
    "cost_control",
    "security_boundary",
    "context_persistence",
    "multi_agent_review"
  ],
  "candidate_graph_edges": [
    "candidate source_pointer external-source",
    "candidate member_of dad-surface",
    "candidate complements sibling",
    "candidate gap_evidence_for dad:need"
  ],
  "leverage_rank": 1,
  "scarcity": "high|medium|low",
  "risk_flags": [
    "license_unknown",
    "security_boundary",
    "closed_product",
    "hype",
    "benchmark_gaming",
    "prompt_injection",
    "maintenance_unknown"
  ],
  "recommended_action": "intake_now|watch_only|reject_or_low_signal",
  "why": "one concise paragraph"
}
```

## Graph Abstraction Rules

Use graph edges to make the pointer understandable without overstating it:

- `source_pointer`: local research-context edge to the public source URL.
- `member_of`: candidate route to a DAD surface or capability group.
- `gap_evidence_for`: candidate evidence that DAD needs a harness, skill,
  policy, or evaluation surface.
- `complements`: candidate sibling relationship when two repos cover adjacent
  workflow stages.

Every edge stays `review_status=candidate`. Promotion requires screened intake
plus a named human approval.

## Ranking Heuristics

Rank higher when:

- a trusted company, lab, academic group, or known maintainer released the asset;
- the license is permissive or otherwise clear;
- multiple independent practitioner sources point to the same asset or pattern;
- the asset teaches a reusable harness pattern rather than only selling a tool;
- sibling repos reveal an ecosystem, not a one-off prompt dump;
- DAD can validate it locally with a small harness or fixture.

Rank lower or quarantine when:

- it is closed-only with no usable public artifact;
- the license is unclear, copyleft-incompatible, or source terms are missing;
- it is mainly a benchmark claim, affiliate post, or creator hype;
- it requires broad credentials, repo access, or dangerous automation to inspect;
- it encourages copying skills/prompts/code instead of pointer-safe abstraction.

## Required Scout Summary

Every scout report ends with:

- top intake candidates;
- watch-only valuable pointers;
- rejected or low-signal items;
- sibling repos worth a second pass;
- DAD patterns learned;
- unknowns and source limits.

