#!/usr/bin/env python3
"""Runner for the DAD contract check usable from hooks and CI.

Dependency-light: stdlib + PyYAML. Exit codes: 0 clean or warn-mode finding;
2 enforce-mode violation or infrastructure failure; never nonzero for
infrastructure problems in effective warn mode (a broken checker must not
block work during probation).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="DAD contract check")
    parser.add_argument("--hub", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--mode", choices=["warn", "enforce", "policy"], default="policy")
    parser.add_argument(
        "--extra-text-env",
        default="",
        help="Environment variable holding extra text to scan (e.g. a PR body).",
    )
    args = parser.parse_args()

    hub = args.hub.resolve()
    sys.path.insert(0, str(hub / "src"))
    # If policy loading itself fails, policy mode must fail closed because the
    # reviewed effective mode cannot be established. Explicit warn remains the
    # only non-blocking infrastructure posture.
    selected_mode = "enforce" if args.mode == "policy" else args.mode
    try:
        from digital_asset_directory.contract_check import (
            effective_mode,
            load_policy,
            render_text,
            resolve_base,
            run_contract_check,
        )

        policy = load_policy(hub)
        selected_mode = effective_mode(policy, args.mode)
        repo = args.repo.resolve()
        base = args.base or resolve_base(repo, args.head)
        extra_text = os.environ.get(args.extra_text_env, "") if args.extra_text_env else ""
        report = run_contract_check(
            repo, hub, base, args.head, extra_text=extra_text, mode=selected_mode
        )
        print(render_text(report))
        if report["violation"] and report["mode"] == "enforce":
            return 2
        return 0
    except Exception as exc:  # noqa: BLE001
        if selected_mode == "enforce":
            print(f"DAD contract check failed to run in enforce mode: {exc}")
            return 2
        print(f"DAD contract check could not run ({exc}); not blocking during probation.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
