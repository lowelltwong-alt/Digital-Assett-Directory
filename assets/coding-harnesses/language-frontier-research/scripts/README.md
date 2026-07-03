# Scripts

Current first-pass runbook:

```text
python scripts/validate_language_frontier_harness.py
python scripts/validate_coding_asset_control_plane.py
python -m pytest tests/test_coding_asset_control_plane.py -q
```

Future scripts should take a pointer-only frontier packet and report:

- accepted candidate route;
- blocked reason;
- required local validation command;
- target DAD asset or harness;
- public/private and source-provenance warnings.
