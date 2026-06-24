# Orphan Radar Integration

The existing `lowelltwong-alt/orphan-radar` repository is a local-first engine for Markdown/text notes using graph structure, TF-IDF similarity, community routing, hub penalties, bridge detection, evidence packets, and human review.

This directory does not replace it. The integration boundary is:

```text
Digital Asset Directory
  -> identifies note/document roots and catalog identity
  -> optionally invokes orphan-radar in read-only mode
  -> stores orphan-radar output as raw external evidence
  -> maps accepted candidate links into reviewable catalog edges
```

## Configuration

Set `ORPHAN_RADAR_COMMAND` or install `orphan-radar` in the active environment. Then use:

```text
asset-dir orphan-radar run --source <notes-folder>
```

## Boundary

- Orphan Radar source files remain immutable.
- Its information-gain and similarity metrics are ranking heuristics.
- Candidate links remain reviewable.
- The directory adds cross-repository asset types, lifecycle, lessons, missing-part, and activation metadata around the narrower note-graph engine.
