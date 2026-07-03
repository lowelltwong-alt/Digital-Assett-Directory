from __future__ import annotations

import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class DadScanCoreResult:
    """Structured result from DAD's Rust scan core."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    cargo_found: bool
    source: str
    out: str
    summary_out: str
    quarantine_out: str

    def to_dict(self, *, include_output: bool = False) -> dict[str, object]:
        payload = asdict(self)
        if not include_output:
            payload["stdout"] = ""
            payload["stderr"] = ""
            payload["output_suppressed"] = True
        else:
            payload["output_suppressed"] = False
        return payload


def run_dad_scan_core(
    *,
    repo_root: Path,
    source: Path,
    source_id: str,
    path_alias: str,
    out: Path,
    summary_out: Path,
    quarantine_out: Path,
    max_files: int | None = None,
    max_content_hash_bytes: int = 10_485_760,
    follow_symlinks: bool = False,
    excludes: list[str] | None = None,
    cargo_bin: str = "cargo",
    manifest_path: Path | None = None,
) -> DadScanCoreResult:
    """Run the Rust scanner through Cargo and return a structured subprocess result.

    The Rust scanner owns deterministic file walking and hashing only. Python keeps
    orchestration, policy, ingestion, and review authority.
    """

    repo_root = repo_root.resolve()
    source = _resolve(repo_root, source)
    out = _resolve(repo_root, out)
    summary_out = _resolve(repo_root, summary_out)
    quarantine_out = _resolve(repo_root, quarantine_out)
    manifest_path = (
        _resolve(repo_root, manifest_path)
        if manifest_path is not None
        else repo_root / "tools" / "dad_scan_core" / "Cargo.toml"
    )

    command = [
        cargo_bin,
        "run",
        "--manifest-path",
        str(manifest_path),
        "--",
        "scan-local",
        "--source",
        str(source),
        "--source-id",
        source_id,
        "--path-alias",
        path_alias,
        "--out",
        str(out),
        "--summary-out",
        str(summary_out),
        "--quarantine-out",
        str(quarantine_out),
        "--max-content-hash-bytes",
        str(max_content_hash_bytes),
    ]
    if max_files is not None:
        command.extend(["--max-files", str(max_files)])
    if follow_symlinks:
        command.append("--follow-symlinks")
    for pattern in excludes or []:
        command.extend(["--exclude", pattern])

    cargo_path = shutil.which(cargo_bin)
    if cargo_path is None:
        return DadScanCoreResult(
            command=command,
            returncode=127,
            stdout="",
            stderr=f"{cargo_bin} was not found on PATH. Install Rust via rustup.",
            cargo_found=False,
            source=str(source),
            out=str(out),
            summary_out=str(summary_out),
            quarantine_out=str(quarantine_out),
        )

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    return DadScanCoreResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        cargo_found=True,
        source=str(source),
        out=str(out),
        summary_out=str(summary_out),
        quarantine_out=str(quarantine_out),
    )


def _resolve(repo_root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (repo_root / path).resolve()
