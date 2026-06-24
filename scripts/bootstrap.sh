#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
[ -f config/sources.local.yaml ] || cp config/sources.example.yaml config/sources.local.yaml
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m digital_asset_directory.cli validate --hub "$ROOT"
.venv/bin/python -m digital_asset_directory.cli roadmap check --hub "$ROOT"
.venv/bin/python -m pytest
