# Controller-Owned State

This directory is reserved for the selected but unqualified inert campaign
controller after an exact human launch approval. Revision 7 names a
projection-only controller and shell adapter; neither is active, authorized to
dispatch, or authorized to write runtime state today.

Workers must never write here. The controller owns leases, checkpoints, budget
state, stop receipts, and append-only job receipt logs. Runtime state is not
source authority and must be rebuildable from accepted receipts and repository
evidence.

Atomic child checkpoints and receipts must bind the accepted v2 binding-table
digest, case digest, unique envelope, producer-attempt digest, and checker-record
digest. Cohort checkpoints additionally bind exact closure; J-600 binds one
selected route, predecessor, trigger class, closure, accepted navigation
receipt, and permitted decisions.

Required runtime names are declared in `campaign.json`. The adapter remains
inert, the launch command and authorization receipt remain `not-authorized`, and
terminal navigation requires a separate Portfolio OS lease. Navigation state is
not written here: its immutable accepted receipts live under
`checks/evidence/navigation/` and its writer may act only on the exact protected
metadata paths declared by the route contract.
