# Professional Recruiting Intelligence Workflow

Status: reusable generated-candidate workflow asset derived from the Nevada Bar Results sweep.

This workflow captures a repeatable pattern for building professional recruiting intelligence
from official credential sources, organization rosters, public enrichment evidence, review
queues, and candidate-only opportunity signals. The seed example is the Nevada Bar Results
folder, but the workflow is domain-general: it can apply to lawyers, doctors, licensed
contractors, experts, executives, researchers, packages, vendors, or any population where
official identity and public enrichment must stay separated.

## Core Asset

Parent asset:

```text
professional_recruiting_intelligence_workflow_system
```

Mission:

```text
official credential source
-> stable person/credential identity
-> organization roster and bio evidence
-> public enrichment evidence
-> identity conflict review
-> candidate recruiting, acquisition, or group-liftout signals
-> reviewed exports and dashboards
```

The central rule is authority-first enrichment:

```text
Official source records decide who exists in the core population.
Enrichment evidence can support, refine, flag, or challenge identity.
Enrichment evidence cannot create source truth by itself.
```

For Nevada Bar Results, official Nevada bar pass lists and state bar directory records are
stronger authority than LinkedIn, firm pages, search snippets, generated scores, or recruiting
signals. In another domain, replace those with the relevant official register, license file,
court record, canonical repository, package registry, certification list, or reviewed source
corpus.

## Sub-Assets

| Sub-asset | Role | Reusable value | Candidate edges |
|---|---|---|---|
| Official source intake | Collects official lists, directories, source files, source URLs, hashes, and extraction notes. | Establishes source truth and replayable provenance. | `has_workflow_step`, `supports_but_cannot_override` |
| Person vs credential identity model | Separates person identity from credential identity, aliases, external ids, and source records. | Prevents one mutable profile from overwriting durable credentials. | `implements`, `documents`, `handles_form` |
| Source snapshot archive | Stores raw or cleaned public source evidence with hashes and local paths. | Supports replay, extraction audits, and source drill-down. | `derived_from`, `lineage_evidence_for` |
| Organization discovery lane | Finds firms, offices, networks, markets, source tiers, lifecycle events, and source plans. | Builds target universe before person-level enrichment. | `has_workflow_step`, `requires_human_gate` |
| Roster and bio extraction lane | Pulls official organization bio pages and extracts people, titles, offices, practices, education, admissions, contact clues, and biography sections. | Converts messy public pages into structured evidence. | `handles_form`, `derived_from` |
| Identity resolution engine | Links roster people to official credentials using names, aliases, timing, jurisdiction, education, employer, and public evidence. | Creates durable graph links while preserving ambiguity. | `composes_with`, `supports_but_cannot_override` |
| Exception lake | Captures conflicting identity/link evidence without overwriting existing confident matches. | Turns conflict into a learning loop instead of silent corruption. | `produces_learning_signal`, `requires_human_gate` |
| Public enrichment lane | Uses public search-result evidence, direct profile URLs, news, courts, CLE, publications, awards, and official bios. | Adds useful context without letting enrichment override authority. | `supports_but_cannot_override`, `contaminates_if_default` |
| Opportunity signal taxonomy | Defines candidate-only signals for acquisition, group liftout, succession, rising talent, retention pressure, and market context. | Converts weak public signals into review leads, not facts. | `has_review_packet`, `requires_human_gate` |
| Review queues | Routes missing, ambiguous, common-name, changed-name, stale-employer, weak-tie, and conflict cases to review. | Keeps risky cases out of default outputs. | `has_review_packet`, `produces_learning_signal` |
| Exports and dashboards | Materializes CSV, SQLite, workbook, Power BI, app, or review packets from canonical data. | Gives users product surfaces while preserving database authority. | `derived_from`, `documents` |
| Tests and roadmap gates | Verifies source coverage, idempotence, exclusions, evidence presence, phase gates, and stale state. | Makes the workflow repeatable across AI sessions. | `tests`, `stabilized_by` |

## Optimized Work Order

Use this order unless a source-specific gate requires a narrower pass.

1. Define authority and privacy boundaries.

   Record which source decides population membership, which sources are enrichment, which
   fields are sensitive, which sources are legally or ethically off limits, and which generated
   outputs are candidate-only.

2. Build the official source manifest.

   Capture source URL, title, source type, local path, content type, SHA-256 or metadata
   identity, retrieval timestamp, extraction status, stated count, extracted count, and notes.
   Do not begin profile enrichment until official source coverage is auditable.

3. Normalize core identity.

   Create separate records for:

   - person identity;
   - credential identity;
   - organization identity;
   - source record identity;
   - alias identity;
   - revision identity.

   Permanent identifiers should be based on stable authority fields when available, such as
   jurisdiction plus bar number, license number, registry id, package name, or official source
   id. Generated normalized-name keys are useful matching aids, not final authority.

4. Build the organization universe.

   For law firms, collect firm name, canonical name key, website, offices, markets, source
   tier, lifecycle status, network membership, known aliases, target jurisdictions, and source
   plan. In other domains, this is the employer, vendor, institution, package owner, project,
   or network universe.

5. Capture official roster and bio evidence.

   Prefer official organization pages, official directories, public regulator pages, and
   direct public bio pages before broad web search. Store raw or cleaned source evidence,
   source URL, source hash, parser status, and extraction confidence.

6. Extract structured profile fields.

   Capture:

   - name fields and aliases;
   - current organization and office;
   - title and role level;
   - practice or specialty type;
   - admission, license, or credential fields;
   - education and dates;
   - years active or experience proxy;
   - leadership roles;
   - awards, rising-star indicators, publications, speaking, CLE, clerkship, and association roles;
   - public contact clues when allowed;
   - evidence text and source URL for every derived claim.

7. Resolve identity conservatively.

   Match in this order:

   - exact official credential id;
   - exact full name plus jurisdiction or source context;
   - exact first/last plus timing and source context;
   - official aliases or source-visible former names;
   - education, admission year, employer, office, and specialty corroboration;
   - public profile or search-result evidence as support only;
   - human review queue when ambiguity remains.

   Common names, changed names, out-of-market clues, stale employer conflicts, and weak
   geography ties must remain review candidates until evidence is strong.

8. Hunt missing attorneys with escalating precision.

   Use a ladder instead of brute force:

   - Recheck official source coverage and parser misses.
   - Search official state bar directory or credential profile.
   - Search firm site and site-specific pages.
   - Use exact quoted name plus firm, jurisdiction, and legal terms.
   - Try known aliases, first-name variants, middle initials, maiden/former name hypotheses,
     and law-school or admission-year clues.
   - Search official-domain results before broad web results.
   - Search nearby jurisdictions only when the source context supports it.
   - Store near misses because they explain why future searches should not repeat the same path.
   - Stop and route to review when the cost rises and evidence is still weak.

   The goal is not infinite search. The goal is a reviewed state: confirmed, no confident
   match, weak tie, stale conflict, or needs human review.

9. Add public enrichment under guardrails.

   For LinkedIn-like sources, use direct public profile URLs, public search-result titles and
   snippets, public firm bios, and reviewer notes. Do not scrape profile pages by default.
   Store enrichment as evidence rows with source, query, timestamp, confidence, and review
   status.

10. Build opportunity signals as review leads.

   Signals can include:

   - rising or up-and-coming attorney;
   - successor or next-generation bench;
   - likely retirement or succession pressure;
   - lateral movement evidence;
   - practice-group concentration;
   - same-office team cluster;
   - carrier panel, insurance-defense, or industry focus;
   - acquisition or tuck-in platform fit;
   - group liftout plausibility.

   These are not claims that someone will move or that a firm is for sale. They are review
   leads with evidence and caveats.

11. Keep conflict and exception records.

   If a new public profile, employer, credential, or source fact conflicts with an existing
   confident decision, create an exception case. Include conflict type, evidence for both
   sides, hypothesized cause, recommended action, rule-update note, and review status. Do not
   overwrite the prior confident record until the exception is resolved.

12. Export only from the canonical store.

   Dashboards, CSVs, workbooks, packets, and stakeholder docs should derive from SQLite or the
   source-of-truth store. They are product surfaces and review surfaces, not competing canon.

13. Run gates before handoff.

   Rebuild derived exports, run source inventory checks, run identity and quality audits, run
   roadmap or phase checks, and update handoff notes. A generated state block may change often,
   but the human process rules should change only when the workflow itself changes.

## Search Strategy For Hard-To-Find Attorneys

The elegant approach is layered recall with precision gates, not blind brute force.

| Stage | Search target | Use when | Stop when |
|---|---|---|---|
| Source replay | Official lists, extraction audit, parser misses | A person should exist but is absent from derived tables. | Official source coverage and extraction are accounted for. |
| Credential lookup | State bar or official credential profile | Name is known but current employer or public profile is unclear. | Credential status, bar number, member date, or no-result evidence is stored. |
| Firm domain | `site:firmdomain name attorney lawyer` style search or firm site index | A current or possible employer is known. | Official bio found, official-domain no-result stored, or ambiguity remains. |
| Exact public search | Quoted full name plus jurisdiction, law, firm, school, year | Official-domain evidence is missing. | Strong profile candidate found or no confident match is justified. |
| Variant search | Nickname, initials, middle names, former names, suffix changes | Exact search fails and there is source-visible reason. | Candidate is linked to evidence or routed to alias review. |
| Contextual search | Practice, school, admission year, courts, CLE, awards, publications | Name is common or profile evidence is sparse. | Corroborating context is found or ambiguity remains. |
| Nearby jurisdiction search | Border states, national firm offices, remote practice | Source evidence suggests cross-jurisdiction practice. | Jurisdiction relevance is supported or rejected. |
| Review queue | Human or AI-assisted evidence review | The remaining case is expensive or risky. | Reviewer records confirmed, no confident match, weak tie, conflict, or defer. |

## Signal Definitions

Use these as candidate-only labels. They need evidence and review before downstream action.

| Signal | Evidence examples | False-positive risk |
|---|---|---|
| Rising attorney | recent promotion, rising-star award, leadership role, high-signal practice, publications, clerkship, association role | Awards can be marketing; title can be generic. |
| Long-practicing attorney | admission year, member-since date, bio chronology, graduation year | Admission date may not equal active practice history. |
| Practice specialty | official bio practice areas, matter descriptions, bar/court pages, publications | Website taxonomy may be broad or SEO-driven. |
| Group liftout candidate | same office, same practice, shared matters, leader/successor cluster, multiple related attorneys | Same office does not prove team portability. |
| Acquisition target | small/regional platform, strong practice fit, lifecycle change, coverage gap, network membership | Healthy competitors can look like targets. |
| Retention or movement pressure | employer conflicts, recent moves, successor gaps, office openings/closures | Stale data can mimic movement. |
| Identity conflict | conflicting employer, profile, credential, or name evidence | Conflict may be source staleness, not a true change. |

## Data Capture Checklist

Minimum durable fields:

- source id, source URL, source type, local path, content identity, retrieval timestamp;
- person id, credential id, organization id, aliases, normalized keys, and source-record ids;
- credential jurisdiction, credential number or official id, status, member/admission date;
- firm or organization name, canonical key, lifecycle status, office, market, source tier;
- bio URL, roster URL, page role, extraction timestamp, parser status, source hash;
- title, role level, office, practice areas, education, admissions, dates, publications, awards;
- enrichment query, result URL, result title/snippet, fetched or checked timestamp;
- match score or confidence with methodology version when calculated;
- review status, false-positive risk, missing evidence, and reviewer notes;
- evidence text and source URL for every candidate signal.

## Graph Model

Useful candidate edges:

- parent workflow `has_workflow_step` each sub-asset;
- official source `supports_but_cannot_override` enrichment outputs;
- enrichment signal `contaminates_if_default` source-of-truth records;
- exception case `produces_learning_signal` identity rules;
- review queue `has_review_packet` ambiguous cases;
- test or audit `stabilized_by` workflow steps;
- scraper variants `variant_of` and `has_delta_candidate`;
- export `derived_from` canonical database;
- opportunity signal `requires_human_gate` downstream action;
- person `has_member_asset` credential/profile/source-evidence cluster.

## Recognition Pattern For Future Sweeps

Classify a repo or folder as a candidate professional recruiting intelligence workflow when
multiple of these appear together:

- official population source, registry, credential, license, membership, or exam-result intake;
- separate person, credential, organization, profile, and alias identities;
- source snapshots, raw source hashes, extraction audits, or source drill-down fields;
- roster, bio, profile, or directory scrapers;
- enrichment lanes that are explicitly weaker than official source truth;
- exception lake, conflict queue, needs-review queue, or no-confident-match state;
- opportunity, acquisition, liftout, succession, rising-star, market, or recruiting signals;
- generated exports/dashboards derived from a database;
- tests or roadmap gates enforcing idempotence, source coverage, no unsafe scraping, or evidence completeness.

Route the repo through these categories:

- `review_first_for_reuse`: source authority workflow, identity architecture, exception lake, tests, roadmap gates.
- `preserve_as_source_evidence`: raw source files, snapshots, source manifests, extraction audit.
- `variant_or_delta_review`: many source-specific scrapers or repeated batch scripts.
- `generated_output_not_canonical`: CSV, workbook, markdown, dashboard, or stakeholder packet exports.
- `exclude_from_default_review`: caches, pycache, temporary crawl files, and bulk snapshots unless doing archaeology.

## Generalization Beyond Law Firms

Replace the domain nouns, keep the architecture:

| Law-firm term | Generic term |
|---|---|
| attorney | professional/person/entity |
| bar number | credential id |
| bar result list | official population source |
| state bar directory | official credential directory |
| law firm | organization/employer/provider |
| attorney bio | public profile/source page |
| LinkedIn evidence | public enrichment evidence |
| group liftout | team mobility/composition opportunity |
| acquisition target | organization opportunity candidate |
| practice area | specialty/capability |
| rising star | high-upside candidate signal |

## Safety Rules

- Treat row-level personal/professional data as sensitive review context even when public.
- Do not scrape LinkedIn profile pages by default.
- Do not let enrichment override official source truth.
- Do not treat candidate opportunity signals as facts.
- Do not act on acquisition, liftout, or recruiting signals without human review.
- Do not import bulk generated exports as independent source truth.
- Do not run destructive rebuilders without backup and migration review.
- Keep all DAD outputs generated-candidate until curated evidence promotes a pattern.

## Current Gaps

- This workflow needs a DAD-native recognizer that can emit composite workflow candidates and
  sub-asset edges from arbitrary repo scans.
- Nevada Bar Results is not a git repository, so commit-level provenance is absent.
- A privacy/minimization policy is needed before broad row-level indexing.
- Scraper variants should be clustered and delta-reviewed before code reuse.
- Opportunity signals need calibration labels before they can influence default scoring.
