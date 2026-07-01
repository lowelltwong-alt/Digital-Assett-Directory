# Prompt: Roll out preflight asset to many repos

Goal: Deploy the central AI engineering preflight asset to the repositories listed in `repos.txt`.

Context:
- The central asset is at: `/path/to/YOUR_ASSET_REPO/assets/ai-engineering-preflight/`.
- The repo list is at: `/path/to/repos.txt`.
- Use `scripts/sync_to_many_repos.py`.

Constraints:
- Dry-run first.
- Use `--profile auto` unless a repo has a known language override.
- Do not push commits or change remotes.
- Do not refactor code during rollout.
- After dry-run, summarize planned changes before applying.

Done when:
- Every listed repo has either been updated or has a clear failure reason.
- You report per-repo status, files changed, commands run, commands not run, assumptions, and risks.
