#!/usr/bin/env python3
"""Deploy the preflight asset to multiple repositories.

Default mode is dry-run. Use --apply to write files.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def asset_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def read_repos(path: Path) -> list[tuple[Path, str | None]]:
    if path.suffix.lower() == '.json':
        data = json.loads(path.read_text(encoding='utf-8'))
        return [(Path(item['path']), item.get('profile')) for item in data.get('repos', [])]
    repos = []
    for line in path.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if ',' in stripped:
            repo_path, profile = [part.strip() for part in stripped.split(',', 1)]
            repos.append((Path(repo_path), profile))
        else:
            repos.append((Path(stripped), None))
    return repos


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--asset', type=Path, default=asset_root_from_script())
    parser.add_argument('--repos-file', type=Path, required=True)
    parser.add_argument('--profile', choices=['auto', 'common', 'python', 'rust', 'mixed'], default='auto')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()

    deploy = args.asset.resolve() / 'scripts' / 'deploy_to_repo.py'
    if not deploy.exists():
        raise SystemExit(f'Deploy script not found: {deploy}')

    failures = 0
    for repo, override_profile in read_repos(args.repos_file):
        profile = override_profile or args.profile
        cmd = [sys.executable, str(deploy), '--asset', str(args.asset.resolve()), '--repo', str(repo), '--profile', profile]
        if args.apply:
            cmd.append('--apply')
        if args.force:
            cmd.append('--force')
        print('\n' + '=' * 80)
        print(f'repo: {repo}')
        print(f'profile: {profile}')
        print('command:', ' '.join(cmd))
        result = subprocess.run(cmd, text=True)
        if result.returncode != 0:
            failures += 1
            print(f'FAILED: {repo} returned {result.returncode}')
    print('\n' + '=' * 80)
    print(f'completed with {failures} failure(s)')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
