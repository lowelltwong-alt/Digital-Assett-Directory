use clap::Args;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Args, Clone)]
pub struct ScanLocalArgs {
    /// Source directory to scan.
    #[arg(long)]
    pub source: PathBuf,

    /// Stable source identifier from DAD config.
    #[arg(long)]
    pub source_id: String,

    /// Display alias used instead of absolute paths in output.
    #[arg(long)]
    pub path_alias: String,

    /// JSONL observation output path.
    #[arg(long)]
    pub out: PathBuf,

    /// Scan summary JSON path.
    #[arg(long)]
    pub summary_out: PathBuf,

    /// Quarantine summary JSON path.
    #[arg(long)]
    pub quarantine_out: PathBuf,

    /// Maximum number of files to include; useful for smoke tests.
    #[arg(long)]
    pub max_files: Option<usize>,

    /// Maximum file size to content-hash. Larger files use metadata-only fingerprinting.
    #[arg(long, default_value_t = 10_485_760)]
    pub max_content_hash_bytes: u64,

    /// Follow symlinks. Default is false.
    #[arg(long, default_value_t = false)]
    pub follow_symlinks: bool,

    /// Additional glob exclude patterns.
    #[arg(long = "exclude")]
    pub excludes: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Observation {
    pub schema_version: String,
    pub observation_type: String,
    pub source_id: String,
    pub path_alias: String,
    pub logical_path: String,
    pub size_bytes: u64,
    pub modified_unix_seconds: Option<u64>,
    pub metadata_sha256: String,
    pub content_sha256: Option<String>,
    pub content_hash_mode: String,
    pub asset_type_hint: String,
    pub extract_method: String,
    pub no_mutation_performed: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SkippedPath {
    pub logical_path: String,
    pub reason: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct QuarantineReport {
    pub schema_version: String,
    pub source_id: String,
    pub path_alias: String,
    pub skipped_count: usize,
    pub skipped: Vec<SkippedPath>,
    pub bounded: bool,
    pub no_mutation_performed: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ScanSummary {
    pub schema_version: String,
    pub source_id: String,
    pub path_alias: String,
    pub source: String,
    pub included_count: usize,
    pub skipped_count: usize,
    pub output_jsonl: String,
    pub quarantine_report: String,
    pub bounded: bool,
    pub no_mutation_performed: bool,
}
