# M9 GitHub transparency release receipt

**Repository:** `lowelltwong-alt/Digital-Assett-Directory` (private)  
**Branch:** `codex/m9-bible-chunking-workflow`  
**PR:** [#97](https://github.com/lowelltwong-alt/Digital-Assett-Directory/pull/97)  
**Head after publication:** `9bac17a9fcd3d5f9ffaad10d843275c8af6696ac`  
**Recorded:** 2026-09-15

## Published files

| Repository path | Staged SHA-256 | Remote blob SHA |
|---|---|---|
| `docs/BIBLE_CHUNKING_REVIEW_MESH.md` | `D681ABB1E64EC6255EE52D9900205E8BF8B4D8B172E8C72FA85B84D9CE533D72` | `6b4106ab0fd8bd1dab5e2ff617b522cb39c88bd2` |
| `docs/M9_BIBLE_CHUNKING_TRANSPARENCY_INDEX.md` | `4C41E9BD89F4BB9A6B94201E7AE75271D5E6699DC7E03F7B9D2A03EBF3096E34` | `99127882ef35464a9421f70b4a07a8d689d2807d` |
| `docs/M9_SUBAGENT_ROLE_CATALOG.md` | `601D68B5630D76079D4BAFBF09DF5F3E4A067261ECF875A8E899F82E3CC42E20` | `20539c250ac4f781a0eb31e590a64099c5f44cea` |
| `docs/M9_CHECKPOINT_LINEAGE.md` | `C944F3F8AAF252A9CBF77BDCFB77CEBFF809BD1DEA3FA411D381CBBB897992A9` | `dafdc42bc565c1765edcc5cb7fadcdf266e2edfd` |
| `docs/M9_LIMITS_AND_EVIDENCE.md` | `C9CDC0E200FCF1F02161F9AA9D94131770F7171DA25093C0CFD5A0AA78338FAC` | `5270e95563254b7703eba1a027a541baa7f25558` |

## Verification

- Connector read-back matched every published document byte-for-byte with its staged UTF-8 content.
- `AI_TABLE_OF_CONTENTS.md` contains exactly one pointer for each published document; its remote blob is `0372d85bd96fb5ce0779981a06e9ff2a2567a78a`.
- The baseline privacy path/content scan over the exact five-document release candidate returned no findings and no skipped files.
- The PR is open, draft, and unmerged. No merge, promotion, production, scheduler, or canonical qualification is implied.

## Public-surface boundary

This release contains workflow, role taxonomy, progress counts, hash-only lineage, incidents, validation limits, and qualification boundaries. It excludes Bible source files, local absolute paths, raw review rows, full transcripts, credentials, and task-local payloads. The DAD repository remains a review and transparency surface, not the source-of-truth Bible corpus.

## Known validation limit

The general DAD `validate` workflow remains blocked before suite selection by the pre-existing `c8-copilot-pointer-scope` exception. The dedicated DAD contract check passed. The validation failure was not rerun because its inputs were unchanged; repair belongs to the DAD owner’s lane.
