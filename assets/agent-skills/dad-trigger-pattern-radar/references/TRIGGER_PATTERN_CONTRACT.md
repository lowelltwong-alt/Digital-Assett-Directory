# Trigger Pattern Contract

Every trigger signature is a versioned candidate digital asset. Record:

- stable pattern identity and separate revision identity;
- problem prevented or opportunity created;
- applies-when and does-not-apply-when boundaries;
- required, any, forbidden, counter-signals, suppressors, transitions, ordered
  sequences, grouping keys, and temporal windows;
- minimum lineage-distinct occurrences, source diversity, and coverage;
- deterministic versus model-proposed fields;
- candidate action class: observe, suggest, project, notify, or mutate;
- authority gate and prohibited side effects;
- cooldown, expiry, wake condition, and idempotency/suppression key;
- privacy class and redaction rule;
- expected benefit, execution cost, interruption cost, and false-positive harm;
- validator, positive/negative cases, rollback, and kill criteria;
- accept, reject, dismiss, snooze, usefulness, harm, and miss feedback;
- historical replay, lineage-grouped holdout results, and drift state;
- epistemic state: observed, derived, model-proposed, or confirmed;
- status: watching, candidate, trial, reviewed, rejected, superseded, or retired.

## Evidence and promotion

- One event creates a watch item, not a reusable rule.
- Copied worktrees count as one lineage.
- Age, similarity, priority, centrality, or confidence never proves value.
- Subjective dependencies, relationships, priorities, and abandonment remain proposed.
- Reminder trials require negative cases and silence/suppression tests.
- Compare useful-action precision, misses, dismissals, harm, and compute cost.
- Do not count unlabeled silence as a true negative.
- Use conservative lower bounds before enabling notifications.

Promotion ladder: observe, group comparable occurrences, propose and dedupe,
shadow-run, review harms and misses, human-approve a bounded trial, then promote,
revise, or retire with versioned evidence and rollback. Notification, external
write, Git mutation, scheduling, and instruction changes always require a named
human approval.
