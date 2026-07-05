#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
[ -f config/sources.local.yaml ] || cp config/sources.example.yaml config/sources.local.yaml
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
DAD_BIN="${HOME}/.dad/bin"
mkdir -p "$DAD_BIN"
cat > "$DAD_BIN/asset-dir" <<EOF
#!/usr/bin/env sh
exec "$ROOT/.venv/bin/python" -m digital_asset_directory.cli "\$@"
EOF
chmod +x "$DAD_BIN/asset-dir"
"$DAD_BIN/asset-dir" doctor --hub "$ROOT" --scope deployment --write-hub-locator
.venv/bin/python -m digital_asset_directory.cli validate --hub "$ROOT"
.venv/bin/python -m digital_asset_directory.cli roadmap check --hub "$ROOT" --no-update
.venv/bin/python -m pytest
printf '%s\n' "Bootstrap complete. Stable shim written to $DAD_BIN/asset-dir. Add $DAD_BIN to PATH or call the shim directly."
