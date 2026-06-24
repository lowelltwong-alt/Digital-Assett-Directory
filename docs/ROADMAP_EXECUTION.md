# Roadmap Execution

Run:

```text
asset-dir roadmap check
```

The checker computes file-based gates and records evidence in `roadmap/state.json`. Human gates remain explicit and cannot be auto-satisfied.

A phase may be marked complete only when:

- required files or outputs exist;
- required validation commands have been run and reported;
- human gates are recorded where required;
- remaining risks are stated;
- the completion does not imply unperformed user-machine scans or production readiness.
