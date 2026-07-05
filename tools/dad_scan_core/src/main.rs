use anyhow::Result;
use clap::{Parser, Subcommand};
#[derive(Debug, Parser)]
#[command(name = "dad-scan-core")]
#[command(about = "Deterministic scanner core for Digital Asset Directory")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Scan a local source tree and emit JSONL observations.
    ScanLocal(dad_scan_core::ScanLocalArgs),
    /// Read-only probe for DAD mail spools, locks, temp fragments, and JSONL health.
    MailSpoolCheck(dad_scan_core::MailSpoolCheckArgs),
    /// Read-only probe for local Git repository roots.
    RepoInventoryProbe(dad_scan_core::RepoInventoryProbeArgs),
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::ScanLocal(args) => {
            let summary = dad_scan_core::scan_local(args)?;
            println!("{}", serde_json::to_string_pretty(&summary)?);
        }
        Command::MailSpoolCheck(args) => {
            let summary = dad_scan_core::check_mail_spools(args)?;
            println!("{}", serde_json::to_string_pretty(&summary)?);
        }
        Command::RepoInventoryProbe(args) => {
            let summary = dad_scan_core::probe_repo_inventory(args)?;
            println!("{}", serde_json::to_string_pretty(&summary)?);
        }
    }
    Ok(())
}
