---
name: dad-autonomy-oversight-control
description: Classify A0-A4 agent authority, validate exact allowlists and leases, enforce consequence and privacy gates, quarantine the smallest scope, trigger deterministic global kill, and require human recovery.
---

# DAD Autonomy Oversight and Control

Use this family for any proposed autonomous or scheduled mutation, runtime
fallback, pause, quarantine, kill, recovery, or control-plane change.

1. Classify the exact action: A0 observe, A1 recommend/draft, A2 bounded
   reversible allowlisted delivery, A3 exact human-confirmed high-consequence
   action, or A4 prohibited.
2. Bind stable operation, target, parameter digest, consequence, effect class,
   plan/checkpoint revision, harness revision, runtime route, scope, expiry, and
   attempt count into one lease.
3. Deny on mismatch, expiry, unknown cost under a hard cap, missing independent
   check, privacy conflict, or active quarantine/kill.
4. Quarantine the smallest sufficient scope: attempt, workflow revision, role,
   family, adapter, repository, then portfolio.
5. Global kill is deterministic and model-independent. It rejects new leases
   and preserves read-only evidence.
6. Recovery is never automatic. A resume request creates an authority request;
   it cannot lift quarantine or widen authority.

This candidate implementation cannot execute or sign actions. Control-plane
self-changes may be drafted and shadowed but require human merge and activation.
