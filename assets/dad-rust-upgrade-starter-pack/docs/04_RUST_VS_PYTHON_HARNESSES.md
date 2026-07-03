# Rust vs Python Harnesses

## Harness definition

A harness is the repeatable test/validation envelope around a tool. It should specify:

```text
inputs -> command -> outputs -> invariants -> failure conditions -> evidence report
```

## Rust coding harness

Best for deterministic components.

### Required layers

```text
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test
cargo nextest run
fixture scan smoke
JSON/JSONL schema validation
no-mutation check
large synthetic scan, optional long CI
coverage, optional long CI
mutation testing, optional/manual
```

### Rust harness outputs

```text
target/nextest/default/junit.xml
coverage/lcov.info
reports/rust/dad_scan_core_smoke.json
reports/rust/no_mutation_report.json
reports/rust/dependency_audit_report.json
```

### Rust invariants

- no source mutation;
- no symlink following unless authorized;
- no secret output;
- no raw text output when no-text mode is required;
- deterministic sort order;
- stable schema version;
- stable error shape;
- bounded memory for large files;
- no `unsafe` unless separately justified.

## Python coding harness

Best for orchestration and domain workflows.

### Required layers

```text
ruff check
ruff format --check
mypy, where configured
pytest unit
pytest integration/smoke
schema export/validate
repo validation
workflow smoke demo
artifact completeness checks
```

### Python harness outputs

```text
.pytest_cache disabled or ignored
reports/python/pytest_report.json
reports/python/schema_validation_report.json
.lawfirm-os-intake/demo/...
processed/scans/...
```

## Mixed Rust/Python harness

Best for DAD migration.

```text
1. Rust scanner emits raw observation JSONL.
2. Python validates JSONL schema.
3. Python adapter converts observations to AssetRecord candidates.
4. Existing Python graph/radar pipeline runs.
5. Diff report compares Python-only vs Rust-assisted scan on tiny fixture.
```

## Harness promotion gates

| Gate | Required before |
|---|---|
| Rust smoke passes | committing Rust crate |
| Rust+Python adapter parity passes | defaulting DAD to Rust scanner |
| Long CI passes twice | large source scans |
| No-mutation proof passes | any scan outside fixtures |
| dependency audit passes | wider reuse across repos |
| security review passes | skill scanner or legal/intake scanner adoption |
