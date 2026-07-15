# Unfinished Intent Recovery Shadow Trial

Status: not yet eligible for recurring activation.

The implementation is testable in deterministic, read-only shadow mode. This
record intentionally does not claim the required seven-day supervised trial has
occurred.

## Required supervised observations

Record at least five reviews on distinct observation timestamps spanning at
least seven calendar days. For each review capture only metadata-safe counts and
fingerprints:

- eligible explicit material plans and correctly captured seeds;
- missed, unnecessary, harmful, or useful captures;
- top-three relation precision, possible-duplicate rejections, and false merges;
- recovery candidates, preserved builds, unknown outcomes, and accidental Git
  mutations;
- unfinished inventory, changed asks, repeated unchanged asks, snoozes, and
  dismissals;
- model calls, tokens, known cost, and whether the cycle used zero model tokens;
- notification privacy review and delivery state.

## Promotion gates

- false merges: zero;
- accidental mutations: zero;
- repeated unchanged asks: zero;
- asks in every digest: at most three and sourced from the existing Today queue;
- deterministic unchanged cycles: zero model calls;
- notification content: no names, paths, prompts, or source content;
- no blind delivery retry;
- explicit Lowell approval for coverage, schedule, timezone, channel, retention,
  expiry, rollback, and kill criteria.

Until all gates pass, `asset-dir os recovery digest` prepares a local packet and
`asset-dir os recovery deliver` returns `activation_required`; neither command
creates a scheduled task nor a Windows toast.
