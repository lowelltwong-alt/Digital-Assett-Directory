# DAD Rollout Wave Plan

Generated: 2026-06-30T22:21:56Z

## Operating rule

Run wave 0 first. Do not install to uncertain/misc repos until DAD has inventoried them locally and confirmed authority files.

## Wave 0

- `Digital-Assett-Directory` — portfolio intelligence, governed learning hub, central asset source of truth — policy: `source_of_truth_owner`
## Wave 1

- `LawFirm-os-semantic-substrate` — canonical semantic-governance and contract repository — policy: `governance_pointer_only`
- `LawFirm-os-skills-registry` — skill supply chain, quarantine, scan, grade, approve, install — policy: `skill_wrapper_pointer`
- `LawFirm-os-orchestrator` — execution plane consuming substrate read-only — policy: `managed_pointer_plus_mailbox`
- `LawFirm-os-exceptions-lake-runtime` — evidence plane / append-only exceptions lake runtime — policy: `managed_pointer_plus_mailbox_append_only_caution`
- `LawFirm-os-legal-knowledge-runtime` — legal document ingestion preflight, retrieval planning, Legal Context Bundle assembly — policy: `managed_pointer_plus_mailbox`
## Wave 2

- `LawFirm-os-intake` — vertical workflow composition and evaluation for intake-to-budget — policy: `managed_pointer_plus_mailbox`
- `LawFirm-os-talent-intelligence` — runtime / feature repo for talent intelligence — policy: `managed_pointer_plus_mailbox`
- `orphan-radar` — orphan/staleness/discovery radar supporting DAD-style asset reuse — policy: `managed_pointer_plus_mailbox`
## Wave 3

- `All-Law-Firm-Talent-Intel` — talent intelligence project, likely predecessor or peer — policy: `managed_pointer_after_inventory`
- `Albert-Trial-Simulation-System` — trial simulation system — policy: `managed_pointer_after_inventory`
- `exceptions-lake-runtime` — exceptions lake runtime project, possibly predecessor/parallel to LawFirm OS runtime — policy: `managed_pointer_after_inventory`
- `logos-governance-architecture` — governance architecture project — policy: `governance_pointer_after_inventory`
- `logos-governed-core` — governed core project — policy: `managed_pointer_after_inventory`
- `airca-fractal-decision-architecture` — fractal decision architecture project — policy: `managed_pointer_after_inventory`
- `fmg-fractal-capability-ontology` — fractal capability ontology project — policy: `managed_pointer_after_inventory`
- `noesis-atlas` — atlas/knowledge system — policy: `managed_pointer_after_inventory`
## Wave 4

- `lowell-career-os` — career operating system — policy: `managed_pointer_after_inventory`
- `logos-scripture-graph` — scripture graph / knowledge graph project — policy: `managed_pointer_after_inventory`
- `logos-boundary-literature` — boundary literature project — policy: `managed_pointer_after_inventory`
- `lairca-logos-grounded-theological-model` — grounded theological model project — policy: `managed_pointer_after_inventory`
- `kirsten-dissertation-knowledge-graph` — dissertation knowledge graph project — policy: `managed_pointer_after_inventory`
- `obsidian-foundry-vault` — Obsidian/Foundry knowledge vault — policy: `mailbox_or_pointer_only`
## Wave 5

- `Ryans-Project` — individual project; inventory required before classification — policy: `inventory_first_then_pointer`
- `Bi-Test` — test or BI project; inventory required before classification — policy: `inventory_first_then_pointer`
## Wave 9

- `lowelltwong-alt` — GitHub profile or meta repository — policy: `do_not_install_without_specific_reason`


## Hooks

Hooks are disabled by default in this wave plan. Add hooks only after a separate approval because hooks can block work.

## Mailboxes

Mailboxes are allowed for persistent repos, but mailbox packets remain candidate evidence until locally reviewed.
