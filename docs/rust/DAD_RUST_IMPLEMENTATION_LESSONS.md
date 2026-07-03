# DAD Rust Implementation Lessons

The authoritative lesson ledger is append-only:

```text
lessons/rust_rollout/lesson_ledger.jsonl
```

Current implementation lessons:

- Install the Rust leaf tool before downstream rollout. Do not ask other repos
  to adopt Rust until DAD can compile, test, and call its own scanner.
- Keep the Python bridge structured and mockable. The bridge should surface the
  exact Cargo command, return code, stdout, stderr, and output paths.
- Treat `cargo fmt --check` as an early pack-quality check. Formatting failures
  are normal for generated scaffolds and should be fixed before expanding scope.
- Keep scan outputs outside the scanned source unless a governed safe-output
  policy is added.

Regenerate the machine summary with:

```bash
asset-dir rust-rollout lessons-summarize
```
