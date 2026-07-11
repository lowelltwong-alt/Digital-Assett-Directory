# QRD/IFC Warning-Only Receiver Evidence

## Status

Candidate implementation evidence only. This packet does not authorize a real
disclosure, crossing, send, promotion, legal judgment, compliance judgment, or
privacy guarantee.

## Scope

The registered `lesson_payload` schema now recognizes optional sanitized QRD
and IFC projections from synthetic candidate packets. Intake remains the owner
of QRD/IFC proof generation. DAD owns only this receiver shape and its normal
review-before-promotion boundary.

The base schema remains warning-only and extensible. Existing key-value senders
still append mail with warnings, and root and nested `additionalProperties`
remain open for reviewed future fields.

## Premortem

- Governance could weaken if a warning-free payload were mistaken for send or
  promotion authority. Discovery docs now state the narrower meaning.
- Child schemas could drift if DAD copied Intake's canonical proof contracts.
  DAD instead validates a bounded safe projection with explicit ownership.
- Client, matter, carrier, privilege, or work-product boundaries could blur if
  support identifiers or free text crossed. The projection forbids those known
  fields and pins inclusion flags false.
- AI output could become authority if proof booleans were writable as true.
  Privacy, noninterference, human-review, receiver-authority, owning-repo-review,
  actual-crossing, and send claims are pinned false.
- Local convenience could bypass review through warning-only composition or
  `--no-payload-validation`. Those compatibility paths remain explicit and do
  not change DAD's release or promotion gates.
- CI could pass while discovery remained incomplete. The front door, TOC,
  navigation registry, Mail Center guide, schema registry, golden fixture, CLI
  validation, and tests are updated together.

## Red Team

- **Legacy break:** remove every optional QRD/IFC field and validate the base
  payload. Covered by a regression test.
- **Extension lock:** add an unknown reviewed extension to the base payload.
  Covered by a regression test.
- **Unsafe authority claim:** set private-data, privacy-guarantee,
  noninterference-guarantee, support-ID, or send flags true. Covered by schema
  rejection tests and warning-only compose coverage.
- **Canonical-owner confusion:** treat the DAD schema as a QRD/IFC generator.
  Fixed in `docs/MAIL_CENTER.md`; Intake remains the proof owner.
- **Real-data crossing:** put source identifiers or free text into `lesson_ir`.
  Known source-ID and free-text keys are forbidden, and using any projection
  requires explicit synthetic scope plus literal-false real/private/client/
  matter/carrier/privilege/work-product flags. This receiver is not a real-data
  scanner and cannot override an upstream scope failure.

## Open Review Boundaries

- Warning-only enforcement is intentionally retained for sender compatibility.
- No real-data path is authorized by this change.
- No DAD receiver authority or authenticated human review is asserted.
- Future hard enforcement requires a separate reviewed migration decision.
