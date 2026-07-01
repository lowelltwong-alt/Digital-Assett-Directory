#!/usr/bin/env python3
"""Deploy AI engineering preflight files from the asset directory into a target repo.

Default mode is dry-run. Use --apply to write files.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

MANAGED_ID = 'AI_ENGINEERING_PREFLIGHT_ASSET'
BEGIN = f'<!-- BEGIN {MANAGED_ID} -->'
END = f'<!-- END {MANAGED_ID} -->'


@dataclass(frozen=True)
class WritePlan:
    target: Path
    content: str
    mode: str  # managed_block or direct


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def asset_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def detect_profile(repo: Path) -> str:
    has_rust = (repo / 'Cargo.toml').exists() or any(repo.rglob('*.rs'))
    has_python = (
        (repo / 'pyproject.toml').exists()
        or (repo / 'setup.py').exists()
        or (repo / 'requirements.txt').exists()
        or any(repo.rglob('*.py'))
    )
    if has_python and has_rust:
        return 'mixed'
    if has_rust:
        return 'rust'
    if has_python:
        return 'python'
    return 'common'


def managed_block(content: str) -> str:
    return f'{BEGIN}\n{content.rstrip()}\n{END}\n'


def merge_managed(existing: str, block: str) -> str:
    if BEGIN in existing and END in existing:
        before = existing.split(BEGIN, 1)[0].rstrip()
        after = existing.split(END, 1)[1].lstrip()
        return f'{before}\n\n{block}\n{after}'.rstrip() + '\n'
    sep = '\n\n' if existing.strip() else ''
    return existing.rstrip() + sep + block


def write_or_preview(plan: WritePlan, apply: bool, force: bool) -> None:
    path = plan.target
    if plan.mode == 'managed_block':
        block = managed_block(plan.content)
        if path.exists():
            final = merge_managed(read(path), block)
            action = 'update-managed-block' if BEGIN in read(path) else 'append-managed-block'
        else:
            final = block
            action = 'create-managed-file'
    else:
        final = plan.content.rstrip() + '\n'
        if path.exists() and not force:
            if read(path) == final:
                action = 'unchanged'
            else:
                candidate = path.with_name(path.name + '.candidate')
                print(f'collision: {path} exists; writing candidate instead: {candidate}')
                path = candidate
                action = 'create-candidate'
        else:
            action = 'create-or-replace'

    print(f'{action}: {path}')
    if apply and action != 'unchanged':
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(final, encoding='utf-8')


def combined_agents(asset: Path, profile: str) -> str:
    parts = [read(asset / 'templates/common/AGENTS.base.md')]
    if profile in {'python', 'mixed'}:
        parts.append(read(asset / 'templates/python/AGENTS.python.md'))
    if profile in {'rust', 'mixed'}:
        parts.append(read(asset / 'templates/rust/AGENTS.rust.md'))
    return '\n\n'.join(part.rstrip() for part in parts) + '\n'


def combined_claude(asset: Path, profile: str) -> str:
    parts = [read(asset / 'templates/common/CLAUDE.base.md')]
    if profile in {'python', 'mixed'}:
        parts.append('Additional Python guidance: read `docs/ai-preflight/PYTHON_PREFLIGHT.md`.')
    if profile in {'rust', 'mixed'}:
        parts.append('Additional Rust guidance: read `docs/ai-preflight/RUST_PREFLIGHT.md`.')
    return '\n\n'.join(part.rstrip() for part in parts) + '\n'


def combined_copilot(asset: Path, profile: str) -> str:
    parts = [read(asset / 'templates/common/copilot-instructions.base.md')]
    if profile in {'python', 'mixed'}:
        parts.append('For Python changes, follow `docs/ai-preflight/PYTHON_PREFLIGHT.md`.')
    if profile in {'rust', 'mixed'}:
        parts.append('For Rust changes, follow `docs/ai-preflight/RUST_PREFLIGHT.md`.')
    return '\n\n'.join(part.rstrip() for part in parts) + '\n'


def direct_docs(asset: Path, repo: Path, profile: str) -> list[WritePlan]:
    plans: list[WritePlan] = []
    source_note = f"""# AI Preflight Asset Source

Installed from asset directory:

```text
{asset}
```

Managed block ID: `{MANAGED_ID}`

Profile deployed: `{profile}`
"""
    plans.append(WritePlan(repo / 'docs/ai-preflight/ASSET_SOURCE.md', source_note, 'direct'))
    plans.append(WritePlan(repo / 'docs/ai-preflight/COMMON_PREFLIGHT.md', read(asset / 'templates/common/PRE_FLIGHT.base.md'), 'direct'))
    if profile in {'python', 'mixed'}:
        plans += [
            WritePlan(repo / 'docs/ai-preflight/PYTHON_PREFLIGHT.md', read(asset / 'templates/python/PRE_FLIGHT.python.md'), 'direct'),
            WritePlan(repo / 'docs/ai-preflight/LONG_SCRIPT_REFACTOR.python.md', read(asset / 'templates/python/LONG_SCRIPT_REFACTOR.python.md'), 'direct'),
            WritePlan(repo / 'docs/ai-preflight/REVIEW_CHECKLIST.python.md', read(asset / 'templates/python/REVIEW_CHECKLIST.python.md'), 'direct'),
        ]
    if profile in {'rust', 'mixed'}:
        plans += [
            WritePlan(repo / 'docs/ai-preflight/RUST_PREFLIGHT.md', read(asset / 'templates/rust/PRE_FLIGHT.rust.md'), 'direct'),
            WritePlan(repo / 'docs/ai-preflight/LONG_MODULE_REFACTOR.rust.md', read(asset / 'templates/rust/LONG_MODULE_REFACTOR.rust.md'), 'direct'),
            WritePlan(repo / 'docs/ai-preflight/REVIEW_CHECKLIST.rust.md', read(asset / 'templates/rust/REVIEW_CHECKLIST.rust.md'), 'direct'),
        ]
    return plans


def claude_skill(asset: Path, profile: str) -> str:
    parts = []
    if profile in {'python', 'mixed'}:
        parts.append(read(asset / 'templates/python/claude_skill/SKILL.md'))
    if profile in {'rust', 'mixed'}:
        parts.append(read(asset / 'templates/rust/claude_skill/SKILL.md'))
    if not parts:
        parts.append("""---\nname: ai-engineering-preflight\ndescription: Use before modifying code in this repository.\n---\n\n# AI Engineering Preflight\n\nRead AGENTS.md and docs/ai-preflight before editing.\n""")
    return '\n\n---\n\n'.join(part.rstrip() for part in parts) + '\n'


def plans_for(asset: Path, repo: Path, profile: str) -> list[WritePlan]:
    if profile == 'auto':
        profile = detect_profile(repo)
    if profile not in {'common', 'python', 'rust', 'mixed'}:
        raise SystemExit(f'Unsupported profile: {profile}')
    print(f'detected/profile: {profile}')

    plans: list[WritePlan] = [
        WritePlan(repo / 'AGENTS.md', combined_agents(asset, profile), 'managed_block'),
        WritePlan(repo / 'CLAUDE.md', combined_claude(asset, profile), 'managed_block'),
        WritePlan(repo / '.github/copilot-instructions.md', combined_copilot(asset, profile), 'managed_block'),
        WritePlan(repo / '.github/instructions/ai-engineering-preflight.instructions.md', combined_copilot(asset, profile), 'direct'),
        WritePlan(repo / '.cursor/rules/ai-engineering-preflight.mdc', read(asset / 'templates/common/cursor-rule.base.mdc'), 'direct'),
        WritePlan(repo / '.claude/skills/ai-engineering-preflight/SKILL.md', claude_skill(asset, profile), 'direct'),
    ]
    plans.extend(direct_docs(asset, repo, profile))
    return plans


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--asset', type=Path, default=asset_root_from_script())
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--profile', choices=['auto', 'common', 'python', 'rust', 'mixed'], default='auto')
    parser.add_argument('--apply', action='store_true', help='write files; otherwise dry-run')
    parser.add_argument('--force', action='store_true', help='replace direct files instead of writing .candidate files')
    args = parser.parse_args()

    asset = args.asset.resolve()
    repo = args.repo.resolve()
    if not (asset / 'asset.json').exists():
        raise SystemExit(f'Asset root not found: {asset}')
    if not repo.exists():
        raise SystemExit(f'Repo path does not exist: {repo}')

    print(f'asset: {asset}')
    print(f'repo: {repo}')
    print(f'mode: {"APPLY" if args.apply else "DRY-RUN"}')
    for plan in plans_for(asset, repo, args.profile):
        write_or_preview(plan, args.apply, args.force)
    if not args.apply:
        print('\nDry-run only. Re-run with --apply to write files.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
