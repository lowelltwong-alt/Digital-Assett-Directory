"""Provider-neutral line structuring core for the Portfolio OS capture inbox.

The core accepts already-observed lines and returns candidate records. It owns
no filesystem path, runtime, scheduler, model, workstream, or execution action.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Iterable

from .portfolio_events import minimize_text

CANDIDATE_SCHEMA_VERSION = "dad.portfolio_capture_candidate.v1"
CORE_RESULT_SCHEMA_VERSION = "dad.portfolio_capture_core_result.v1"

AUTHORITY_BOUNDARY = (
    "Structured captures are local candidate evidence that requires human review. "
    "The core cannot create or change workstreams, dispatch an agent, schedule a "
    "routine, mutate a source inbox, write a repository, or grant authority."
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CaptureCoreLimits:
    """Hard budgets for one provider-neutral line-structuring pass."""

    max_lines: int = 500
    max_line_chars: int = 2_000

    def __post_init__(self) -> None:
        if not 1 <= self.max_lines <= 10_000:
            raise ValueError("max_lines must be between 1 and 10000")
        if not 32 <= self.max_line_chars <= 20_000:
            raise ValueError("max_line_chars must be between 32 and 20000")


def _digest_text(text: str) -> str:
    return "sha256:" + sha256(text.encode("utf-8")).hexdigest()


def structure_capture_lines(
    lines: Iterable[str],
    *,
    source_fingerprint: str,
    captured_at: str,
    limits: CaptureCoreLimits | None = None,
) -> dict[str, Any]:
    """Return bounded, redacted capture candidates without performing effects.

    Any exhausted budget fails the whole batch closed. Partial lines are never
    promoted into candidate records, because doing so would create false intent.
    """

    limits = limits or CaptureCoreLimits()
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    blank_line_count = 0
    duplicate_line_count = 0
    redaction_count = 0
    observed_line_count = 0
    problems: list[str] = []

    for line_number, raw in enumerate(lines, start=1):
        observed_line_count = line_number
        if line_number > limits.max_lines:
            problems.append("line_budget_exhausted")
            break
        if not isinstance(raw, str):
            problems.append("non_text_line")
            break
        text = raw.rstrip("\r\n")
        if len(text) > limits.max_line_chars:
            problems.append("line_length_budget_exhausted")
            break
        minimized, count = minimize_text(text.strip())
        minimized = " ".join(minimized.split())
        redaction_count += count
        if not minimized:
            blank_line_count += 1
            continue
        text_digest = _digest_text(minimized.casefold())
        candidate_id = "dad:capture-candidate:" + text_digest.split(":", 1)[1]
        if candidate_id in seen:
            duplicate_line_count += 1
            continue
        seen.add(candidate_id)
        candidates.append(
            {
                "schema_version": CANDIDATE_SCHEMA_VERSION,
                "candidate_id": candidate_id,
                "captured_at": captured_at,
                "source_fingerprint": source_fingerprint,
                "source_line_number": line_number,
                "text": minimized,
                "text_fingerprint": text_digest,
                "redaction_count": count,
                "status": "needs_human_decision",
                "recommended_action": "review_with_dad_work_router",
                "candidate_only": True,
                "execution_authorized": False,
                "authority_boundary": AUTHORITY_BOUNDARY,
            }
        )

    complete = not problems
    if not complete:
        candidates = []
    return {
        "schema_version": CORE_RESULT_SCHEMA_VERSION,
        "status": "complete_candidate" if complete else "partial_candidate",
        "captured_at": captured_at,
        "source_fingerprint": source_fingerprint if complete else "",
        "candidates": candidates,
        "summary": {
            "observed_line_count": observed_line_count,
            "candidate_count": len(candidates),
            "blank_line_count": blank_line_count,
            "duplicate_line_count": duplicate_line_count,
            "redaction_count": redaction_count,
        },
        "coverage": {
            "complete": complete,
            "problems": sorted(set(problems)),
            "budgets": {
                "max_lines": limits.max_lines,
                "max_line_chars": limits.max_line_chars,
            },
        },
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


__all__ = [
    "AUTHORITY_BOUNDARY",
    "CANDIDATE_SCHEMA_VERSION",
    "CORE_RESULT_SCHEMA_VERSION",
    "CaptureCoreLimits",
    "structure_capture_lines",
]
