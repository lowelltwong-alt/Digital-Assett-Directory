# Prompt: Python Bridge Agent

Write the Python wrapper and adapter layer for DAD's Rust scanner.

Required:

- `scripts/run_dad_scan_core.py` wrapper.
- JSONL validator for Rust observations.
- Adapter from Rust observation rows to DAD `AssetRecord` candidates.
- Fixture comparison: Python scanner vs Rust-assisted scanner on tiny source tree.

Constraints:

- Rust output must not bypass Python validation.
- No silent fallback to Python scanner; fallback must be explicit in the report.
- Do not change DAD's default scanner until parity fixtures pass.

Report files changed, commands run, tests run, tests not run, and risks.
