# GitHub Discovery Notes

Generated: 2026-06-30T22:21:56Z

The GitHub connector observed the authenticated user as `lowelltwong-alt` and returned accessible repositories under that owner. The list used for this seed contains 26 repositories.

DAD repo observations:

- `Digital-Assett-Directory` is private, default branch `main`, and the README describes it as a local-first, read-only-by-default portfolio intelligence repository.
- DAD README lists preflight, postflight, agent install, and mail-related commands.
- DAD `AI_FRONT_DOOR.md` lists `docs/MAIL_CENTER.md`, `processed/mail/`, and related reports as mail-center surfaces.
- DAD `docs/MAIL_CENTER.md` defines the mail hub, local mirrors, packet types, storage layout, and command names.
- DAD `src/digital_asset_directory/cli.py` exposes mail compose/collect/route/deliver/review/digest and agent preflight/postflight/midflight/install commands.
- DAD `src/digital_asset_directory/governance.py` installs a managed `AGENTS.md` block, `.digital-asset-directory.yml`, mailbox mirror, and hooks.

Important caveat: this map is not a substitute for a fresh local DAD scan. Local repos may exist that are not visible to the GitHub connector, and repo authority files may have changed.
