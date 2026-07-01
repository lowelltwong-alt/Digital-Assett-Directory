You are updating the repo map before a DAD rollout.

## Goal

Refresh `repo_map/lowelltwong-alt.repository_map.v0.1.0.json` from the current local/GitHub repository set.

## Steps

1. List repos accessible through DAD/local/GitHub.
2. For each repo, read README and AI authority files where available.
3. Classify family, authority tier, rollout policy, profiles, wave, mailbox eligibility, and hook eligibility.
4. Mark uncertain repos as `inventory_first_then_pointer`.
5. Do not install anything during mapping.
6. Validate JSON and report changes.
