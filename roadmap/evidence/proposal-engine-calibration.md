# Proposal Engine Calibration Evidence

Evidence date: 2026-06-26T11:18:23.890609+00:00

## Source Review File

- Review file: `C:\Users\lowel\OneDrive\Desktop\Git Projects\04_Digital_Assett_Directory\processed\proposals\proposal_review_template.jsonl`
- Source review records are human labels over generated candidate proposals.
- This evidence does not promote source-repository changes or generated proposals to truth.

## Gate Coverage

- Reviewed records: **50**
- Reviewed bottom-up records: **25**
- Reviewed top-down records: **25**
- Calibration gate complete: **True**

## Review Outcomes

- Usefulness: `{'useful': 30, 'not_useful': 18, 'unsure': 2}`
- Safety: `{'safe': 50}`
- Novelty: `{'already_known': 25, 'unsure': 19, 'novel': 6}`
- Actionability: `{'actionable': 30, 'not_actionable': 18, 'unsure': 2}`
- Decisions: `{'accept_candidate': 28, 'reject_candidate': 18, 'defer': 4}`
- Accepted bottom-up candidates: **4**
- Accepted top-down candidates: **24**
- Candidate default path from accepted counts: **top_down_orchestration**
- Human-selected default path: **hybrid**
- Human default rationale: Human review approved hybrid default: top-down should be the safer default review queue because it produced strong governed stale-asset risk reviews, while bottom-up remains useful for same-family or high-evidence connections but produced many shallow lexical false positives.

## Calibration Findings

- False positive notes: **18**
- False negative notes: **1**
- Useful example notes: **30**
- Structured calibration notes complete: **True**

### False Positive Notes

- `review-002` `bottom_up_self_proposal` `dad:proposal:f568eec4-f190-58e7-b65e-ddbf0aca5198`: Cross-repo lexical overlap between registry validation test and legal billing source note does not imply test coverage for the target document.
- `review-003` `bottom_up_self_proposal` `dad:proposal:f5c0dc09-611e-5c9b-9e5d-177ceddc37db`: DAD README is hub documentation, not documentation coverage for a private law firm roster dataset; likely shallow token overlap.
- `review-004` `bottom_up_self_proposal` `dad:proposal:f6545c18-f9b1-5ccf-8bc2-96d103a6e0bb`: Archived skill-agent control-plane test does not test ABA UTBMS source-note content; archived copy plus cross-domain overlap.
- `review-005` `bottom_up_self_proposal` `dad:proposal:f6907a72-42a3-56da-a4a5-1e7f194c1190`: Logos gold-promotion test is domain/governance-specific and does not provide coverage for legal billing ABA source note.
- `review-007` `bottom_up_self_proposal` `dad:proposal:f720179e-0f39-52c1-927b-5d6a94bf3cf3`: Augustine canon README does not document law firm roster dataset; likely generic token overlap.
- `review-010` `bottom_up_self_proposal` `dad:proposal:f7b7777b-70a1-5af3-98d5-30453fb24a33`: Archived Logos philosophy README does not materially document FMG decision log; cross-project generic governance overlap.
- `review-011` `bottom_up_self_proposal` `dad:proposal:f7bbe50a-3325-554d-817b-c6d0b8e917bb`: Archived Logos translation README is not actionable documentation for session_start_notice.py; likely shallow Logos-path overlap.
- `review-012` `bottom_up_self_proposal` `dad:proposal:f8435bfe-472c-5e75-b4f3-fc30a07f2693`: Archived canon README does not document legal billing LEDES XML parsing; cross-domain lexical overlap.
- `review-013` `bottom_up_self_proposal` `dad:proposal:f864c545-812b-5eac-88ce-ea04ec8cff36`: Generic graph/assertion documentation overlap does not establish documentation coverage for a Logos reliability evidence schema test.
- `review-015` `bottom_up_self_proposal` `dad:proposal:f8926fc3-79d3-5d5e-8cac-177c6ead3071`: Archived noncanonical text category README is not actionable coverage for identity/label separation validator code.

### False Negative Notes

- `review-041` `top_down_orchestration` `dad:proposal:efc65168-a450-50b5-b9cd-c5b6a3fc921c`: Top-down stale-asset proposals are useful, but the proposal engine still does not group stale research/media assets by collection, owner, topic, or decision workflow, so it under-proposes the higher-value bundled review action.

### Useful Examples

- `review-001` `bottom_up_self_proposal` `dad:proposal:f52a7d0f-d5b2-5620-afbc-6b8fcb7e0451`: Good same-repo documentation-to-validator coverage; the graph shapes README plausibly explains graph shape context for identity/label separation validation.
- `review-008` `bottom_up_self_proposal` `dad:proposal:f72c04a6-c48e-5751-b699-a0853546c455`: Segment provenance test appears relevant to governance/talent intelligence extension because provenance controls can operationalize the extension safely.
- `review-009` `bottom_up_self_proposal` `dad:proposal:f76a3dc6-944a-5af8-a63c-ab6debd7217a`: Potentially useful cross-domain chunking workflow connection; deferred because Mock Trial is actively changing and excluded from pilot action.
- `review-014` `bottom_up_self_proposal` `dad:proposal:f877bf91-967d-5e45-a46b-e71470f43c96`: Useful same-family connection: graph concepts documentation can help future agents understand what chunking gold validation is preserving or testing.
- `review-016` `bottom_up_self_proposal` `dad:proposal:f8c6cd32-e991-509c-b5ca-f3b2d27e4473`: Useful governance connection: agent-skill operating guidance can support review and hardening of malicious skill intake policy.
- `review-019` `bottom_up_self_proposal` `dad:proposal:f8fadf7c-c77e-5b18-9c92-61d3524a400a`: Useful governance/workflow connection: exception handling runtime docs may help harden universal prompt header rules, but action should wait for boundary review.
- `review-027` `top_down_orchestration` `dad:proposal:4a6dc4fd-865c-5732-afcf-c7a3cb8cae3c`: Clear top-down win: portfolio-level stale lifecycle review helps prioritize governed keep, renew, archive, or dismiss decisions across many assets.
- `review-028` `top_down_orchestration` `dad:proposal:db105629-045d-54bb-bfc3-9e58323de9e6`: Useful top-down stale-asset item: flags a research PDF for freshness/risk review without implying source truth or mutation.
- `review-029` `top_down_orchestration` `dad:proposal:ded3d2b4-67e8-58f3-875a-2955dcfca370`: Useful top-down stale-asset item: flags a research PDF for freshness/risk review without implying source truth or mutation.
- `review-030` `top_down_orchestration` `dad:proposal:e0b4f671-8123-526e-9b55-f7433ff34125`: Useful top-down stale-asset item: flags a research PDF for freshness/risk review without implying source truth or mutation.

## Remaining Risks

- Human labels are calibration evidence, not proof that any source repo should change.
- External code, license, security, and compatibility review remain required before reuse.
- Roadmap status should change only if the relevant phase acceptance criteria are otherwise met.
