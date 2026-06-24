#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
"$ROOT/.venv/bin/python" -m digital_asset_directory.cli scan --hub "$ROOT" "$@"
