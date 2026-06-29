# Digital Asset Directory

A local-first, read-only-by-default portfolio intelligence repository for discovering, cataloging, connecting, evaluating, and reusing digital assets across local drives and GitHub repositories.

This seed is designed for the private repository `lowelltwong-alt/Digital-Assett-Directory` and the local destination:

```text
C:\Users\lowel\OneDrive\Desktop\Git Projects\04_Digital_Assett_Directory
```

## Mission

Turn scattered files, repositories, lessons, schemas, workflows, prompts, tests, research, and architectural decisions into a governed asset graph that can answer:

- What have I already built?
- Which assets are reusable, verified, stale, dormant, duplicated, or missing context?
- What forgotten asset has become relevant because something new appeared?
- Which two or three assets could combine into a higher-value capability?
- What missing component would activate an otherwise dormant asset?
- Which external GitHub projects may supply that missing component?
- What should a future AI agent read before it starts a build?
- What lesson from this build must be captured for the next one?

## What this seed already provides

- Local-drive and GitHub inventory adapters.
- Raw versus processed data separation.
- Stable asset identity separate from content revisions.
- An Asset Identity And Similarity Ladder: metadata fingerprint, SHA-256, chunk
  hashes, extracted text, gated embeddings, knowledge graph, and audit log.
- SQLite catalog plus JSONL and graph exports.
- Deterministic tags, capabilities, needs, outcomes, and lifecycle metadata.
- Staleness, orphan, missing-part, dormant-asset, and synergy radars.
- Query-driven AI context packs.
- Append-only lessons, handoffs, audit events, and scan history.
- `AGENTS.md`, `CLAUDE.md`, Claude Code hooks, and downstream Git-hook templates.
- A roadmap with machine-checkable phase gates.
- JSON Schemas, a SKOS taxonomy seed, and a lightweight RDF/OWL ontology seed.
- Optional integration with the existing `orphan-radar` repository.

## Safety posture

The default operating mode is **read-only discovery**:

- source files are hashed before and after local scans;
- source files are not edited, moved, renamed, or deleted;
- symlinks are not followed;
- secrets, credentials, private keys, `.env` files, dependency folders, and generated build folders are excluded by default;
- absolute local paths are represented through source aliases in processed outputs;
- AI-generated links, tags, synergies, and research suggestions remain candidates until reviewed;
- remote GitHub access is read-only and uses `GITHUB_TOKEN` from the environment, never a committed token.

## First run on Windows

```powershell
# From the extracted repository
powershell -ExecutionPolicy Bypass -File .\scripts\install_to_target.ps1
cd 'C:\Users\lowel\OneDrive\Desktop\Git Projects\04_Digital_Assett_Directory'
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1

# Review config before the first broad scan
notepad .\config\sources.local.yaml

# Run validation and a dry status check
.\.venv\Scripts\python.exe -m digital_asset_directory.cli validate
.\.venv\Scripts\python.exe -m digital_asset_directory.cli status

# First scan
.\.venv\Scripts\python.exe -m digital_asset_directory.cli scan
```

## Core commands

```powershell
asset-dir scan
asset-dir status
asset-dir context "evaluation harness and learning loops"
asset-dir idea "combine orphan detection with skill discovery"
asset-dir lesson add --repo . --summary "What changed" --lesson "Reusable insight"
asset-dir agent preflight --repo . --agent codex --task "Implement a new scanner"
asset-dir agent postflight --session <SESSION_ID> --repo . --summary "Implemented scanner" --tests "pytest"
asset-dir agent install --repo 'C:\path\to\another\repo'
asset-dir research missing --limit 20
asset-dir recommend skills --threshold 3
asset-dir recommend swarm "Build a source-grounded assistant with evaluation and audit"
asset-dir roadmap check
asset-dir validate

# Optional after the first reviewed scan
powershell -ExecutionPolicy Bypass -File .\scripts\register_scheduled_scan.ps1 -DailyAt '02:30'
```

## Read order for AI systems

```text
AI_FRONT_DOOR.md
AGENTS.md
MACHINE_NAVIGATION_MANIFEST.json
registry/source-of-truth.json
registry/design-authority.json
registry/identity-layer-registry.json
AI_TABLE_OF_CONTENTS.md
docs/ARCHITECTURE.md
docs/ASSET_IDENTITY_AND_SIMILARITY_LADDER.md
docs/ASSET_VALUE_MODEL.md
roadmap/roadmap.yaml
```

## Current status

This package is a **tested seed scaffold**, not a claim that every local or remote asset has already been cataloged. The first complete scan must be run on the user's Windows machine with the reviewed local-source configuration and, for private GitHub repositories, a read-only token.
