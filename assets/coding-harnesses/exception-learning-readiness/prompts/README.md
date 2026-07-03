# Exception Learning Readiness Prompts

Use this harness when DAD needs evidence that exception events, fix outcomes,
release gates, and backfill candidates are routed conservatively before they
become reusable learning.

Prompt checklist:

- name the exception pattern being tested;
- name whether the expected result is queue, blocker, quarantine, or release hold;
- include only safe summaries, paths, hashes, IDs, and validation refs;
- do not include raw logs, secrets, private rows, hidden reasoning, or long
  copied source content;
- ask reviewers to look for false-green readiness, stale reports, and
  private-to-public movement.

Minimum command:

```text
asset-dir exceptions learning-check --scenarios assets/coding-harnesses/exception-learning-readiness/examples/synthetic-learning-readiness-scenarios.json
```
