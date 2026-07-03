# Rust Learning and Crate Resources

## Core learning sequence

1. The Rust Book: ownership, borrowing, structs, enums, error handling, traits, generics, modules.
2. The Cargo Book: packages, workspaces, features, build/test commands.
3. Rust API Guidelines: naming, interoperability, predictability, type safety, dependability.
4. Clippy docs: common lint-driven improvements.
5. Rust by Example and Rustlings for drills.

## Concepts to learn for this repo family

### Must know

- ownership and borrowing;
- `Result<T, E>` and `?`;
- modules and crates;
- `Path` / `PathBuf`;
- iterators;
- `serde` structs;
- streaming file IO;
- deterministic sorting;
- CLI design with `clap`;
- test fixtures;
- avoiding `unwrap` in production paths.

### Learn later

- lifetimes beyond common references;
- async/Tokio;
- PyO3/maturin;
- Rayon parallelism;
- mmap;
- fuzzing;
- property testing;
- criterion benchmarks;
- `unsafe` review.

## Crate shortlist for DAD scan core

| Need | Crate |
|---|---|
| CLI | `clap` |
| JSON/JSONL | `serde`, `serde_json` |
| errors | `anyhow` first, `thiserror` later for library errors |
| walking | `walkdir` or `ignore` |
| glob/exclude | `globset` |
| hashing | `sha2`, maybe `blake3` for optional speed |
| time | `jiff` or `time` |
| temp fixtures | `tempfile` |
| CLI tests | `assert_cmd`, `predicates` |
| snapshots | `insta` |
| property tests | `proptest` |
| benchmarking | `criterion`, `hyperfine` |
| Python bridge later | `PyO3`, `maturin` |

## Recommended first DAD exercises

1. Write a Rust function that returns a stable sorted list of files under a directory.
2. Add exclude patterns.
3. Compute metadata-only fingerprints.
4. Compute content SHA-256 for small files only.
5. Emit one JSON object per file.
6. Write a Python validator that reads the JSONL.
7. Add a no-mutation test that hashes source files before and after.
8. Run the same fixture twice and compare output except timestamps/scan IDs.

## Warning signs while learning Rust

- You are adding lifetimes everywhere: redesign around owned structs or simple references.
- You are cloning everything: acceptable for first pass, then profile and simplify.
- You want async for local scanning: probably unnecessary at first.
- You want `unsafe`: almost certainly wrong for your first DAD scanner.
- You are encoding policy in Rust enums before the policy is stable: keep it in config/Python.
