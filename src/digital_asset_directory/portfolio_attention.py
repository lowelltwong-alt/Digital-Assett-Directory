"""Portfolio OS attention core: lifecycle state machine, triggers, board.

Replaces the audited draft's flag-scan fold with:

* an explicit **last-event-wins lifecycle state machine** with a legal
  transition table (audit C6/C7 — terminal states are now reachable and a
  later snooze always beats an earlier resume);
* **trigger signatures** (mechanism M3): dismissal suppresses a specific
  trigger on a workstream, not the workstream itself, and interrupt-tier
  triggers are never suppressed by dismissal;
* **dismissal-to-decision convergence** (M2): at the policy threshold the
  kernel proposes an explicit incubation decision instead of decaying into
  priority soup or silent suppression;
* an **AttentionPolicy** actually threaded through the fold (C14);
* a **dependency rollup and board projection** (M7): ``depends_on``/``blocks``
  assertions become transitive blocking counts and lifecycle columns —
  deterministic graph math with reasons, never a score;
* **coverage honesty** (M5): "no trigger" and "could not evaluate" are
  different outputs.

Priority constants are ordinal ranks, not calibrated scores (methodology note
in the constants block). Everything here is deterministic; no model calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, Iterable

from .ids import stable_id

# Ordinal priority ranks. Methodology: these are display-ordering ranks inside
# three human tiers (interrupt > nudge > weekly); the absolute numbers carry no
# meaning beyond stable ordering, are not probabilities, and never authorize an
# action. Calibration input is the per-class accept-rate stats surfaced in the
# state output; a rank change should cite them.
PRIORITY_BLOCKER = 90
PRIORITY_CONFLICT = 85
PRIORITY_NUDGE_RELATED_IDLE = 70
PRIORITY_WEEKLY_DECISION = 60
PRIORITY_DECISION_PROPOSED = 55
PRIORITY_INCUBATION_REVIEW = 50
CLASS_DECAY_PENALTY = 15
MAX_TODAY = 3

LIFECYCLE_STATES = (
    "proposed",
    "active",
    "paused",
    "snoozed",
    "incubating",
    "merged",
    "superseded",
    "archived",
)
TERMINAL_STATES = frozenset({"merged", "superseded", "archived"})

FEEDBACK_ACTIONS = (
    "resume",
    "keep",
    "snooze",
    "incubate",
    "pause",
    "dismiss",
    "reject_decision",
    "merge",
    "supersede",
    "archive",
)

_ACTION_TO_STATE = {
    "resume": "active",
    "keep": "active",
    "snooze": "snoozed",
    "incubate": "incubating",
    "pause": "paused",
    "merge": "merged",
    "supersede": "superseded",
    "archive": "archived",
}

# Legal transitions. Terminal states are re-openable only by an explicit
# resume; everything else is append-recorded but ignored with a diagnostic.
_OPEN_STATES = frozenset({"proposed", "active", "paused", "snoozed", "incubating"})
LIFECYCLE_TRANSITIONS: dict[str, frozenset[str]] = {
    state: frozenset(_ACTION_TO_STATE) for state in _OPEN_STATES
}
LIFECYCLE_TRANSITIONS.update({state: frozenset({"resume"}) for state in TERMINAL_STATES})

TRIGGER_KINDS = (
    "blocker",
    "conflict_decision",
    "related_active_idle",
    "weekly_decision",
    "incubation_review",
    "decision_proposed",
)
_INTERRUPT_KINDS = frozenset({"blocker", "conflict_decision"})


@dataclass(frozen=True, slots=True, kw_only=True)
class AttentionPolicy:
    """Humane-attention thresholds, threaded through the fold (fixes C14)."""

    stale_days: int = 3
    weekly_days: int = 7
    incubation_review_days: int = 30
    dismiss_cooldown_days: int = 3
    dismiss_decision_threshold: int = 3
    decay_min_samples: int = 3
    decay_max_accept_rate: float = 0.4

    def __post_init__(self) -> None:
        if self.stale_days < 1 or self.weekly_days < self.stale_days:
            raise ValueError("Require 1 <= stale_days <= weekly_days.")
        if self.incubation_review_days < 1:
            raise ValueError("incubation_review_days must be at least 1.")
        if self.dismiss_cooldown_days < 1 or self.dismiss_decision_threshold < 1:
            raise ValueError("Dismissal cooldown and threshold must be at least 1.")


def trigger_signature(
    workstream_id: str,
    trigger_kind: str,
    material_inputs: dict[str, Any] | None = None,
) -> str:
    """Return a stable signature for one materially distinct trigger epoch.

    Inputs must already be discretized: day-level review dates, coarse idle
    bands, normalized blocker text, sorted relation labels, and the explicit
    dismissal epoch. Raw timestamps are deliberately excluded so cooldowns do
    not churn while a reason is materially unchanged.
    """

    canonical_inputs = json.dumps(
        material_inputs or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return stable_id("portfolio-trigger", workstream_id, trigger_kind, canonical_inputs)


def _idle_band(inactive_days: int | None, policy: AttentionPolicy) -> str:
    """Discretize idle age without making signatures change every day."""

    if not isinstance(inactive_days, int):
        return "unknown"
    if inactive_days < policy.weekly_days:
        return "stale"
    if inactive_days < 30:
        return "weekly"
    if inactive_days < 90:
        return "monthly"
    return "quarterly_plus"


def parse_dt(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def days_since(value: str, now: datetime) -> int | None:
    parsed = parse_dt(value)
    if parsed is None:
        return None
    return max(0, int((now - parsed).total_seconds() // 86_400))


def latest_iso(*values: str) -> str:
    best_value = ""
    best_dt: datetime | None = None
    for value in values:
        parsed = parse_dt(value)
        if parsed is not None and (best_dt is None or parsed > best_dt):
            best_dt = parsed
            best_value = value
    return best_value


# ---------------------------------------------------------------------------
# Lifecycle state machine (last event wins, in ledger order)
# ---------------------------------------------------------------------------


def fold_lifecycle(
    proposed_at: str,
    stream_events: list[dict[str, Any]],
    diagnostics: list[str],
) -> dict[str, Any]:
    """Fold one workstream's capsule/feedback events into lifecycle state.

    Events arrive in ledger (append) order; each legal event transitions the
    machine, so the *last* event always wins (fixes C6). Illegal transitions
    are recorded as diagnostics and ignored (history is never rewritten).
    """

    state = "proposed"
    since = proposed_at
    snooze_until = ""
    review_at = ""
    capsule: dict[str, Any] | None = None
    dismissals: list[dict[str, Any]] = []
    accepts_like: list[str] = []
    dismissal_epoch = 0
    decision_rejected_at = ""
    last_activity_event_at = proposed_at

    for event in stream_events:
        kind = event.get("event_kind")
        payload = event.get("payload", {})
        recorded_at = str(event.get("recorded_at", ""))
        if kind == "capsule_recorded":
            if state in TERMINAL_STATES:
                diagnostics.append(f"capsule_on_terminal:{event.get('event_id', '')}")
                continue
            capsule = {
                "capsule_id": str(payload.get("capsule_id", "")),
                "pause_reason": str(payload.get("pause_reason", "")),
                "blocker": str(payload.get("blocker", "")),
                "last_check": str(payload.get("last_check", "")),
                "next_action": str(payload.get("next_action", "")),
                "snooze_until": str(payload.get("snooze_until", "")),
                "incubating": bool(payload.get("incubating", False)),
                "review_at": str(payload.get("review_at", "")),
                "recorded_at": recorded_at,
            }
            last_activity_event_at = latest_iso(last_activity_event_at, recorded_at)
            # A capsule may carry an explicit state intent; it never activates
            # implicitly (the audited draft's surprise `next_action -> active`
            # rule is gone).
            if capsule["snooze_until"]:
                state, since, snooze_until = "snoozed", recorded_at, capsule["snooze_until"]
            elif capsule["incubating"]:
                state, since, review_at = "incubating", recorded_at, capsule["review_at"]
            elif capsule["pause_reason"]:
                state, since = "paused", recorded_at
            continue
        if kind != "focus_feedback":
            continue
        action = str(payload.get("action", ""))
        if action not in _ACTION_TO_STATE and action not in {"dismiss", "reject_decision"}:
            diagnostics.append(f"unknown_action:{action}")
            continue
        if action == "dismiss":
            dismissals.append(
                {
                    "recorded_at": recorded_at,
                    "trigger_signature": str(payload.get("trigger_signature", "")),
                }
            )
            continue
        if action == "reject_decision":
            # M2: rejection starts a fresh dismissal epoch. Historical events
            # stay in the ledger, but no longer count toward convergence.
            dismissal_epoch += 1
            dismissals = []
            decision_rejected_at = recorded_at
            last_activity_event_at = latest_iso(last_activity_event_at, recorded_at)
            continue
        if action not in LIFECYCLE_TRANSITIONS.get(state, frozenset()):
            diagnostics.append(f"illegal_transition:{state}->{action}")
            continue
        state = _ACTION_TO_STATE[action]
        since = recorded_at
        snooze_until = str(payload.get("snooze_until", "")) if action == "snooze" else ""
        review_at = str(payload.get("review_at", "")) if action == "incubate" else ""
        last_activity_event_at = latest_iso(last_activity_event_at, recorded_at)
        if action in {"resume", "keep", "merge"}:
            accepts_like.append(action)

    return {
        "lifecycle_state": state,
        "state_since": since,
        "snooze_until": snooze_until,
        "review_at": review_at,
        "capsule": capsule,
        "dismissals": dismissals,
        "accept_actions": accepts_like,
        "dismissal_epoch": dismissal_epoch,
        "decision_rejected_at": decision_rejected_at,
        "last_activity_event_at": last_activity_event_at,
    }


# ---------------------------------------------------------------------------
# Dependency rollup and board projection (M7)
# ---------------------------------------------------------------------------


def dependency_rollup(
    workstreams: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Transitive blocking analysis over explicit depends_on/blocks bindings.

    ``blocks(A, B)`` and ``depends_on(B, A)`` both mean: A must finish before
    B. Only open workstreams participate. Deterministic DFS with cycle guard;
    the bottleneck is the workstream with the highest transitive blocking
    count, shown with its directly blocked list as the reason.
    """

    open_ids = {
        ws_id for ws_id, ws in workstreams.items() if ws["lifecycle_state"] not in TERMINAL_STATES
    }
    blocks: dict[str, set[str]] = {ws_id: set() for ws_id in open_ids}
    invalid_assertions: list[dict[str, str]] = []
    for ws_id, ws in workstreams.items():
        for binding in ws.get("bindings", []):
            assertion_state = str(binding.get("assertion_state", "active"))
            assertion_status = str(binding.get("assertion_status", ""))
            if (
                binding.get("retracted") is True
                or binding.get("active") is False
                or assertion_state == "retracted"
                or assertion_status in {"proposed", "rejected", "retracted"}
            ):
                continue
            kind = binding.get("binding_kind")
            ref = str(binding.get("ref", ""))
            if kind in {"blocks", "depends_on"} and ws_id == ref:
                invalid_assertions.append(
                    {
                        "kind": "self_dependency",
                        "source": ws_id,
                        "target": ref,
                    }
                )
                continue
            if kind == "blocks" and ws_id in open_ids and ref in open_ids:
                blocks[ws_id].add(ref)
            elif kind == "depends_on" and ws_id in open_ids and ref in open_ids:
                blocks[ref].add(ws_id)

    def reachable(start: str, target: str) -> bool:
        seen: set[str] = set()
        stack = list(blocks.get(start, ()))
        while stack:
            node = stack.pop()
            if node == target:
                return True
            if node in seen:
                continue
            seen.add(node)
            stack.extend(blocks.get(node, ()))
        return False

    # Edges inside a cycle are invalid for critical-path and suppression
    # purposes. Surface them explicitly and project only the acyclic remainder.
    cycle_edges = {
        (source, target)
        for source, targets in blocks.items()
        for target in targets
        if reachable(target, source)
    }
    cycle_nodes = sorted({node for edge in cycle_edges for node in edge})
    if cycle_nodes:
        invalid_assertions.append(
            {
                "kind": "dependency_cycle",
                "source": ",".join(cycle_nodes),
                "target": "",
            }
        )
        for source, target in cycle_edges:
            blocks[source].discard(target)

    def transitive(start: str) -> set[str]:
        seen: set[str] = set()
        stack = list(blocks.get(start, ()))
        while stack:
            node = stack.pop()
            if node in seen or node == start:
                continue
            seen.add(node)
            stack.extend(blocks.get(node, ()))
        return seen

    rollup: dict[str, dict[str, Any]] = {}
    for ws_id in sorted(open_ids):
        blocked = transitive(ws_id)
        direct_upstream = sorted(
            upstream for upstream, downs in blocks.items() if ws_id in downs
        )
        rollup[ws_id] = {
            "blocking_count": len(blocked),
            "blocks_directly": sorted(blocks.get(ws_id, ())),
            "blocked_by": direct_upstream,
        }
    bottlenecks = [
        {
            "workstream_id": ws_id,
            "blocking_count": info["blocking_count"],
            "blocks_directly": info["blocks_directly"],
        }
        for ws_id, info in sorted(
            rollup.items(), key=lambda kv: (-kv[1]["blocking_count"], kv[0])
        )
        if info["blocking_count"] > 0
    ]
    return {
        "per_workstream": rollup,
        "bottlenecks": bottlenecks[:5],
        "invalid_assertions": invalid_assertions,
        "cycle_nodes": cycle_nodes,
    }


def board_projection(workstreams: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    """Scrum-style board: lifecycle columns as a pure projection of the fold."""

    board: dict[str, list[dict[str, str]]] = {state: [] for state in LIFECYCLE_STATES}
    for ws in sorted(workstreams, key=lambda w: (w["proposed_at"], w["workstream_id"])):
        board[ws["lifecycle_state"]].append(
            {"workstream_id": ws["workstream_id"], "idea_text": ws["idea_text"]}
        )
    return board


# ---------------------------------------------------------------------------
# Trigger evaluation (per open workstream)
# ---------------------------------------------------------------------------


def evaluate_triggers(
    workstream: dict[str, Any],
    *,
    policy: AttentionPolicy,
    now: datetime,
    related_active_labels: list[str],
    dependency_info: dict[str, Any] | None,
    class_stats: dict[str, dict[str, Any]],
    coverage: list[dict[str, str]],
) -> dict[str, Any]:
    """Evaluate one workstream's triggers into a focus item (or suppression).

    Returns the focus item; ``priority == 0`` means suppressed, with the
    suppression reason preserved (silence stays explainable, M5).
    """

    ws_id = workstream["workstream_id"]
    state = workstream["lifecycle_state"]
    capsule = workstream.get("capsule") or {}
    snooze_until = workstream.get("snooze_until", "")
    review_at = workstream.get("review_at", "")
    dismissals = workstream.get("dismissals", [])
    inactive_days = workstream.get("inactive_days")

    triggers: list[dict[str, Any]] = []
    suppressed: list[str] = []

    dismissal_epoch = int(workstream.get("dismissal_epoch", 0))
    signature_base = {"dismissal_epoch": dismissal_epoch, "state": state}

    def add(
        kind: str,
        tier: str,
        priority: int,
        reason: str,
        *,
        material_inputs: dict[str, Any] | None = None,
    ) -> None:
        signature_inputs = {**signature_base, **(material_inputs or {})}
        triggers.append(
            {
                "trigger_kind": kind,
                "trigger_signature": trigger_signature(ws_id, kind, signature_inputs),
                "tier": tier,
                "priority": priority,
                "reason": reason,
            }
        )

    if state in TERMINAL_STATES:
        suppressed.append(f"closed ({state})")
    else:
        snooze_dt = parse_dt(snooze_until)
        snoozing = state == "snoozed" and snooze_dt is not None and snooze_dt > now
        snooze_expired = state == "snoozed" and snooze_dt is not None and snooze_dt <= now
        if state == "snoozed" and snooze_until and snooze_dt is None:
            coverage.append(
                {"workstream_id": ws_id, "note": f"unparsable snooze_until '{snooze_until}'"}
            )
        review_dt = parse_dt(review_at)
        incubating_quietly = state == "incubating" and (review_dt is None or review_dt > now)
        if state == "incubating" and review_at and review_dt is None:
            coverage.append(
                {"workstream_id": ws_id, "note": f"unparsable review_at '{review_at}'"}
            )
            incubating_quietly = True

        blocked_by = (dependency_info or {}).get("blocked_by", [])
        blocker_text = capsule.get("blocker", "")
        next_action = capsule.get("next_action", "")
        pause_reason = capsule.get("pause_reason", "")
        idle = isinstance(inactive_days, int) and inactive_days >= policy.stale_days
        weekly_idle = isinstance(inactive_days, int) and inactive_days >= policy.weekly_days

        if snoozing:
            suppressed.append(f"snoozed until {snooze_until}")
        elif incubating_quietly:
            suppressed.append(
                f"incubating by choice{f' until {review_at}' if review_at else ''}"
            )
        else:
            if blocker_text and state != "paused":
                add(
                    "blocker",
                    "interrupt",
                    PRIORITY_BLOCKER,
                    f"Blocked: {blocker_text}",
                    material_inputs={"blocker": blocker_text.casefold()},
                )
            if workstream.get("needs_human_decision") and not workstream.get("conflict_resolved"):
                add(
                    "conflict_decision",
                    "interrupt",
                    PRIORITY_CONFLICT,
                    "Unresolved conflict with prior work; needs a keep-or-supersede decision.",
                )
            if state == "incubating":
                add(
                    "incubation_review",
                    "weekly",
                    PRIORITY_INCUBATION_REVIEW,
                    f"Incubation review date reached ({review_at}); decide resume, keep incubating, or archive.",
                )
            if state in {"proposed", "active"} or snooze_expired:
                if blocked_by:
                    upstream = ", ".join(blocked_by[:2])
                    suppressed.append(f"waiting on upstream workstream(s): {upstream}")
                else:
                    if related_active_labels and idle and not next_action:
                        related_str = ", ".join(sorted(set(related_active_labels))[:2])
                        add(
                            "related_active_idle",
                            "nudge",
                            PRIORITY_NUDGE_RELATED_IDLE,
                            f"Related to active work ({related_str}) but idle "
                            f"{inactive_days} day(s) with no next action.",
                            material_inputs={
                                "idle_band": _idle_band(inactive_days, policy),
                                "related": sorted(set(related_active_labels)),
                            },
                        )
                    if weekly_idle and not next_action and not pause_reason:
                        add(
                            "weekly_decision",
                            "weekly",
                            PRIORITY_WEEKLY_DECISION,
                            f"Open {inactive_days} days with no pause reason or next action; "
                            "decide resume, pause, or supersede.",
                            material_inputs={"idle_band": _idle_band(inactive_days, policy)},
                        )
                    elif snooze_expired and not next_action and not pause_reason:
                        add(
                            "weekly_decision",
                            "weekly",
                            PRIORITY_WEEKLY_DECISION,
                            f"Snooze expired on {snooze_until}; decide resume, snooze again, "
                            "incubate, or archive.",
                            material_inputs={
                                "snooze_until": snooze_dt.date().isoformat(),
                                "idle_band": _idle_band(inactive_days, policy),
                            },
                        )

        # M3 dismissal handling: signatures suppress; interrupts are immune.
        generic_dismissals = [d for d in dismissals if not d["trigger_signature"]]
        kept: list[dict[str, Any]] = []
        for trig in triggers:
            if trig["trigger_kind"] in _INTERRUPT_KINDS:
                kept.append(trig)
                continue
            sig_dismissals = [
                d for d in dismissals if d["trigger_signature"] == trig["trigger_signature"]
            ] + generic_dismissals
            count = len(sig_dismissals)
            recent = any(
                (lambda dt: dt is not None and (now - dt).total_seconds() < policy.dismiss_cooldown_days * 86_400)(
                    parse_dt(d["recorded_at"])
                )
                for d in sig_dismissals
            )
            if count >= policy.dismiss_decision_threshold and state != "incubating":
                # M2: converge to an explicit decision instead of decay/noise.
                kept.append(
                    {
                        "trigger_kind": "decision_proposed",
                        "trigger_signature": trigger_signature(
                            ws_id,
                            "decision_proposed",
                            {"dismissal_epoch": dismissal_epoch},
                        ),
                        "tier": "weekly",
                        "priority": PRIORITY_DECISION_PROPOSED,
                        "reason": (
                            f"Dismissed {count} time(s): propose incubating this with a review "
                            "date, or archive it. One explicit decision ends the reminders."
                        ),
                    }
                )
            elif recent:
                suppressed.append(
                    f"'{trig['trigger_kind']}' dismissed within the last "
                    f"{policy.dismiss_cooldown_days} day(s)"
                )
            else:
                kept.append(trig)
        # Deduplicate decision_proposed (several triggers can converge).
        seen_sigs: set[str] = set()
        triggers = [
            t for t in kept if not (t["trigger_signature"] in seen_sigs or seen_sigs.add(t["trigger_signature"]))
        ]

        if not triggers and not suppressed:
            suppressed.append(
                "intentional (has a next action or explicit pause reason)"
                if (next_action or pause_reason)
                else "no attention trigger yet"
            )

    top = max(triggers, key=lambda t: t["priority"], default=None)
    priority = top["priority"] if top else 0
    tier = top["tier"] if top else "silent"
    reasons = [t["reason"] for t in sorted(triggers, key=lambda t: -t["priority"])]

    # Per-class precision decay (kept from the draft: lowers prominence only).
    if priority > 0 and workstream.get("relations"):
        top_type = workstream["relations"][0]["relationship_type"]
        if class_stats.get(top_type, {}).get("low_precision"):
            priority = max(1, priority - CLASS_DECAY_PENALTY)
            reasons.append(
                f"De-prioritised: '{top_type}' suggestions have a low accept rate for you."
            )

    dep = dependency_info or {}
    if priority > 0 and dep.get("blocking_count"):
        reasons.append(
            f"Resolving this unblocks {dep['blocking_count']} other workstream(s)."
        )

    return {
        "workstream_id": ws_id,
        "idea_text": workstream["idea_text"],
        "proposal_kind": workstream["proposal_kind"],
        "lifecycle_state": state,
        "priority": priority,
        "tier": tier,
        "trigger_signature": top["trigger_signature"] if top else "",
        "trigger_kind": top["trigger_kind"] if top else "",
        "reasons": reasons,
        "suppressed_reasons": suppressed,
        "next_action": capsule.get("next_action", ""),
        "inactive_days": inactive_days,
        "last_activity_at": workstream.get("last_activity_at", ""),
    }


def relationship_class_stats(
    workstreams: dict[str, dict[str, Any]],
    *,
    policy: AttentionPolicy,
    relationship_types: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    """Per-class accept/dismiss precision stats (M4). Lowers prominence only."""

    stats: dict[str, dict[str, Any]] = {
        rel_type: {"accepts": 0, "dismisses": 0} for rel_type in relationship_types
    }
    for ws in workstreams.values():
        relations = ws.get("relations", [])
        if not relations:
            continue
        top_type = relations[0]["relationship_type"]
        stats[top_type]["accepts"] += len(ws.get("accept_actions", []))
        stats[top_type]["dismisses"] += len(ws.get("dismissals", []))
    for counts in stats.values():
        total = counts["accepts"] + counts["dismisses"]
        counts["samples"] = total
        counts["accept_rate"] = round(counts["accepts"] / total, 4) if total else None
        counts["low_precision"] = bool(
            total >= policy.decay_min_samples
            and counts["accepts"] / total < policy.decay_max_accept_rate
        )
    return stats


# ---------------------------------------------------------------------------
# Divergence vs. sprawl (M6): connected? tended? — reported, never scored
# ---------------------------------------------------------------------------


def sprawl_clusters(
    workstreams: dict[str, dict[str, Any]],
    *,
    policy: AttentionPolicy,
) -> list[dict[str, Any]]:
    """Family-linked (sibling/duplicate/continuation) open untended workstreams.

    Tended = any of: next action, capsule, binding, or activity fresher than
    ``stale_days``. Fresh work is exempt (allowed to be untended)."""

    def untended(ws: dict[str, Any]) -> bool:
        capsule = ws.get("capsule") or {}
        idle = ws.get("inactive_days")
        fresh = not isinstance(idle, int) or idle < policy.stale_days
        return not (fresh or capsule or ws.get("bindings"))

    open_untended = {
        ws_id: ws
        for ws_id, ws in workstreams.items()
        if ws["lifecycle_state"] in {"proposed", "active"} and untended(ws)
    }
    adjacency: dict[str, set[str]] = {}
    for ws_id, ws in open_untended.items():
        for relation in ws.get("relations", []):
            if relation["relationship_type"] in {"sibling", "duplicate", "continuation"} and relation[
                "target_id"
            ] in open_untended:
                adjacency.setdefault(ws_id, set()).add(relation["target_id"])
                adjacency.setdefault(relation["target_id"], set()).add(ws_id)

    clusters: list[dict[str, Any]] = []
    visited: set[str] = set()
    for start in sorted(adjacency):
        if start in visited:
            continue
        component: set[str] = set()
        stack = [start]
        while stack:
            node = stack.pop()
            if node in component:
                continue
            component.add(node)
            stack.extend(adjacency.get(node, ()))
        visited |= component
        if len(component) >= 2:
            clusters.append(
                {
                    "workstream_ids": sorted(component),
                    "reason": (
                        f"{len(component)} related open workstreams are all untended "
                        "(no next action, pause reason, or binding). Consider merging, "
                        "picking one, or incubating the set."
                    ),
                }
            )
    return clusters


__all__ = [
    "AttentionPolicy",
    "FEEDBACK_ACTIONS",
    "LIFECYCLE_STATES",
    "LIFECYCLE_TRANSITIONS",
    "MAX_TODAY",
    "TERMINAL_STATES",
    "TRIGGER_KINDS",
    "board_projection",
    "days_since",
    "dependency_rollup",
    "evaluate_triggers",
    "fold_lifecycle",
    "latest_iso",
    "parse_dt",
    "relationship_class_stats",
    "sprawl_clusters",
    "trigger_signature",
]
