#!/usr/bin/env python3
"""Thin Python wrapper for DAD's Rust scanner core.

This wrapper intentionally keeps Python as the orchestration boundary. It does
not parse DAD config yet; first use it for smoke tests and explicit arguments.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-path", default="tools/dad_scan_core/Cargo.toml")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--source-id")
    parser.add_argument("--path-alias")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--quarantine-out", type=Path)
    parser.add_argument("--max-files", type=int, default=None)
    parser.add_argument("--max-content-hash-bytes", type=int, default=10_485_760)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--print-command", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.source is None:
        parser.print_help()
        return 0

    required = ["source_id", "path_alias", "out", "summary_out", "quarantine_out"]
    missing = [name.replace("_", "-") for name in required if getattr(args, name) in (None, "")]
    if missing:
        parser.error("Missing required scan options: " + ", ".join(missing))

    cmd = [
        "cargo",
        "run",
        "--manifest-path",
        args.manifest_path,
        "--",
        "scan-local",
        "--source",
        str(args.source),
        "--source-id",
        args.source_id,
        "--path-alias",
        args.path_alias,
        "--out",
        str(args.out),
        "--summary-out",
        str(args.summary_out),
        "--quarantine-out",
        str(args.quarantine_out),
        "--max-content-hash-bytes",
        str(args.max_content_hash_bytes),
    ]
    if args.max_files is not None:
        cmd.extend(["--max-files", str(args.max_files)])

    if args.print_command:
        print(" ".join(cmd))

    try:
        return subprocess.run(cmd, check=False, timeout=args.timeout_seconds).returncode
    except FileNotFoundError:
        print("cargo was not found on PATH. Install Rust via rustup before running this wrapper.", file=sys.stderr)
        return 127
    except subprocess.TimeoutExpired:
        print(
            f"dad_scan_core timed out after {args.timeout_seconds} seconds.",
            file=sys.stderr,
        )
        return 124


if __name__ == "__main__":
    raise SystemExit(main())
