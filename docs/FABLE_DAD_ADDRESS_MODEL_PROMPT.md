# Fable Prompt: DAD 9-Layer Address Model Review

You are reviewing DAD's adopted 9-layer address model.

Context:

- DAD is a local-first digital asset, mail, exception, harness, skill, template,
  and learning-control-plane hub across many repos.
- DAD uses a knowledge graph for relationships, but it now also uses a compact
  address model as a coordinate system for where assets, lessons, workflows,
  exception events, and learning outcomes belong.
- DAD adopted layer 9 as `learning_adaptation` because recursive AI improvement
  needs a first-class place for postflight outcomes, solution variants, context
  deltas, calibration, upgrades, retirement, and future lookup triggers.
- LawFirm OS source research inspired the model. It has an 8-layer DNA address
  discipline and observed ninth-layer variants: learning/adaptation and
  orchestration/workflow.

Primary files:

- `docs/DAD_ADDRESS_MODEL.md`
- `registry/dad-address-model-registry.json`
- `schemas/dad-address-model-registry.schema.json`
- `docs/REPO_LOCAL_DIGITAL_ASSET_DIRECTORY.md`
- `schemas/repo-local-digital-asset-record.schema.json`
- `docs/KNOWLEDGE_GRAPH_MODEL.md`

Please red-team and improve the design:

1. Does the model actually help agents find, fill, and reuse DAD records, or is
   it too ceremonial?
2. Are the 9 layers the right decomposition for AI coding, repo governance,
   exception learning, and cross-repo asset memory?
3. Is layer 9 as `learning_adaptation` the right choice, or should workflow /
   orchestration become a separate first-class layer, card type, or graph edge
   family?
4. Is the compact tuple enough: `environment / authority_zone / layer / domain /
   module / object_type / object_id / version`?
5. Can workflows be encoded more powerfully without bloating context packs?
6. What fields should every asset card fill, which should be optional, and which
   should be refs to separate records?
7. What synthetic tests would prove agents can fill and use the model
   deterministically?
8. Where could this model create false confidence, overfitting, private-data
   leakage, source-authority drift, or graph confusion?
9. Propose one standard improvement and one non-obvious/creative improvement.

Return:

- Critical / High / Medium / Low findings.
- A premortem failure story.
- A revised compact schema or tuple if you have one.
- Suggested tests and fixture examples.
- Any frontier-AI or professional architecture ideas DAD should research next.

Do not implement changes. Treat all recommendations as candidate-only until DAD
review, migration tests, and human approval where needed.
