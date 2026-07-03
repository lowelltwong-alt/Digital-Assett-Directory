#!/usr/bin/env python3
"""Preview or apply this pack's overlay into a repository.

Default is dry-run. Use --apply to copy files.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[1]
OVERLAY = PACK_ROOT / "overlay"


def iter_overlay_files():
    for path in sorted(OVERLAY.rglob("*")):
        if path.is_file():
            yield path, path.relative_to(OVERLAY)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--apply", action="store_true", help="Actually copy files. Default is dry-run.")
    parser.add_argument("--dry-run", action="store_true", help="Preview copy operations. This is the default.")
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"{mode}: overlay {OVERLAY} -> {repo}")

    for src, rel in iter_overlay_files():
        dest = repo / rel
        exists = dest.exists()
        print(f"{'COPY' if args.apply else 'WOULD COPY'} {rel} {'(overwrite)' if exists else ''}")
        if args.apply:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
