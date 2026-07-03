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
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::ScanLocal(args) => {
            let summary = dad_scan_core::scan_local(args)?;
            println!("{}", serde_json::to_string_pretty(&summary)?);
        }
    }
    Ok(())
}
