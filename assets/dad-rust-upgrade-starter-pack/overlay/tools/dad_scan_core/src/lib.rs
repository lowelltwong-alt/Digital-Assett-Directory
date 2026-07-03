mod extract;
mod hash;
mod models;
mod report;
mod walk;

pub use models::{Observation, QuarantineReport, ScanLocalArgs, ScanSummary};

use anyhow::{bail, Context, Result};
use std::fs;
use std::path::{Path, PathBuf};

pub fn scan_local(args: ScanLocalArgs) -> Result<ScanSummary> {
    validate_args(&args)?;

    if let Some(parent) = args.out.parent() {
        fs::create_dir_all(parent).with_context(|| format!("create output parent {}", parent.display()))?;
    }
    if let Some(parent) = args.summary_out.parent() {
        fs::create_dir_all(parent).with_context(|| format!("create summary parent {}", parent.display()))?;
    }
    if let Some(parent) = args.quarantine_out.parent() {
        fs::create_dir_all(parent).with_context(|| format!("create quarantine parent {}", parent.display()))?;
    }

    let discovered = walk::discover_files(&args)?;
    let mut observations = Vec::with_capacity(discovered.included.len());

    for path in &discovered.included {
        let metadata = fs::metadata(path).with_context(|| format!("metadata {}", path.display()))?;
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
            modified_unix_seconds: metadata.modified().ok().and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok()).map(|d| d.as_secs()),
            metadata_sha256,
            content_sha256,
            content_hash_mode,
            asset_type_hint: extract::asset_type_hint(path),
            extract_method: "extension_hint_only".to_string(),
            no_mutation_performed: true,
        });
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
        source: args.source.display().to_string(),
        included_count: observations.len(),
        skipped_count: quarantine.skipped_count,
        output_jsonl: args.out.display().to_string(),
        quarantine_report: args.quarantine_out.display().to_string(),
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
    if args.max_content_hash_bytes == 0 {
        bail!("--max-content-hash-bytes must be greater than zero");
    }
    if output_inside_source(&args.source, &args.out)? || output_inside_source(&args.source, &args.summary_out)? || output_inside_source(&args.source, &args.quarantine_out)? {
        bail!("output path appears to be inside the scanned source; choose an output outside source or add a governed safe-output policy first");
    }
    Ok(())
}

fn output_inside_source(source: &Path, out: &Path) -> Result<bool> {
    let source = source.canonicalize().with_context(|| format!("canonicalize source {}", source.display()))?;
    let out_abs = if out.exists() {
        out.canonicalize()?
    } else if let Some(parent) = out.parent() {
        let parent = parent.canonicalize().unwrap_or_else(|_| parent.to_path_buf());
        parent.join(out.file_name().unwrap_or_default())
    } else {
        PathBuf::from(out)
    };
    Ok(out_abs.starts_with(source))
}

fn logical_path(args: &ScanLocalArgs, path: &Path) -> Result<String> {
    let rel = path.strip_prefix(&args.source).with_context(|| format!("strip prefix {} from {}", args.source.display(), path.display()))?;
    let rel = rel.to_string_lossy().replace('\\', "/");
    Ok(format!("{}/{}", args.path_alias.trim_end_matches('/'), rel))
}
