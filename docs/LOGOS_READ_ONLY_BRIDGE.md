# Logos Read-Only DAD Bridge

The Logos family uses LLOS surface `1.0.0` with asymmetric communication.
Logos-local tools may write their own outboxes and read or pull central DAD
candidates. DAD may read approved control metadata and outboxes, then write
candidate records under `DAD_DATA_ROOT`.

DAD may not create directories, locks, temp files, inboxes, contracts, hooks,
source files, or any other filesystem entry inside a Logos repository. The
runtime classifies Logos repositories by reviewed remote identity and known
aliases; repo-owned `.digital-asset/dad-write-policy.json` files add a second
fail-closed deny signal.

There is no standing approval, environment override, daemon grant, or scheduled
write path. The 2026-07-11 rollout approval authorized installation by Codex; it
did not grant DAD write permission. A future write requires a separately
implemented foreground grant bound to one repo, operation, path set, prestate,
expiry, nonce, and single use. Until that mechanism is explicitly approved and
tested, DAD writes to Logos remain unconditionally blocked.

The central read-only audit writes
`processed/reports/logos_llos_audit.json` under the active data root. Its hashes,
versions, and status are candidate operational metadata, never Logos authority.

For a repository whose active worktree is intentionally pinned to a dirty or
in-progress branch, mail policy may set `llos_control_path` to a clean,
centrally managed read-only mirror. Mail collection continues to read the live
repository `path`; only the LLOS version and deny-write audit reads the mirror.
The daemon never fetches, updates, or writes either root as part of this audit.

