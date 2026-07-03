# Skill: Rust CI QA

## Purpose

Create PR and long CI for Rust tools inside Python-governed repos.

## PR CI

- fmt;
- clippy;
- cargo test;
- CLI help smoke;
- tiny fixture scan.

## Long CI

- nextest;
- doc tests;
- cargo-deny;
- cargo-audit;
- coverage;
- mutation testing;
- large synthetic scan;
- cross-platform matrix.

## Boundary

Do not make long CI a required PR gate until it has a stable pass history and clear failure ownership.
