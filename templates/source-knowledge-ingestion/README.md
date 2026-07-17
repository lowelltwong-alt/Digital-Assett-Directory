# Source Knowledge Ingestion Template

Use this template when a monorepo or multi-repository Law Firm OS project wants
to contribute reusable knowledge to DAD without moving product or client data.

1. Copy `source-repository-manifest.template.json` locally and declare only
   stable repository identity, owner, safe candidate families, privacy-excluded
   families, and explicit read/copy allowlists.
2. Run metadata inventory first. Review its counts and exclusions.
3. Approve a bounded content read separately; approve exact copies more narrowly.
4. Build normalized candidate records and a candidate graph.
5. Run the deterministic validator and an independent checker.
6. Submit proposed adoption patches to the source repository under its local
   authority. DAD never writes downstream automatically.

Rollback is non-destructive: mark the snapshot rejected or superseded, route to
the prior reviewed snapshot, and rebuild the graph. Never delete provenance.
