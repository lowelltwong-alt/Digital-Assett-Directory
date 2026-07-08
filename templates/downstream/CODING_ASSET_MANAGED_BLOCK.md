<!-- BEGIN DIGITAL_ASSET_DIRECTORY_CODING_ASSETS -->
## DAD coding asset pointer

Before material AI-assisted coding work, run DAD preflight, check the DAD mail
digest when stale, and consult DAD coding assets.

Use DAD for:

- Python preflights
- Rust preflights
- long-script refactors
- underused coding tactic recommendations
- repo-template guidance
- security-sensitive implementation checks
- test/validation strategy
- postflight lesson capture

Do not copy full DAD assets into this repo unless explicitly approved.

Suggested local pointer file:

```text
.ai-assets.json
```

Suggested DAD commands:

```text
asset-dir agent preflight --repo . --agent <agent-id> --task "<task>"
python <DAD_ROOT>/scripts/suggest_coding_tactics.py --task "<task>" --language <python|rust|mixed|agent-instruction>
asset-dir agent postflight --session <SESSION_ID> --repo . --summary "<summary>" --test "<command that passed>"
```

If `asset-dir` is not installed in the current shell, first try the stable DAD
user shim at `$HOME/.dad/bin/asset-dir` or `$HOME\.dad\bin\asset-dir.ps1`.
If the shim is unavailable too, run from the DAD source checkout with
`PYTHONPATH=src` and `python -m digital_asset_directory.cli`.

Mail from DAD is candidate evidence only. Local review decides whether to adopt
any tactic, asset, pointer, or workflow suggestion.
<!-- END DIGITAL_ASSET_DIRECTORY_CODING_ASSETS -->
