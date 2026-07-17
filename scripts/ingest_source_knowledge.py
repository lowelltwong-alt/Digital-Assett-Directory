from __future__ import annotations

import argparse
import json
from pathlib import Path

from digital_asset_directory.source_knowledge_ingestion import build_snapshot, validate_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or validate a governed DAD source-knowledge snapshot.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--source-root", type=Path, required=True)
    build.add_argument("--destination", type=Path, required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    result = (
        build_snapshot(args.source_root, args.destination)
        if args.command == "build"
        else validate_snapshot(args.destination)
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if args.command == "build" or result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
