use crate::models::{
    MailSpoolCheckArgs, MailSpoolCheckSummary, MailSpoolIssueSample, MailSpoolRootSummary,
};
use anyhow::{Context, Result, bail};
use serde_json::Value;
use std::collections::HashSet;
use std::fs::{self, File};
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

#[derive(Debug)]
struct RootSpec {
    path: PathBuf,
    alias: String,
}

#[derive(Debug, Default)]
struct RootCounts {
    checked_file_count: usize,
    jsonl_file_count: usize,
    lock_file_count: usize,
    temp_fragment_count: usize,
    rust_packet_count: usize,
    malformed_jsonl_row_count: usize,
    oversized_jsonl_row_count: usize,
}

pub fn check_mail_spools(args: MailSpoolCheckArgs) -> Result<MailSpoolCheckSummary> {
    validate_args(&args)?;
    let roots = root_specs(&args)?;
    let mut root_summaries = Vec::with_capacity(roots.len());
    let mut issue_samples: Vec<MailSpoolIssueSample> = Vec::new();
    let mut total = RootCounts::default();
    let mut seen_file_paths: HashSet<PathBuf> = HashSet::new();

    for root in roots {
        let mut counts = RootCounts::default();
        let status = if root.path.exists() {
            inspect_existing_root(
                &root,
                &args,
                &mut counts,
                &mut issue_samples,
                &mut seen_file_paths,
            )?
        } else {
            "missing".to_string()
        };
        add_counts(&mut total, &counts);
        root_summaries.push(MailSpoolRootSummary {
            root_alias: root.alias,
            status,
            checked_file_count: counts.checked_file_count,
            jsonl_file_count: counts.jsonl_file_count,
            lock_file_count: counts.lock_file_count,
            temp_fragment_count: counts.temp_fragment_count,
            rust_packet_count: counts.rust_packet_count,
            malformed_jsonl_row_count: counts.malformed_jsonl_row_count,
            oversized_jsonl_row_count: counts.oversized_jsonl_row_count,
        });
    }

    root_summaries.sort_by(|left, right| left.root_alias.cmp(&right.root_alias));
    issue_samples.sort_by(|left, right| {
        left.logical_path
            .cmp(&right.logical_path)
            .then(left.line_number.cmp(&right.line_number))
            .then(left.issue_type.cmp(&right.issue_type))
    });
    if issue_samples.len() > args.max_samples {
        issue_samples.truncate(args.max_samples);
    }

    let issue_count = total.lock_file_count
        + total.temp_fragment_count
        + total.malformed_jsonl_row_count
        + total.oversized_jsonl_row_count;

    Ok(MailSpoolCheckSummary {
        schema_version: "dad_mail_spool_check.v0_1".to_string(),
        root_count: root_summaries.len(),
        checked_file_count: total.checked_file_count,
        jsonl_file_count: total.jsonl_file_count,
        lock_file_count: total.lock_file_count,
        temp_fragment_count: total.temp_fragment_count,
        rust_packet_count: total.rust_packet_count,
        malformed_jsonl_row_count: total.malformed_jsonl_row_count,
        oversized_jsonl_row_count: total.oversized_jsonl_row_count,
        issue_count,
        roots: root_summaries,
        issue_samples,
        no_mutation_performed: true,
        authority_boundary: concat!(
            "Rust mail-spool check is read-only structural evidence. ",
            "Python mail doctor remains the authoritative collect/route/deliver gate."
        )
        .to_string(),
        authoritative_gate: "mail doctor".to_string(),
        semantic_checks_not_performed: vec![
            "collection audit verification".to_string(),
            "delivery log hash verification".to_string(),
            "public release gating".to_string(),
            "cross-source provenance conflict detection".to_string(),
            "Rust rollout MailMessageRecord semantic validation".to_string(),
        ],
    })
}

fn validate_args(args: &MailSpoolCheckArgs) -> Result<()> {
    if args.roots.is_empty() {
        bail!("provide at least one --root");
    }
    if args.roots.len() != args.root_aliases.len() {
        bail!("provide exactly one --root-alias for each --root");
    }
    if args.max_jsonl_row_bytes == 0 {
        bail!("--max-jsonl-row-bytes must be greater than zero");
    }
    for alias in &args.root_aliases {
        validate_alias(alias)?;
    }
    Ok(())
}

fn root_specs(args: &MailSpoolCheckArgs) -> Result<Vec<RootSpec>> {
    args.roots
        .iter()
        .zip(args.root_aliases.iter())
        .map(|(path, alias)| {
            Ok(RootSpec {
                path: path.canonicalize().unwrap_or_else(|_| path.to_path_buf()),
                alias: alias.to_string(),
            })
        })
        .collect()
}

fn validate_alias(alias: &str) -> Result<()> {
    if alias.is_empty() || alias.trim() != alias {
        bail!("--root-alias must be a non-empty public-safe relative alias");
    }
    if alias.contains('\\') || alias.contains(':') || Path::new(alias).is_absolute() {
        bail!("--root-alias must use forward-slash relative segments only");
    }
    for segment in alias.split('/') {
        if segment.is_empty() || segment == "." || segment == ".." {
            bail!("--root-alias must not contain empty, current, or parent segments");
        }
    }
    if !alias
        .chars()
        .all(|value| value.is_ascii_alphanumeric() || matches!(value, '/' | '-' | '_' | '.'))
    {
        bail!("--root-alias contains unsupported characters");
    }
    Ok(())
}

fn inspect_existing_root(
    root: &RootSpec,
    args: &MailSpoolCheckArgs,
    counts: &mut RootCounts,
    issue_samples: &mut Vec<MailSpoolIssueSample>,
    seen_file_paths: &mut HashSet<PathBuf>,
) -> Result<String> {
    if !root.path.is_dir() {
        return Ok("not_directory".to_string());
    }
    let mut files: Vec<PathBuf> = WalkDir::new(&root.path)
        .follow_links(false)
        .into_iter()
        .filter_map(|entry| entry.ok())
        .filter(|entry| entry.file_type().is_file())
        .map(|entry| entry.path().to_path_buf())
        .collect();
    files.sort_by(|left, right| {
        logical_path(root, left)
            .unwrap_or_default()
            .cmp(&logical_path(root, right).unwrap_or_default())
    });

    for path in files {
        let canonical_path = fs::canonicalize(&path).unwrap_or_else(|_| path.clone());
        if !seen_file_paths.insert(canonical_path) {
            continue;
        }
        let logical = logical_path(root, &path)?;
        counts.checked_file_count += 1;
        if is_lock(&path) {
            counts.lock_file_count += 1;
            push_issue_sample(
                issue_samples,
                args.max_samples,
                "jsonl_lock",
                logical.clone(),
                None,
                "lock file present",
            );
        }
        if is_temp_fragment(&path) {
            counts.temp_fragment_count += 1;
            push_issue_sample(
                issue_samples,
                args.max_samples,
                "atomic_temp_fragment",
                logical.clone(),
                None,
                "atomic temp fragment present",
            );
        }
        if is_rust_rollout_packet(&path) {
            counts.rust_packet_count += 1;
        }
        if is_jsonl(&path) {
            counts.jsonl_file_count += 1;
            inspect_jsonl(&path, &logical, args, counts, issue_samples)?;
        }
    }
    Ok("checked".to_string())
}

fn inspect_jsonl(
    path: &Path,
    logical_path: &str,
    args: &MailSpoolCheckArgs,
    counts: &mut RootCounts,
    issue_samples: &mut Vec<MailSpoolIssueSample>,
) -> Result<()> {
    let file = File::open(path).with_context(|| format!("open {}", path.display()))?;
    let mut reader = BufReader::new(file);
    let mut buffer = Vec::new();
    let mut line_number = 0;
    loop {
        buffer.clear();
        let bytes_read = reader
            .read_until(b'\n', &mut buffer)
            .with_context(|| format!("read {}", path.display()))?;
        if bytes_read == 0 {
            break;
        }
        line_number += 1;
        if buffer.len() > args.max_jsonl_row_bytes {
            counts.oversized_jsonl_row_count += 1;
            push_issue_sample(
                issue_samples,
                args.max_samples,
                "oversized_jsonl_record",
                logical_path.to_string(),
                Some(line_number),
                "row exceeds max_jsonl_row_bytes",
            );
            continue;
        }
        let trimmed = trim_jsonl_line(&buffer);
        if trimmed.is_empty() {
            continue;
        }
        if serde_json::from_slice::<Value>(trimmed).is_err() {
            counts.malformed_jsonl_row_count += 1;
            push_issue_sample(
                issue_samples,
                args.max_samples,
                "malformed_jsonl",
                logical_path.to_string(),
                Some(line_number),
                "row is not valid JSON",
            );
        }
    }
    Ok(())
}

fn trim_jsonl_line(bytes: &[u8]) -> &[u8] {
    let mut start = 0;
    let mut end = bytes.len();
    while start < end && bytes[start].is_ascii_whitespace() {
        start += 1;
    }
    while end > start && bytes[end - 1].is_ascii_whitespace() {
        end -= 1;
    }
    &bytes[start..end]
}

fn is_jsonl(path: &Path) -> bool {
    path.extension()
        .and_then(|value| value.to_str())
        .map(|value| value.eq_ignore_ascii_case("jsonl"))
        .unwrap_or(false)
}

fn is_lock(path: &Path) -> bool {
    path.extension()
        .and_then(|value| value.to_str())
        .map(|value| value.eq_ignore_ascii_case("lock"))
        .unwrap_or(false)
}

fn is_temp_fragment(path: &Path) -> bool {
    path.extension()
        .and_then(|value| value.to_str())
        .map(|value| value.eq_ignore_ascii_case("tmp"))
        .unwrap_or(false)
}

fn is_rust_rollout_packet(path: &Path) -> bool {
    let normalized = path.to_string_lossy().replace('\\', "/");
    normalized.contains("/rust_rollout/")
        && path
            .extension()
            .and_then(|value| value.to_str())
            .map(|value| value.eq_ignore_ascii_case("json"))
            .unwrap_or(false)
}

fn logical_path(root: &RootSpec, path: &Path) -> Result<String> {
    let relative = path
        .strip_prefix(&root.path)
        .with_context(|| format!("derive logical path under {}", root.alias))?
        .to_string_lossy()
        .replace('\\', "/");
    Ok(format!("{}/{}", root.alias.trim_end_matches('/'), relative))
}

fn push_issue_sample(
    samples: &mut Vec<MailSpoolIssueSample>,
    max_samples: usize,
    issue_type: &str,
    logical_path: String,
    line_number: Option<usize>,
    detail: &str,
) {
    if samples.len() >= max_samples {
        return;
    }
    samples.push(MailSpoolIssueSample {
        issue_type: issue_type.to_string(),
        logical_path,
        line_number,
        detail: detail.to_string(),
    });
}

fn add_counts(left: &mut RootCounts, right: &RootCounts) {
    left.checked_file_count += right.checked_file_count;
    left.jsonl_file_count += right.jsonl_file_count;
    left.lock_file_count += right.lock_file_count;
    left.temp_fragment_count += right.temp_fragment_count;
    left.rust_packet_count += right.rust_packet_count;
    left.malformed_jsonl_row_count += right.malformed_jsonl_row_count;
    left.oversized_jsonl_row_count += right.oversized_jsonl_row_count;
}
