# Non-Logos Rust Rollout Guide

Non-Logos repos may be eligible for DAD-applied Rust scaffolds only when the
reviewed Rust status matrix gives them a local path, active status, and enabled
rollout flag.

The target repo must be able to build and test its Rust slice without DAD being
present. DAD may generate starter files, but ownership moves to the target repo.

Every target scaffold must preserve these statements:

- Python remains the orchestrator.
- Rust is deterministic leaf tooling only.
- Local source authority wins over DAD candidate guidance.
- No external email, GitHub write, or destructive source mutation is authorized.
- Rust validation commands are local to the target repo.

If DAD lessons change, DAD should send an update packet rather than overwrite
target repo files outside an explicit local apply.
