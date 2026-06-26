from __future__ import annotations

import ast
import re
from pathlib import PurePosixPath
from typing import Any

CODE_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".cs",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".sh",
    ".ps1",
    ".sql",
}


def _normalized_path(path: str) -> str:
    return path.replace("\\", "/").lower()


def _lines(text: str) -> list[str]:
    return text.splitlines()


def _non_empty_lines(text: str) -> int:
    return sum(1 for line in _lines(text) if line.strip())


def _public_name(name: str) -> bool:
    return bool(name) and not name.startswith("_")


def _python_symbols(text: str) -> dict[str, int]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {"import_count": 0, "function_count": 0, "class_count": 0, "public_symbol_count": 0}
    import_count = 0
    function_count = 0
    class_count = 0
    public_symbol_count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            import_count += 1
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            function_count += 1
            if _public_name(node.name):
                public_symbol_count += 1
        elif isinstance(node, ast.ClassDef):
            class_count += 1
            if _public_name(node.name):
                public_symbol_count += 1
    return {
        "import_count": import_count,
        "function_count": function_count,
        "class_count": class_count,
        "public_symbol_count": public_symbol_count,
    }


def _regex_symbols(text: str) -> dict[str, int]:
    import_count = len(
        re.findall(r"^\s*(import|from|use|using|require|const\s+.+require)\b", text, re.M)
    )
    function_count = len(
        re.findall(r"^\s*(def|function|func|fn)\s+[A-Za-z_][A-Za-z0-9_]*", text, re.M)
    )
    class_count = len(re.findall(r"^\s*(class|interface|struct)\s+[A-Za-z_]", text, re.M))
    public_symbol_count = function_count + class_count
    return {
        "import_count": import_count,
        "function_count": function_count,
        "class_count": class_count,
        "public_symbol_count": public_symbol_count,
    }


def classify_code_role(logical_path: str, text: str = "") -> str:
    normalized = _normalized_path(logical_path)
    name = PurePosixPath(normalized).name
    parts = set(PurePosixPath(normalized).parts)
    if name in {"__init__.py", "__main__.py"}:
        return "package_marker" if name == "__init__.py" else "entrypoint_wrapper"
    if "tests" in parts or name.startswith("test_") or name.endswith("_test.py"):
        return "test_support"
    if "scripts" in parts or name.endswith(".sh") or name.endswith(".ps1"):
        return "script"
    if name in {"cli.py", "api.py"} or name.startswith("cli_"):
        return "entrypoint"
    if any(term in name for term in ("validator", "gateway", "ingestion", "loader")):
        return "runtime_core"
    if any(term in name for term in ("store", "util", "ports", "context")):
        return "support_module"
    if _non_empty_lines(text) >= 120:
        return "runtime_core"
    return "module"


def classify_workflow_subtype(logical_path: str, text: str = "") -> str:
    normalized = _normalized_path(logical_path)
    name = PurePosixPath(normalized).name
    text_lower = text.lower()
    path_parts = set(PurePosixPath(normalized).parts)
    if "archive" in path_parts or "zips" in path_parts or "main-clean-" in normalized:
        return "archive_or_pinned_copy"
    if "/.ci-contracts/" in normalized or "/90_ai_tooling_and_temp/" in normalized:
        return "archive_or_pinned_copy"
    if name in {"pull_request_template.md", "bug_report.md", "documentation_request.md"}:
        return "issue_or_pr_template"
    if "issue_template" in path_parts or "pull_request_template" in name:
        return "issue_or_pr_template"
    if name == "codeowners":
        return "ownership_metadata"
    if "rulesets" in path_parts or name.endswith(".ruleset.json"):
        return "ruleset_config"
    if ".github" in path_parts and "workflows" in path_parts:
        if re.search(r"\b(run|uses):\s+", text_lower) and any(
            term in text_lower
            for term in ("pytest", "validate", "check", "build", "schema", "shacl")
        ):
            return "ci_validation_workflow"
        return "ci_workflow_wrapper"
    if "workflow" in name or "workflows" in path_parts:
        return "governance_workflow_doc"
    if "registry" in path_parts or name.endswith((".json", ".yaml", ".yml")):
        return "registry_or_config_wrapper"
    return "workflow_unspecified"


def build_content_profile(logical_path: str, text: str, asset_type: str) -> dict[str, Any]:
    lines = _lines(text)
    non_empty = _non_empty_lines(text)
    suffix = PurePosixPath(_normalized_path(logical_path)).suffix
    if suffix == ".py":
        symbols = _python_symbols(text)
    elif suffix in CODE_SUFFIXES:
        symbols = _regex_symbols(text)
    else:
        symbols = {
            "import_count": 0,
            "function_count": 0,
            "class_count": 0,
            "public_symbol_count": 0,
        }
    profile: dict[str, Any] = {
        "line_count": len(lines),
        "non_empty_line_count": non_empty,
        "char_count": len(text),
        "code_like": suffix in CODE_SUFFIXES,
        "import_count": symbols["import_count"],
        "function_count": symbols["function_count"],
        "class_count": symbols["class_count"],
        "public_symbol_count": symbols["public_symbol_count"],
        "methodology": "bounded deterministic text/code/workflow feature extraction",
    }
    if asset_type == "code" or suffix in CODE_SUFFIXES:
        profile["code_role"] = classify_code_role(logical_path, text)
    if asset_type == "workflow" or "workflow" in _normalized_path(logical_path):
        profile["workflow_subtype"] = classify_workflow_subtype(logical_path, text)
    return profile
