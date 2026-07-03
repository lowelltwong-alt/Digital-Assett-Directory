# Executive Decision: Rust Adoption for DAD and Repo Family

## Decision

Upgrade **DAD first** with a small Rust scanner core. Do not rewrite DAD.

Use this architecture:

```text
Python CLI / orchestration
  -> Rust deterministic scanner / verifier
  -> JSON/JSONL observations
  -> Python validation, graph/radar, context packs, lessons, review workflows
```

## Why DAD first

DAD is the repo most likely to benefit from Rust outside Logos Scripture Graph because it scans local drives and GitHub repositories, hashes files, computes identity layers, writes JSONL/SQLite/graph outputs, and already tries to keep scans read-only and source-safe.

## Rust belongs in DAD when the operation is

- deterministic;
- file-heavy;
- hash-heavy;
- repeated in CI or scans;
- stable enough to define an input/output contract;
- safe to express as JSON/JSONL evidence.

## Rust does not belong first when the operation is

- domain interpretation;
- semantic authority;
- human review;
- agent/model orchestration;
- rapidly changing product workflow;
- UI/dashboard logic;
- governance policy.

## Recommended DAD first crate

```text
tools/dad_scan_core/
```

Initial responsibility:

```text
walk local source -> apply exclude/quarantine rules -> metadata/hash observations -> JSONL -> summary JSON
```

Non-responsibility:

```text
asset value scoring, graph/radar logic, lessons, mail center, recommendations, DAD governance authority
```

## First merge target

A passing PR should prove:

```text
cargo check
cargo test
cargo fmt --check
cargo clippy -- -D warnings
python scripts/run_dad_scan_core.py --help
scanner emits valid JSONL for a tiny fixture
scanner does not mutate source files
```

## Long CI target

Long Rust CI should be **manual/nightly/path-triggered**, not every PR at first.

Long CI should include:

```text
cross-platform build
nextest
coverage
cargo-deny
cargo-audit
large synthetic fixture scan
property tests
snapshot tests
mutation testing, optional/manual
benchmark smoke, optional/manual
```
