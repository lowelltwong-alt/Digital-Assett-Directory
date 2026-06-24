# Security and Privacy

## Default controls

- read-only source access;
- no symlink traversal;
- bounded file sizes;
- explicit path exclusions;
- token-from-environment only;
- secret-like files excluded;
- sensitive excerpts redacted or omitted;
- absolute paths replaced by aliases in processed records;
- generated data kept out of Git by default;
- no automatic external writes or merges.

## Review before full-drive access

Before expanding beyond the Git Projects folder, review:

- client, legal, HR, financial, health, identity, and credential locations;
- cloud-sync behavior and retention;
- backups and catalog encryption;
- file ownership and third-party rights;
- whether content excerpts should be disabled for particular roots;
- whether a source requires metadata-only scanning.

## External repositories

A candidate GitHub project should not be imported based on stars alone. Review:

- license and compatibility;
- maintenance and release history;
- security posture and dependency risks;
- provenance and authorship;
- fit with the missing capability;
- integration and exit costs;
- whether a small local prototype can test the hypothesis.
