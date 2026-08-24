# Controller-Owned State

This directory is reserved for a future qualified campaign controller after an
exact human launch approval. It is not active state today.

Workers must never write here. The controller owns leases, checkpoints, budget
state, stop receipts, and append-only job receipt logs. Runtime state is not
source authority and must be rebuildable from accepted receipts and repository
evidence.

Required runtime names are declared in `campaign.json`. No controller, adapter,
launch command, shutdown command, or authorization receipt is selected in this
specification-only revision.

