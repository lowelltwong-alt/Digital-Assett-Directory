# DAD Local Deployment

DAD is local-first. The normal local deployment path is:

```powershell
.\scripts\bootstrap.ps1
```

On Unix-like shells:

```sh
./scripts/bootstrap.sh
```

Bootstrap installs DAD into the repo-local `.venv`, writes the user hub locator
at `~/.dad/hub.json`, and creates stable user-level shims under `~/.dad/bin`.
Add `~/.dad/bin` to PATH when you want to call `asset-dir` from any repo without
remembering the DAD checkout path.

The user hub locator has this shape:

```json
{
  "schema_version": "dad.hub-locator.v1",
  "hub_path": "C:/path/to/04_Digital_Assett_Directory",
  "hub_ref": "dad://hub/Digital-Assett-Directory"
}
```

The locator is read as UTF-8, with a UTF-8 BOM tolerated for Windows/editor
compatibility. It must parse to a JSON object; arrays, strings, malformed JSON,
or locator targets that are not a valid DAD hub fail closed.

## Resolution Order

DAD resolves the hub in this order:

1. Explicit `--hub`.
2. `DAD_HUB` or `DAD_HUB_PATH`.
3. User locator `~/.dad/hub.json`.
4. Current repo fallback, only when the command is already inside the DAD hub.

The fallback exists for raw checkouts and test runs. It is not the preferred
cross-repo invocation path.

## Doctor

Use deployment scope to prove DAD is callable and locatable:

```powershell
asset-dir doctor --scope deployment
```

Deployment scope is a fast smoke check. It prints hub resolution, Python,
`asset-dir` or shim availability, Rust toolchain availability, caller-repo
status, reviewed policy reachability, and unavailable-hub policy. It does not
write `processed/reports/operational_readiness.*`.

For cross-repo deployment proof, check both `deployment_ready` and
`deployment.asset_dir.external_invocation_ready`. The deployment probe clears
source-checkout `PYTHONPATH`/`PYTHONHOME` and runs from a temporary non-DAD
directory before it can verify an external invocation path. A raw source
checkout inside the DAD repo may still be callable through
`python -m digital_asset_directory`, but that is reported as
`invocation_mode: raw_checkout_fallback` and does not prove another repo can
invoke DAD through `asset-dir` or the user shim.

Also check `deployment.asset_dir.user_bin_on_path` when diagnosing why a shell
still says `asset-dir` is unavailable. `user_shim_available=true` means a direct
shim exists; `user_bin_on_path=true` means that shell should also resolve plain
`asset-dir`.

If `asset-dir` is not on PATH yet, use either of these:

```powershell
& "$HOME\.dad\bin\asset-dir.ps1" doctor --scope deployment
.\.venv\Scripts\python.exe -m digital_asset_directory.cli doctor --scope deployment
```

The deployment doctor also emits machine-readable recovery guidance at:

```text
deployment.asset_dir.recovery_guidance
```

Use that field when an agent reports `asset-dir` is unavailable. It names the
missing pieces, the bootstrap command, the user bin directory to add to PATH,
direct shim commands, and the boundary that deployment recovery does not
authorize writes to the caller repo or any target repo.

The recovery payload also includes a machine-readable `contract` object. That
contract freezes the allowed `missing_or_unverified` codes, allowed
`preferred_action` values, and the fields that may contain local paths. Future
agents should extend that contract deliberately instead of inventing new strings
inside recovery output.

`--write-hub-locator` is deliberately narrow. It may repair the user-level
locator at `~/.dad/hub.json` or a DAD child-probe temporary locator, but it must
not write locator files inside a caller repo or arbitrary target path. External
invocation probes must also attest that the imported DAD operational module came
from the resolved hub; green-looking wrapper output alone is not deployment
proof.

If the locator write itself fails because the user-level `.dad` folder is
locked, denied, offline, or otherwise unavailable, deployment doctor fails
closed with a structured `locator_write` error and does not write into the
caller repo as a fallback.

Use operational scope when you also want the stricter local readiness check for
catalog, roadmap, generated surfaces, and validation state:

```powershell
asset-dir doctor --scope operational
```

Operational scope writes `processed/reports/operational_readiness.md` and
`processed/reports/operational_readiness.json` in the DAD hub.
Those persisted reports redact local recovery command paths and keep only the
non-sensitive recovery contract plus a pointer back to `doctor --scope
deployment` for local-only commands.

## Unavailable Hub Policy

When DAD is unavailable, ordinary local coding may continue with a logged
warning. Cross-repo writes, public release, enrollment apply/update, protected
repo work, and mail containing sensitive payloads fail closed unless a named
human bypass is recorded.

Named bypass records can be written even when the hub cannot resolve:

```powershell
asset-dir dad unavailable-ack --operation <operation> --reason "<reason>" --reviewed-by <human>
```

When the hub is available, this appends to the hub audit log. When the hub is
unavailable, it appends to the user-local fallback audit at
`~/.dad/audit/unavailable-acks.jsonl`, or to `--audit-output <jsonl>` when a
test or operator needs an explicit local file. The acknowledgement is an audit
record only; it does not approve broad writes, enrollment, public release, or
sensitive mail by itself.

This policy lets agents work locally without pretending DAD is deployed while
still blocking the operations that can mutate other repos or move sensitive
context.
