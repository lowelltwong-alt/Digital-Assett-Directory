# Prompt: Security and Unsafe Reviewer

Review the Rust scanner for:

- symlink traversal;
- path traversal;
- output path inside source path;
- accidental raw content output;
- secret leakage;
- `unsafe` usage;
- dependency risk;
- panic/unwrap surfaces;
- large-file memory behavior;
- deterministic sorting and stable schema.

Output:

- blocking issues;
- non-blocking issues;
- required tests;
- dependency audit concerns;
- approval/reject recommendation.

Do not approve if commands were not run or if source-mutation proof is missing.
