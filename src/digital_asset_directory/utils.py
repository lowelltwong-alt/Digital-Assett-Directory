from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+.#/-]{1,63}")
SECRET_PATTERNS = [
    re.compile(
        r"(?i)(api[_-]?key|token|secret|password|passwd|client[_-]?secret)"
        r"""["']?\s*[:=]\s*["']?([^\s,;"']+)"""
    ),
    re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        re.S,
    ),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s,;\"']+"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])"),
    re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)"),
]

ATOMIC_WRITE_REPLACE_ATTEMPTS = 10
ATOMIC_WRITE_CLEANUP_ATTEMPTS = 5


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def json_dumps(value: Any, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        indent=2 if pretty else None,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )


def _direct_overwrite_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def atomic_write_text(path: Path, text: str, *, allow_direct_fallback: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        replace_error: PermissionError | None = None
        for attempt in range(ATOMIC_WRITE_REPLACE_ATTEMPTS):
            try:
                os.replace(tmp_name, path)
                replace_error = None
                break
            except PermissionError as exc:
                replace_error = exc
                if attempt == ATOMIC_WRITE_REPLACE_ATTEMPTS - 1:
                    break
                time.sleep(0.05 * (attempt + 1))
        if replace_error is not None and allow_direct_fallback:
            try:
                _direct_overwrite_text(path, text)
            except OSError as fallback_error:
                raise replace_error from fallback_error
        elif replace_error is not None:
            raise replace_error
    finally:
        for attempt in range(ATOMIC_WRITE_CLEANUP_ATTEMPTS):
            try:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
                break
            except PermissionError:
                if attempt == ATOMIC_WRITE_CLEANUP_ATTEMPTS - 1:
                    break
                time.sleep(0.05 * (attempt + 1))
            except OSError:
                break


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json_dumps(value) + "\n")


def write_json(path: Path, value: Any, *, allow_direct_fallback: bool = False) -> None:
    atomic_write_text(
        path,
        json_dumps(value, pretty=True) + "\n",
        allow_direct_fallback=allow_direct_fallback,
    )


def write_jsonl(path: Path, values: Iterable[Any], *, allow_direct_fallback: bool = False) -> None:
    text = "".join(json_dumps(value) + "\n" for value in values)
    atomic_write_text(path, text, allow_direct_fallback=allow_direct_fallback)


def redact_sensitive_text(text: str) -> tuple[str, int]:
    count = 0
    redacted = text
    for pattern in SECRET_PATTERNS:

        def repl(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            if match.lastindex and match.lastindex >= 1 and match.lastindex == 2:
                return f"{match.group(1)}=[REDACTED]"
            return "[REDACTED_SECRET]"

        redacted = pattern.sub(repl, redacted)
    return redacted, count


def tokens(text: str) -> set[str]:
    stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "into",
        "your",
        "you",
        "are",
        "not",
        "will",
        "all",
        "use",
        "using",
        "has",
        "have",
        "can",
        "its",
        "but",
        "our",
        "file",
        "files",
        "repo",
        "repository",
        "readme",
        "http",
        "https",
        "www",
        "com",
    }
    return {
        m.group(0).lower().strip("_./-+") for m in WORD_RE.finditer(text) if len(m.group(0)) > 2
    } - stop


def jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a, b = set(left), set(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def idf_weights(token_sets: Iterable[Iterable[str]]) -> dict[str, float]:
    sets = [set(values) for values in token_sets]
    if not sets:
        return {}
    document_count = len(sets)
    df: Counter[str] = Counter(token for values in sets for token in values)
    return {
        token: math.log((document_count + 1) / (count + 1)) + 1.0
        for token, count in df.items()
    }


def idf_weighted_cosine(
    left: Iterable[str], right: Iterable[str], weights: dict[str, float]
) -> float:
    left_tokens = set(left)
    right_tokens = set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    shared = left_tokens & right_tokens
    if not shared:
        return 0.0
    numerator = sum(weights.get(token, 1.0) ** 2 for token in shared)
    left_norm = math.sqrt(sum(weights.get(token, 1.0) ** 2 for token in left_tokens))
    right_norm = math.sqrt(sum(weights.get(token, 1.0) ** 2 for token in right_tokens))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def rarest_tokens(tokens_: Iterable[str], weights: dict[str, float], limit: int) -> list[str]:
    return sorted(set(tokens_), key=lambda token: (-weights.get(token, 1.0), token))[:limit]


def split_multi(values: list[str] | tuple[str, ...] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        for part in re.split(r"[,;\n]", value):
            cleaned = part.strip()
            if cleaned:
                result.append(cleaned)
    return result


def safe_relative(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except (ValueError, OSError):
        return path.name


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "registry").exists():
            return candidate
        if (candidate / ".git").exists():
            return candidate
    return current
