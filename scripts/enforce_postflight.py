#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Block push while a repository has open Digital Asset Directory sessions."
    )
    parser.add_argument("--hub", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.hub.resolve() / "src"))
    from digital_asset_directory.governance import enforce_postflight

    ok, message = enforce_postflight(args.hub.resolve(), args.repo.resolve())
    print(message)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
