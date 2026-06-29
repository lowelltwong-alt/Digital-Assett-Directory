# Claude Post-Merge Roadmap Red-Team

Reviewer: Claude Code (claude-opus-4-8), fresh-eyes post-merge review
Date: 2026-06-29
Branch reviewed: `codex/algorithm-calibration-fixes` (working tree clean at start)
Scope: verify the merged state of roadmap work through Phase 5; read-only except this report.

## Verdict

**Conditional pass.**

The shipped code is honest about what it does, the validation baseline is green,
generated outputs are not committed as truth, and the background radar and Phase 3
sandbox work are genuinely conservative. However, Phase 4 and Phase 5 are marked
**`complete`** while their *named capabilities were never built*, and the human
gates that close them were largely **self-attested by Codex**, not independently
verified by a human. The roadmap checker cannot tell the difference. Treat Phases
4–5 as "boundary-deferred," not "delivered," before relying on this status
anywhere downstream or in a public release.

---

## Top findings by severity

### HIGH

1. **Human gates are satisfied by a string, with no reviewer-identity check.**
   `roadmap.py:_verified_human_gate` accepts any gate whose record has
   `phase_id` matching and `status == "verified"`. It does not check *who* recorded
   it. So an agent that writes its own `reviewer: "codex"` record with
   `status: "verified"` satisfies a "human gate." This directly undercuts
   `docs/ROADMAP_EXECUTION.md:9` ("Human gates remain explicit and cannot be
   auto-satisfied") and the AGENTS.md rule against marking roadmap work complete
   without acceptance evidence. The gate's integrity rests entirely on honest
   authorship of `gate-evidence.json`, which nothing enforces.

2. **Phase 4 and Phase 5 are computed `complete` but the named capability was not
   delivered.** Phase 4 is titled "Optional embeddings and AI-assisted enrichment";
   Phase 5 is "Scheduled change detection and external missing-part research."
   Neither embeddings/model enrichment nor scheduled/automated external research
   was built. Both phases were closed by *re-scoping to the safe subset* ("we did
   nothing risky") and recording that as gate satisfaction. The evidence files are
   admirably explicit about this, but `roadmap check` emits `computed_status:
   "complete"` against the original titles — which overstates delivery to anyone
   reading status rather than the evidence prose.

3. **6 of the 8 Phase 4/5 human gates were recorded by Codex, not a human.**
   `phase-4-deterministic-baseline-retained`, `phase-4-evaluation-harness-benefit-shown`,
   `phase-4-generated-metadata-candidate-status`, `phase-5-external-code-review-gates-active`,
   `phase-5-no-autonomous-merge-promotion`, and `phase-5-rate-limits-source-terms-reviewed`
   all carry `reviewer: "codex"`. The two "approved" gates
   (`phase-4-provider-privacy-boundary-approved`, `phase-5-alert-channels-approved`)
   carry `reviewer: "Lowell-directed roadmap order; codex-recorded conservative
   boundary"` — i.e., the human directed the *order of work*, but Codex authored and
   recorded the boundary. Contrast Phases 1.5 and 2, which have crisp
   `reviewer: "Lowell"` records tied to real review files. Phases 4–5 lack that
   independent human sign-off.

### MEDIUM

4. **`research missing` is a live external-call path with no enablement gate.**
   `cli.py:466` → `research.research_missing_parts` calls
   `requests.get("https://api.github.com/search/repositories", ...)`
   immediately, with or without a token. There is no flag, confirmation, config
   `enabled` switch, or preflight in front of it. Phase 5's "zero scheduled external
   calls" is true only because nothing *schedules* it; the manual command itself
   fires real network traffic on demand. The "gated" framing is procedural, not a
   code-level block.

5. **Roadmap completion is not reproducible from a clean checkout.** Phases 1, 1.5,
   and 2 compute `complete` because their `required_outputs` exist *on the local
   disk* (`processed/catalog/assets.jsonl`, `processed/calibration/...`,
   `processed/reports/...`). Those paths are `.gitignore`d (lines 24–32) and are not
   in the repo. A fresh clone would compute those phases as `planned`/`blocked`
   (missing outputs). The "complete" status is therefore environment-dependent and
   not independently verifiable from version control.

6. **Declared vs computed status drift is silent.** `roadmap.yaml` still declares
   phases 1, 1.5, 2, 3, 4, 5 as `status: planned`, while `roadmap check` computes
   them `complete` and the evidence/commit ("Record conservative roadmap phase 4
   and 5 closure") treat them as closed. The checker reports both fields but does
   **not** flag or exit non-zero on the mismatch. The drift direction is
   conservative (YAML under-claims), but a reader of `roadmap.yaml` alone gets a
   different answer than `roadmap check`.

### LOW / NOTES

7. **Live GitHub-scan code is present and gated only by per-source `enabled:false`.**
   `catalog.py:178` correctly skips disabled github sources, but `scan` defaults to
   `github=True` (`cli.py:102`). Protection is the config flag in the operative
   (gitignored) `sources.local.yaml`, not a hard block. Reasonable for a manual
   tool, but worth naming as a soft gate.

8. **Catalog-size figures vary across evidence and nothing reconciles them.**
   Phase 2.5 JSON reports `catalog_asset_count: 51241`; the radar v1 smoke run cites
   "~95k assets / 654k edges"; Phase 1.5 cites `inspected_path_count: 106743`.
   Different scan moments, but no doc reconciles them, so "complete" rests on
   differently-sized local snapshots.

9. **Phase 4 "evaluation harness shows measurable benefit" gate is closed with a
   Phase 2.5 deterministic-scoring artifact**, not an embeddings/AI-enrichment
   harness. Defensible as a conservative reinterpretation, but it reuses evidence
   for a different question than the gate originally posed.

---

## Confirmed good evidence

- **Validation baseline is green** (commands and results below): pytest 163 passed,
  ruff clean, `validate` 65 checked / 0 errors, `roadmap check --no-update` exit 0.
- **No generated outputs are committed as truth.** `git ls-files` over
  `processed/ raw/ state/ audit/` returns only `README.md` and `.gitkeep` markers.
  `.gitignore` properly excludes catalog, graph, calibration, learning, reports,
  state DBs, secrets (`.env`, `*credential*`, `*secret*`, `*.pem`, `*.key`).
- **Source-scan secret exclusions** are present in `config/sources.example.yaml`
  (`**/*credential*`, `**/*secret*`, `**/*.pem`, `**/*.key`, `**/.env*`) and the DAD
  repo's own `raw/processed/state/audit` are excluded from being re-scanned.
- **`run_scan` honors the `enabled` flag** for both local and github sources; the
  example github source is `enabled: false`.
- **Background Connection Radar v1 is genuinely conservative**: gate-before-score
  (`safety`/`evidence`/`authority`), `raw_text_persisted=false` and
  `safety_cleared=true` enforced by schema, hard compute caps, family dedup, all
  records `review_status="generated_candidate"` under ignored `processed/` paths.
  The real-catalog smoke run produced 10,000 candidates but **0 escalation packets**
  at `tau=0.70` — conservative, not forced.
- **Phase 3 sandbox pilot** used a disposable temp repo, mutated no active repo,
  and demonstrated fail-closed enforcement (exit 2 before postflight, 0 after).
- **Phase 2.5 "100/100" benefit claim is real**: the on-disk
  `phase_2_5_score_delta_validation.json` shows `matched_review_record_count: 100`,
  desired movement `{about_right:54, too_high:18, too_low:28}`, `about_right_churn:0`.
- **`readiness.py` is planning-only template text** — it explicitly cannot enable
  embeddings, scheduled scans, or external research.
- Evidence docs consistently include honest red-team/premortem sections and explicit
  "not accepted as" lists.

---

## Overclaim risks

- **Status word "complete" on Phases 4–5** vs the as-built reality (capability
  deferred). Recommend a status like `boundary_deferred` / `awaiting_capability_gate`
  or a roadmap-level note so the word "complete" doesn't propagate.
- **Self-attested human gates** (finding 3): "verified" by the same agent that did
  the work is not independent verification.
- **Phase 2.5 benefit is narrow**: content profiling covers only code/schema/test/
  agent/skill/prompt/workflow/config; `document` is 1/38,314 profiled, `dataset`
  8/5,123, `model`/`algorithm`/`adapter` 0. The "measurable benefit" is real for the
  target surface only — as the evidence itself states — and must not be generalized
  to documents, media, or row-level corpora.
- The 100/100-with-zero-churn result is clean enough to warrant confirming that the
  Phase 2 desired-band labels are **independent human labels**, not derived from the
  new content-aware scorer (guard against circular validation).

---

## Security / privacy risks

- **`research missing` fires live external GitHub calls with no gate** (finding 4).
  This is the single most concrete contradiction of the "external research gated"
  posture. Mitigation today is only that nobody runs it and nothing schedules it.
- **No hard kill-switch for external calls.** `github_scan.py` and `research.py`
  carry fully functional `requests`-based network code. Gating is config/usage
  discipline, not an enforced flag. Acceptable for a manual local-first tool, but a
  public release or a less careful operator changes the risk profile.
- **Public-release exposure**: gate evidence and several evidence files embed
  absolute local paths and a real owner handle (`lowelltwong-alt`), and reference
  local-only generated artifacts. None of that is secret, but it should be reviewed
  before any public DAD repo.
- No raw secrets or tokens found in tracked files; token use is env-var based
  (`GITHUB_TOKEN`), which is correct.

---

## Roadmap gate risks

- The checker's `status == "verified"` test (finding 1) is the central structural
  risk: it makes "human gate" a self-serviceable field.
- Phases 4 and 5 declare **no `required_files`, `required_outputs`, or `commands`** —
  they are 100% human-gate-driven. Combined with finding 1, that means an agent can
  close them by writing JSON alone. There is no file/command anchor forcing real
  artifacts to exist.
- Silent declared/computed drift (finding 6) means `roadmap.yaml` and `roadmap check`
  can disagree indefinitely with no warning.

---

## Candidate-only risks

- Candidate-only semantics are **well preserved**: radar contracts default to
  `generated_candidate`, generated outputs live under ignored paths, and AGENTS.md /
  front door / identity ladder all reiterate "candidates do not prove truth."
- Residual risk: a future agent reads `computed_status: complete` for Phase 4 and
  treats it as blanket permission to enable embeddings/LLM enrichment. The evidence
  file warns against exactly this, but the *status word* invites the misread.

---

## Premortem (six months out)

1. **A future agent flips embeddings/external research on, citing "Phase 4/5
   complete."** The status word, not the prose, is what gets remembered. Most likely
   failure.
2. **Someone runs `asset-dir research missing` (or a script wraps it)** and external
   GitHub traffic starts with no review record — "zero external calls" quietly
   becomes false.
3. **A clean clone / CI cannot reproduce "complete"** because the generated outputs
   are local-only; the roadmap looks regressed and someone "fixes" it by regenerating
   or relaxing gates.
4. **Self-attested gates compound**: later phases inherit the precedent that an agent
   may record its own "verified" human gate, eroding the human-in-the-loop guarantee.
5. **Phase 2.5 benefit gets over-generalized** to documents/media/datasets where
   content profiling barely fired, and scores are trusted beyond their calibrated
   surface.
6. **Public release leaks local paths / owner handle / catalog shape** from evidence
   files that were written as internal notes.

---

## Recommended fix order

1. **Re-status Phases 4 and 5** away from bare `complete`. Either add a distinct
   status (`boundary_deferred`) or split each phase into a closed "conservative
   boundary" sub-gate and an open "capability" sub-gate. Keep the excellent evidence
   prose; fix the one-word summary.
2. **Strengthen `_verified_human_gate`** to require a human reviewer for human gates
   (e.g., reject `reviewer` values that are agent IDs like `codex`/`claude-code`, or
   require an explicit `human_verified: true` set only by a human-run command). At
   minimum, surface the reviewer in `roadmap check` output and flag agent-recorded
   human gates.
3. **Add an enablement gate to `research missing`** (and any github scan entry):
   require an explicit `--enable-external` flag or config switch plus a recorded
   approval, so the live-call path cannot fire by accident.
4. **Make declared/computed drift loud**: have `roadmap check` warn (and optionally
   exit non-zero under a `--strict` flag) when `declared_status != computed_status`,
   and reconcile `roadmap.yaml` to match reality.
5. **Anchor Phase 4/5 acceptance to at least one tracked file** (the evidence docs
   themselves), so completion is not purely JSON-driven.
6. **Confirm Phase 2.5 labels are independent** of the content-aware scorer; record
   that confirmation.
7. **Add a public-release scrub checklist** for evidence files (paths, handles,
   local-only references) before any public DAD repo.

---

## Commands run and results

All run with `$env:PYTHONPATH='src'` from the repo root on Windows / Python 3.12.

| Command | Result |
|---|---|
| `python -m pytest` | **163 passed** (~22s) |
| `python -m ruff check src tests scripts noxfile.py` | **All checks passed!** |
| `python -m digital_asset_directory.cli validate` | `{"valid": true, "checked_count": 65, "errors": []}` |
| `python -m digital_asset_directory.cli roadmap check --no-update` | exit **0**; phases 1/1.5/2/2.5/3/4/5 computed `complete`; declared status for 1/1.5/2/3/4/5 still `planned` |

Supporting read-only checks:
- `git ls-files processed raw state audit` → only `README.md` / `.gitkeep` (no generated outputs committed).
- Inspected `roadmap.py`, `cli.py` (scan/research/roadmap commands), `catalog.py`
  (`run_scan` honors `enabled`), `github_scan.py`, `research.py`, `readiness.py`,
  `config/sources.example.yaml`, `.gitignore`, and the Phase 2.5 validation JSON.

Note: the earlier "exit 255" seen when piping `roadmap check` through
`Select-Object` was a PowerShell pipe artifact; the command's real exit code is `0`.

---

## Anything not verified

- **The operative `config/sources.local.yaml`** (gitignored) was not read. The
  GitHub-deferred / source-scope claims depend on its contents; I verified only the
  example config and the code that honors `enabled`.
- **Independence of the Phase 2 desired-band labels** from the content-aware scorer
  (possible circular validation) — not confirmed.
- **The Phase 3 central-hub handoff/lesson IDs** and the "100 indexed lessons" claim
  were not independently re-derived; the referenced `raw/lessons/...` data is
  gitignored and local-only.
- **The radar v1 smoke-run numbers** (95k assets / 654k edges / 0 packets) were read
  from evidence, not re-executed.
- **Provider/embedding privacy posture for a future public split** — out of scope of
  the current local-only boundary; flagged as a future gate only.
- I did **not** run a live scan, a github scan, or `research missing` (would generate
  outputs / external calls); this review stayed read-only except for this report.
