---
name: dad-learning-loop
description: Complete evidence-backed learning loops using privacy-safe observations, validation, deduplication, and human-gated DAD candidate routing.
---

# DAD Learning Loop

## Before

- Search relevant DAD lessons, exception classes, and reviewed rules before
  proposing a new solution.
- Record which lesson was used, rejected, missing, or harmful and why.

## During

- Treat surprises, regressions, inaccurate recommendations, and incomplete
  feedback as candidate exceptions.
- Capture the smallest useful evidence: issue class, scope, evidence reference,
  fix reference, validator, confidence, applicability, non-applicability, and
  danger if the lesson is misapplied.
- Escalate uncertainty proportionally and preserve counterevidence.

## Close

- Verify that the response changed an observable result.
- Deduplicate against existing lessons and patterns.
- Return a reusable lesson or explicitly state that none was found.
- Send only privacy-safe candidate metadata through the repository's approved
  DAD transport.

Do not promote candidate lessons to truth, alter instructions automatically
from one poor outcome, or store raw client facts, secrets, or transcripts.
