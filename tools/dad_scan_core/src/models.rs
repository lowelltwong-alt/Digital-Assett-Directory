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

#[derive(Debug, Args, Clone)]
pub struct MailSpoolCheckArgs {
    /// Mail spool root to inspect. Repeat with one matching --root-alias per root.
    #[arg(long = "root", required = true)]
    pub roots: Vec<PathBuf>,

    /// Public-safe alias for the matching --root value.
    #[arg(long = "root-alias", required = true)]
    pub root_aliases: Vec<String>,

    /// Maximum JSONL row size before the row is treated as oversized.
    #[arg(long, default_value_t = 64_000)]
    pub max_jsonl_row_bytes: usize,

    /// Maximum issue samples to include in the JSON output.
    #[arg(long, default_value_t = 25)]
    pub max_samples: usize,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct MailSpoolIssueSample {
    pub issue_type: String,
    pub logical_path: String,
    pub line_number: Option<usize>,
    pub detail: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct MailSpoolRootSummary {
    pub root_alias: String,
    pub status: String,
    pub checked_file_count: usize,
    pub jsonl_file_count: usize,
    pub lock_file_count: usize,
    pub temp_fragment_count: usize,
    pub rust_packet_count: usize,
    pub malformed_jsonl_row_count: usize,
    pub oversized_jsonl_row_count: usize,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct MailSpoolCheckSummary {
    pub schema_version: String,
    pub root_count: usize,
    pub checked_file_count: usize,
    pub jsonl_file_count: usize,
    pub lock_file_count: usize,
    pub temp_fragment_count: usize,
    pub rust_packet_count: usize,
    pub malformed_jsonl_row_count: usize,
    pub oversized_jsonl_row_count: usize,
    pub issue_count: usize,
    pub roots: Vec<MailSpoolRootSummary>,
    pub issue_samples: Vec<MailSpoolIssueSample>,
    pub no_mutation_performed: bool,
    pub authority_boundary: String,
    pub authoritative_gate: String,
    pub semantic_checks_not_performed: Vec<String>,
}

#[derive(Debug, Args, Clone)]
pub struct EventLogCheckArgs {
    /// Event JSONL root to inspect. Repeat with one matching --root-alias per root.
    #[arg(long = "root", required = true)]
    pub roots: Vec<PathBuf>,

    /// Public-safe alias for the matching --root value.
    #[arg(long = "root-alias", required = true)]
    pub root_aliases: Vec<String>,

    /// Maximum JSONL row size before the row is treated as oversized.
    #[arg(long, default_value_t = 64_000)]
    pub max_jsonl_row_bytes: usize,

    /// Maximum issue samples to include in the JSON output.
    #[arg(long, default_value_t = 25)]
    pub max_samples: usize,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct EventLogIssueSample {
    pub issue_type: String,
    pub logical_path: String,
    pub line_number: Option<usize>,
    pub detail: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct EventLogRootSummary {
    pub root_alias: String,
    pub status: String,
    pub checked_file_count: usize,
    pub jsonl_file_count: usize,
    pub event_record_count: usize,
    pub malformed_jsonl_row_count: usize,
    pub invalid_utf8_row_count: usize,
    pub oversized_jsonl_row_count: usize,
    pub non_object_row_count: usize,
    pub missing_required_field_count: usize,
    pub invalid_field_value_count: usize,
    pub duplicate_event_id_count: usize,
    pub duplicate_dedupe_key_count: usize,
    pub unsafe_string_count: usize,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct EventLogCheckSummary {
    pub schema_version: String,
    pub root_count: usize,
    pub checked_file_count: usize,
    pub jsonl_file_count: usize,
    pub event_record_count: usize,
    pub malformed_jsonl_row_count: usize,
    pub invalid_utf8_row_count: usize,
    pub oversized_jsonl_row_count: usize,
    pub non_object_row_count: usize,
    pub missing_required_field_count: usize,
    pub invalid_field_value_count: usize,
    pub duplicate_event_id_count: usize,
    pub duplicate_dedupe_key_count: usize,
    pub unsafe_string_count: usize,
    pub issue_count: usize,
    pub roots: Vec<EventLogRootSummary>,
    pub issue_samples: Vec<EventLogIssueSample>,
    pub no_mutation_performed: bool,
    pub authority_boundary: String,
    pub authoritative_gate: String,
    pub semantic_checks_not_performed: Vec<String>,
}

#[derive(Debug, Args, Clone)]
pub struct RepoInventoryProbeArgs {
    /// Local root to inspect for Git repositories. Repeat with one --root-alias per root.
    #[arg(long = "root", required = true)]
    pub roots: Vec<PathBuf>,

    /// Public-safe alias for the matching --root value.
    #[arg(long = "root-alias", required = true)]
    pub root_aliases: Vec<String>,

    /// Maximum directory depth under each root to inspect.
    #[arg(long, default_value_t = 5)]
    pub max_depth: usize,

    /// Follow symlinks. Disabled until external target provenance exists.
    #[arg(long, default_value_t = false)]
    pub follow_symlinks: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct RepoInventoryProbeRecord {
    pub root_alias: String,
    pub logical_path: String,
    pub depth: usize,
    pub git_marker_type: String,
    pub contract_present: bool,
    pub contract_parse_status: String,
    pub contract_schema_version_present: bool,
    pub contract_repo_id_present: bool,
    pub contract_capture_surface_version_present: bool,
    pub contract_cli_fallback_present: bool,
    pub contract_stable_user_shim_present: bool,
    pub contract_windows_user_shim_present: bool,
    pub contract_raw_checkout_fallback_present: bool,
    pub contract_stable_shim_before_raw_checkout: bool,
    pub contract_structural_pass: bool,
    pub contract_issue_codes: Vec<String>,
    pub no_mutation_performed: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct RepoInventorySkippedDir {
    pub root_alias: String,
    pub logical_path: String,
    pub reason: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct RepoInventoryProbeRootSummary {
    pub root_alias: String,
    pub status: String,
    pub repo_count: usize,
    pub skipped_dir_count: usize,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct RepoInventoryProbeSummary {
    pub schema_version: String,
    pub root_count: usize,
    pub repo_count: usize,
    pub skipped_dir_count: usize,
    pub roots: Vec<RepoInventoryProbeRootSummary>,
    pub repos: Vec<RepoInventoryProbeRecord>,
    pub skipped_dirs: Vec<RepoInventorySkippedDir>,
    pub no_mutation_performed: bool,
    pub authority_boundary: String,
}

#[derive(Debug, Args, Clone)]
pub struct Phase8EvidenceCheckArgs {
    /// Phase 8 command evidence JSON file to inspect.
    #[arg(long)]
    pub commands: PathBuf,

    /// Public-safe alias for the command evidence file.
    #[arg(long = "commands-alias")]
    pub commands_alias: String,

    /// Maximum issue samples to include in the JSON output.
    #[arg(long, default_value_t = 25)]
    pub max_samples: usize,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Phase8EvidenceIssueSample {
    pub issue_type: String,
    pub logical_path: String,
    pub detail: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Phase8EvidenceCheckSummary {
    pub schema_version: String,
    pub checked_file_alias: String,
    pub checked_file_status: String,
    pub required_command_count: usize,
    pub observed_command_count: usize,
    pub passed_required_command_count: usize,
    pub missing_required_command_count: usize,
    pub non_passed_required_command_count: usize,
    pub schema_issue_count: usize,
    pub unsafe_string_count: usize,
    pub issue_count: usize,
    pub human_review_status: String,
    pub human_review_pending: bool,
    pub phase8_evidence_structural_clean: bool,
    pub phase8_human_gate_satisfied: bool,
    pub issue_samples: Vec<Phase8EvidenceIssueSample>,
    pub no_mutation_performed: bool,
    pub authority_boundary: String,
    pub authoritative_gate: String,
    pub semantic_checks_not_performed: Vec<String>,
}
