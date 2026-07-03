# Python/Rust Boundary

DAD uses Python as the orchestrator and Rust as deterministic leaf tooling.

Rust may own:

- local file walking;
- exclusion and quarantine accounting;
- bounded hashing;
- metadata observation emission;
- JSONL validation;
- static manifest and ledger integrity checks.

Python keeps:

- Typer CLI orchestration;
- DAD config, registries, and policy routing;
- SQLite/catalog workflows;
- graph, radar, and usefulness scoring;
- human review state;
- mail, lessons, exceptions, and calibration loops;
- model calls and agent context packs.

Rust must not own legal judgment, theological judgment, governance promotion,
source authority, review authority, external service writes, or destructive
source mutation.
