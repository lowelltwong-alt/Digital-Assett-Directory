#!/usr/bin/env python3
"""Install this asset into a central asset directory.

Default mode is dry-run. Use --apply to write files.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

IGNORE_NAMES = {'.git', '__pycache__'}


def iter_files(root: Path):
    for path in sorted(root.rglob('*')):
        if any(part in IGNORE_NAMES for part in path.parts):
            continue
        if path.is_file():
            yield path


def copy_tree(source: Path, target: Path, apply: bool, force: bool) -> None:
    if not (source / 'asset.json').exists():
        raise SystemExit(f'Not an asset root: {source}')

    for src in iter_files(source):
        rel = src.relative_to(source)
        dst = target / rel
        action = 'copy'
        if dst.exists() and not force:
            if src.read_bytes() == dst.read_bytes():
                action = 'unchanged'
            else:
                action = 'skip-existing(use --force to replace)'
        print(f'{action}: {rel}')
        if apply and action == 'copy':
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        elif apply and action == 'unchanged':
            pass
        elif apply and action.startswith('skip'):
            pass
        elif apply and force:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='write files; otherwise dry-run')
    parser.add_argument('--force', action='store_true', help='replace existing differing files')
    args = parser.parse_args()

    print(f'source: {args.source}')
    print(f'target: {args.target}')
    print(f'mode: {"APPLY" if args.apply else "DRY-RUN"}')
    copy_tree(args.source.resolve(), args.target.resolve(), args.apply, args.force)
    if not args.apply:
        print('\nDry-run only. Re-run with --apply to write files.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
