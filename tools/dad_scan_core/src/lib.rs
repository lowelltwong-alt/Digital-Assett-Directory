mod event_log;
mod extract;
mod hash;
mod mail_spool;
mod models;
mod phase8_evidence;
mod repo_probe;
mod report;
mod walk;

pub use event_log::check_event_logs;
pub use mail_spool::check_mail_spools;
pub use models::{
    EventLogCheckArgs, EventLogCheckSummary, EventLogIssueSample, EventLogRootSummary,
    MailSpoolCheckArgs, MailSpoolCheckSummary, MailSpoolIssueSample, MailSpoolRootSummary,
    Observation, Phase8EvidenceCheckArgs, Phase8EvidenceCheckSummary, Phase8EvidenceIssueSample,
    QuarantineReport, RepoInventoryProbeArgs, RepoInventoryProbeRecord,
    RepoInventoryProbeRootSummary, RepoInventoryProbeSummary, RepoInventorySkippedDir,
    ScanLocalArgs, ScanSummary,
};
pub use phase8_evidence::check_phase8_evidence;
pub use repo_probe::probe_repo_inventory;

use anyhow::{Context, Result, bail};
use std::collections::BTreeSet;
use std::env;
use std::ffi::{OsStr, OsString};
use std::fs;
use std::path::{Component, Path, PathBuf};

pub fn scan_local(args: ScanLocalArgs) -> Result<ScanSummary> {
    validate_args(&args)?;

    let discovered = walk::discover_files(&args)?;
    let mut observations = Vec::with_capacity(discovered.included.len());

    for path in &discovered.included {
        let metadata =
            fs::metadata(path).with_context(|| format!("metadata {}", path.display()))?;
        let logical_path = logical_path(&args, path)?;
        let metadata_sha256 = hash::metadata_fingerprint(&metadata);
        let (content_sha256, content_hash_mode) = if metadata.len() <= args.max_content_hash_bytes {
            match hash::sha256_file(path) {
                Ok(value) => (Some(value), "content_sha256".to_string()),
                Err(exc) => (None, format!("read_error:{exc}")),
            }
        } else {
            (None, "oversize_metadata_only".to_string())
        };
        observations.push(Observation {
            schema_version: "dad_scan_observation.v0_1".to_string(),
            observation_type: "local_file_candidate".to_string(),
            source_id: args.source_id.clone(),
            path_alias: args.path_alias.clone(),
            logical_path,
            size_bytes: metadata.len(),
            modified_unix_seconds: metadata
                .modified()
                .ok()
                .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                .map(|d| d.as_secs()),
            metadata_sha256,
            content_sha256,
            content_hash_mode,
            asset_type_hint: extract::asset_type_hint(path),
            extract_method: "extension_hint_only".to_string(),
            no_mutation_performed: true,
        });
    }

    if let Some(parent) = args.out.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("create output parent {}", parent.display()))?;
    }
    if let Some(parent) = args.summary_out.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("create summary parent {}", parent.display()))?;
    }
    if let Some(parent) = args.quarantine_out.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("create quarantine parent {}", parent.display()))?;
    }

    observations.sort_by(|a, b| a.logical_path.cmp(&b.logical_path));
    report::write_jsonl(&args.out, &observations)?;

    let quarantine = QuarantineReport {
        schema_version: "dad_quarantine_report.v0_1".to_string(),
        source_id: args.source_id.clone(),
        path_alias: args.path_alias.clone(),
        skipped_count: discovered.skipped.len(),
        skipped: discovered.skipped,
        bounded: discovered.bounded,
        no_mutation_performed: true,
    };
    report::write_pretty_json(&args.quarantine_out, &quarantine)?;

    let summary = ScanSummary {
        schema_version: "dad_scan_summary.v0_1".to_string(),
        source_id: args.source_id.clone(),
        path_alias: args.path_alias.clone(),
        source: args.path_alias.clone(),
        included_count: observations.len(),
        skipped_count: quarantine.skipped_count,
        output_jsonl: output_ref(&args.out),
        quarantine_report: output_ref(&args.quarantine_out),
        bounded: discovered.bounded,
        no_mutation_performed: true,
    };
    report::write_pretty_json(&args.summary_out, &summary)?;
    Ok(summary)
}

fn validate_args(args: &ScanLocalArgs) -> Result<()> {
    if !args.source.exists() {
        bail!("source path does not exist: {}", args.source.display());
    }
    if args.source.is_symlink() && !args.follow_symlinks {
        bail!("source path is a symlink; refusing without --follow-symlinks");
    }
    if args.follow_symlinks {
        bail!("--follow-symlinks is disabled until external target provenance is implemented");
    }
    if args.max_content_hash_bytes == 0 {
        bail!("--max-content-hash-bytes must be greater than zero");
    }
    if matches!(args.max_files, Some(0)) {
        bail!("--max-files must be greater than zero when provided");
    }
    validate_path_alias(&args.path_alias)?;
    validate_output_path(&args.out, "jsonl")?;
    validate_output_path(&args.summary_out, "json")?;
    validate_output_path(&args.quarantine_out, "json")?;
    validate_distinct_outputs([&args.out, &args.summary_out, &args.quarantine_out])?;
    if output_inside_source(&args.source, &args.out)?
        || output_inside_source(&args.source, &args.summary_out)?
        || output_inside_source(&args.source, &args.quarantine_out)?
    {
        bail!(
            "output path appears to be inside the scanned source; choose an output outside source or add a governed safe-output policy first"
        );
    }
    Ok(())
}

fn validate_path_alias(path_alias: &str) -> Result<()> {
    if path_alias.is_empty() || path_alias.trim() != path_alias {
        bail!("--path-alias must be a non-empty public-safe relative alias");
    }
    if path_alias.contains('\\') || path_alias.contains(':') {
        bail!("--path-alias must use forward-slash relative segments only");
    }
    if Path::new(path_alias).is_absolute() {
        bail!("--path-alias must not be an absolute path");
    }
    for segment in path_alias.split('/') {
        if segment.is_empty() || segment == "." || segment == ".." {
            bail!("--path-alias must not contain empty, current, or parent segments");
        }
    }
    if !path_alias
        .chars()
        .all(|value| value.is_ascii_alphanumeric() || matches!(value, '/' | '-' | '_' | '.'))
    {
        bail!("--path-alias contains unsupported characters");
    }
    Ok(())
}

fn validate_output_path(path: &Path, extension: &str) -> Result<()> {
    if path.exists() {
        bail!(
            "output path already exists; refusing to overwrite {}",
            path.display()
        );
    }
    if path
        .extension()
        .and_then(|value| value.to_str())
        .map(|value| !value.eq_ignore_ascii_case(extension))
        .unwrap_or(true)
    {
        bail!(
            "output path must use .{} extension: {}",
            extension,
            path.display()
        );
    }
    Ok(())
}

fn validate_distinct_outputs<'a>(paths: impl IntoIterator<Item = &'a PathBuf>) -> Result<()> {
    let mut seen = BTreeSet::new();
    for path in paths {
        let key = output_identity_key(&normalized_candidate_path(path)?);
        if !seen.insert(key) {
            bail!("output paths must be distinct");
        }
    }
    Ok(())
}

#[cfg(windows)]
fn output_identity_key(path: &Path) -> String {
    path.to_string_lossy()
        .replace('\\', "/")
        .to_ascii_lowercase()
        .trim_start_matches("//?/")
        .to_string()
}

#[cfg(not(windows))]
fn output_identity_key(path: &Path) -> String {
    path.to_string_lossy().to_string()
}

fn output_inside_source(source: &Path, out: &Path) -> Result<bool> {
    let source = source
        .canonicalize()
        .with_context(|| format!("canonicalize source {}", source.display()))?;
    let out_abs = normalized_candidate_path(out)?;
    Ok(out_abs.starts_with(source))
}

fn absolute_path(path: &Path) -> Result<PathBuf> {
    if path.is_absolute() {
        Ok(path.to_path_buf())
    } else {
        Ok(env::current_dir()
            .context("resolve current directory for relative path")?
            .join(path))
    }
}

fn canonical_candidate_path(path: &Path) -> Result<PathBuf> {
    let abs_path = normalize_components(&absolute_path(path)?);
    if abs_path.exists() {
        return abs_path
            .canonicalize()
            .with_context(|| format!("canonicalize output {}", abs_path.display()));
    }

    let mut missing_components: Vec<OsString> = Vec::new();
    let mut cursor = abs_path.as_path();
    while let Some(parent) = cursor.parent() {
        if cursor.exists() {
            let mut resolved = cursor
                .canonicalize()
                .with_context(|| format!("canonicalize output ancestor {}", cursor.display()))?;
            for component in missing_components.iter().rev() {
                resolved.push(component);
            }
            return Ok(resolved);
        }
        if let Some(file_name) = cursor.file_name() {
            missing_components.push(file_name.to_os_string());
        }
        cursor = parent;
    }

    Ok(abs_path)
}

fn normalized_candidate_path(path: &Path) -> Result<PathBuf> {
    Ok(normalize_components(&canonical_candidate_path(path)?))
}

fn normalize_components(path: &Path) -> PathBuf {
    let mut normalized = PathBuf::new();
    for component in path.components() {
        match component {
            Component::CurDir => {}
            Component::ParentDir => {
                normalized.pop();
            }
            Component::Prefix(prefix) => normalized.push(prefix.as_os_str()),
            Component::RootDir => normalized.push(component.as_os_str()),
            Component::Normal(value) if value == OsStr::new(".") => {}
            Component::Normal(value) if value == OsStr::new("..") => {
                normalized.pop();
            }
            Component::Normal(value) => normalized.push(value),
        }
    }
    normalized
}

fn logical_path(args: &ScanLocalArgs, path: &Path) -> Result<String> {
    let rel = path.strip_prefix(&args.source).with_context(|| {
        format!(
            "strip prefix {} from {}",
            args.source.display(),
            path.display()
        )
    })?;
    let rel = rel.to_string_lossy().replace('\\', "/");
    Ok(format!("{}/{}", args.path_alias.trim_end_matches('/'), rel))
}

fn output_ref(path: &Path) -> String {
    path.file_name()
        .and_then(|value| value.to_str())
        .map(ToString::to_string)
        .unwrap_or_else(|| "scan-output".to_string())
}
