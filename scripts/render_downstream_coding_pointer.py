from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HUB = "../Digital-Assett-Directory"
TEMPLATE = ROOT / "templates" / "downstream" / "AI_ASSETS_POINTER.template.json"


def render_pointer(hub: str) -> dict[str, Any]:
    payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    previous_hub = payload["hub"].rstrip("/\\")
    hub = hub.rstrip("/\\").replace("\\", "/")
    payload["hub"] = hub
    for asset in payload.get("assets", []):
        source = asset.get("source", "")
        if source.startswith(previous_hub):
            asset["source"] = hub + source[len(previous_hub) :]
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a downstream DAD coding asset pointer.")
    parser.add_argument("--hub", default=DEFAULT_HUB, help="Path from target repo to DAD hub.")
    parser.add_argument("--output", help="Optional output path. Defaults to stdout.")
    parser.add_argument("--force", action="store_true", help="Allow overwriting an existing output file.")
    args = parser.parse_args()

    rendered = json.dumps(render_pointer(args.hub), indent=2, sort_keys=False) + "\n"
    if not args.output:
        print(rendered, end="")
        return 0

    output = Path(args.output)
    if output.exists() and not args.force:
        raise SystemExit(f"Refusing to overwrite existing file without --force: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
