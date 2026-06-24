from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from .utils import utc_now, write_json


def run_orphan_radar(
    repo_root: Path, source: Path, executable: str = "orphan-radar"
) -> dict[str, Any]:
    if not shutil.which(executable):
        raise RuntimeError(
            "orphan-radar executable was not found. Install the sibling repository first or supply --executable."
        )
    output = repo_root / "raw" / "events" / f"orphan-radar-{utc_now().replace(':', '-')}"
    result = subprocess.run(
        [executable, "scan", "--src", str(source), "--out", str(output)],
        capture_output=True,
        text=True,
        check=False,
        timeout=1800,
    )
    payload = {
        "created_at": utc_now(),
        "source": str(source),
        "output": str(output),
        "returncode": result.returncode,
        "stdout": result.stdout[-10000:],
        "stderr": result.stderr[-10000:],
    }
    write_json(output / "adapter_run.json", payload)
    if result.returncode:
        raise RuntimeError(
            f"orphan-radar failed with code {result.returncode}: {result.stderr[-1000:]}"
        )
    return payload
