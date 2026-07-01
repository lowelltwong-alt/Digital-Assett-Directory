# Draft only. Review paths before running.
$Hub = 'C:\Users\lowel\OneDrive\Desktop\Git Projects\04_Digital_Assett_Directory'
$RepoRoot = 'C:\Users\lowel\OneDrive\Desktop\Git Projects'

# Wave 0 — Digital-Assett-Directory
# Install the control kit and master assets into DAD first; do not run downstream agent install against DAD itself.
# Use prompts/codex_install_control_kit_into_dad.prompt.md from the control kit.

# Wave 1 — LawFirm-os-exceptions-lake-runtime
asset-dir agent preflight --repo "$RepoRoot\LawFirm-os-exceptions-lake-runtime" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\LawFirm-os-exceptions-lake-runtime" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\LawFirm-os-exceptions-lake-runtime" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 1 — LawFirm-os-legal-knowledge-runtime
asset-dir agent preflight --repo "$RepoRoot\LawFirm-os-legal-knowledge-runtime" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\LawFirm-os-legal-knowledge-runtime" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\LawFirm-os-legal-knowledge-runtime" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 1 — LawFirm-os-orchestrator
asset-dir agent preflight --repo "$RepoRoot\LawFirm-os-orchestrator" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\LawFirm-os-orchestrator" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\LawFirm-os-orchestrator" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 1 — LawFirm-os-semantic-substrate
asset-dir agent preflight --repo "$RepoRoot\LawFirm-os-semantic-substrate" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\LawFirm-os-semantic-substrate" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\LawFirm-os-semantic-substrate" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 1 — LawFirm-os-skills-registry
asset-dir agent preflight --repo "$RepoRoot\LawFirm-os-skills-registry" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\LawFirm-os-skills-registry" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\LawFirm-os-skills-registry" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 2 — LawFirm-os-intake
asset-dir agent preflight --repo "$RepoRoot\LawFirm-os-intake" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\LawFirm-os-intake" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\LawFirm-os-intake" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 2 — LawFirm-os-talent-intelligence
asset-dir agent preflight --repo "$RepoRoot\LawFirm-os-talent-intelligence" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\LawFirm-os-talent-intelligence" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\LawFirm-os-talent-intelligence" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 2 — orphan-radar
asset-dir agent preflight --repo "$RepoRoot\orphan-radar" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\orphan-radar" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\orphan-radar" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 3 — Albert-Trial-Simulation-System
asset-dir agent preflight --repo "$RepoRoot\Albert-Trial-Simulation-System" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\Albert-Trial-Simulation-System" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\Albert-Trial-Simulation-System" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 3 — All-Law-Firm-Talent-Intel
asset-dir agent preflight --repo "$RepoRoot\All-Law-Firm-Talent-Intel" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\All-Law-Firm-Talent-Intel" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\All-Law-Firm-Talent-Intel" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 3 — airca-fractal-decision-architecture
asset-dir agent preflight --repo "$RepoRoot\airca-fractal-decision-architecture" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\airca-fractal-decision-architecture" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\airca-fractal-decision-architecture" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 3 — exceptions-lake-runtime
asset-dir agent preflight --repo "$RepoRoot\exceptions-lake-runtime" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\exceptions-lake-runtime" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\exceptions-lake-runtime" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 3 — fmg-fractal-capability-ontology
asset-dir agent preflight --repo "$RepoRoot\fmg-fractal-capability-ontology" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\fmg-fractal-capability-ontology" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\fmg-fractal-capability-ontology" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 3 — logos-governance-architecture
asset-dir agent preflight --repo "$RepoRoot\logos-governance-architecture" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\logos-governance-architecture" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\logos-governance-architecture" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 3 — logos-governed-core
asset-dir agent preflight --repo "$RepoRoot\logos-governed-core" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\logos-governed-core" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\logos-governed-core" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 3 — noesis-atlas
asset-dir agent preflight --repo "$RepoRoot\noesis-atlas" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\noesis-atlas" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\noesis-atlas" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 4 — kirsten-dissertation-knowledge-graph
asset-dir agent preflight --repo "$RepoRoot\kirsten-dissertation-knowledge-graph" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\kirsten-dissertation-knowledge-graph" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\kirsten-dissertation-knowledge-graph" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 4 — lairca-logos-grounded-theological-model
asset-dir agent preflight --repo "$RepoRoot\lairca-logos-grounded-theological-model" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\lairca-logos-grounded-theological-model" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\lairca-logos-grounded-theological-model" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 4 — logos-boundary-literature
asset-dir agent preflight --repo "$RepoRoot\logos-boundary-literature" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\logos-boundary-literature" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\logos-boundary-literature" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 4 — logos-scripture-graph
asset-dir agent preflight --repo "$RepoRoot\logos-scripture-graph" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\logos-scripture-graph" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\logos-scripture-graph" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 4 — lowell-career-os
asset-dir agent preflight --repo "$RepoRoot\lowell-career-os" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\lowell-career-os" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\lowell-career-os" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# Wave 4 — obsidian-foundry-vault
asset-dir agent preflight --repo "$RepoRoot\obsidian-foundry-vault" --agent codex --task "Install DAD managed pointer" --hub "$Hub"
asset-dir agent install --repo "$RepoRoot\obsidian-foundry-vault" --hub "$Hub"
asset-dir agent postflight --repo "$RepoRoot\obsidian-foundry-vault" --session <SESSION_ID> --summary "Installed DAD managed pointer" --hub "$Hub"

# SKIP pending inventory/specific approval: Bi-Test (inventory_first_then_pointer)
# SKIP pending inventory/specific approval: Ryans-Project (inventory_first_then_pointer)
# SKIP pending inventory/specific approval: lowelltwong-alt (do_not_install_without_specific_reason)
