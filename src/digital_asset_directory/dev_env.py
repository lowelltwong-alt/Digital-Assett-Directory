"""Development-environment readiness check.

Detects a common failure mode: a `.venv` (or other interpreter) that lacks the
declared `[project.optional-dependencies] dev` extras, so `python -m pytest`
fails with ``No module named pytest``. This module only *detects and reports*;
it never installs packages (installing is a human-gated action).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

# Import name -> the pip/distribution hint it belongs to. Runtime deps are
# always required; the pytest/testmon/picked hints come from the `dev` extra.
RUNTIME_MODULES = ["yaml", "jsonschema", "typer", "pydantic", "networkx", "requests"]
DEV_MODULES = {
    "pytest": "pytest (dev extra) — required to run the test suite",
    "pytest_testmon": "pytest-testmon (dev extra)",
    "pytest_picked": "pytest-picked (dev extra)",
}
RECOVERY_COMMAND = 'python -m pip install -e ".[dev]"'


def _importable(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def dev_environment_status() -> dict[str, Any]:
    """Report interpreter + which runtime/dev modules are importable."""
    runtime_missing = [m for m in RUNTIME_MODULES if not _importable(m)]
    dev_missing = [m for m in DEV_MODULES if not _importable(m)]
    can_run_tests = "pytest" not in dev_missing
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    ok = not runtime_missing and can_run_tests
    recovery: list[str] = []
    if runtime_missing or dev_missing:
        recovery.append(f"Install the package with dev extras: {RECOVERY_COMMAND}")
        if not in_venv:
            recovery.append(
                "You are not in a virtual environment; activate the project's .venv "
                "first (or create one) so extras land where the tests run."
            )
    return {
        "schema_version": "dad.dev_env.v1",
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "in_virtualenv": in_venv,
        "runtime_modules_missing": runtime_missing,
        "dev_modules_missing": dev_missing,
        "can_run_pytest": can_run_tests,
        "ok": ok,
        "recovery_command": RECOVERY_COMMAND,
        "recovery": recovery,
        "note": (
            "This check never installs packages. If dev extras are missing, run the "
            "recovery command yourself in the intended interpreter."
        ),
        "supported_dev_env": {
            "python": ">=3.11",
            "install": RECOVERY_COMMAND,
            "run_tests": "$env:PYTHONPATH='src'; python -m pytest  (PowerShell)",
            "validate": "python -m digital_asset_directory.cli validate",
        },
    }
