use crate::models::{
    EventLogCheckArgs, EventLogCheckSummary, EventLogIssueSample, EventLogRootSummary,
};
use anyhow::{Context, Result, bail};
use serde_json::Value;
use std::collections::{HashMap, HashSet};
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
    event_record_count: usize,
    malformed_jsonl_row_count: usize,
    invalid_utf8_row_count: usize,
    oversized_jsonl_row_count: usize,
    non_object_row_count: usize,
    missing_required_field_count: usize,
    invalid_field_value_count: usize,
    duplicate_event_id_count: usize,
    duplicate_dedupe_key_count: usize,
    unsafe_string_count: usize,
}

#[derive(Debug)]
struct SeenEventRef {
    logical_path: String,
    line_number: usize,
}

#[derive(Debug, Default)]
struct EventSeenState {
    event_ids: HashMap<String, SeenEventRef>,
    dedupe_keys: HashMap<String, SeenEventRef>,
}

const REQUIRED_FIELDS: &[&str] = &[
    "schema_version",
    "event_id",
    "event_type",
    "dedupe_key",
    "source_repo",
    "source_visibility",
    "created_at",
    "payload",
    "authority_boundary",
];

const EVENT_TYPES: &[&str] = &[
    "lesson_found",
    "exception_seen",
    "fix_outcome",
    "asset_used",
    "asset_rejected",
    "harness_needed",
    "dad_notice_ack",
    "dad_notice_saved_for_future",
    "dad_notice_implemented",
    "dad_notice_rejected",
    "governance_drift",
    "pipeline_health",
];

const VISIBILITIES: &[&str] = &["public", "internal", "private", "restricted", "unknown"];
const RESPONSE_STATES: &[&str] = &[
    "not_applicable",
    "acknowledged",
    "saved_for_future",
    "implementing",
    "implemented",
    "rejected",
    "deferred",
    "needs_human_review",
];
const SENSITIVITIES: &[&str] = &["public_metadata", "internal_metadata", "private_metadata"];
const MAX_STRING_CHARS: usize = 500;

pub fn check_event_logs(args: EventLogCheckArgs) -> Result<EventLogCheckSummary> {
    validate_args(&args)?;
    let roots = root_specs(&args)?;
    let mut root_summaries = Vec::with_capacity(roots.len());
    let mut issue_samples: Vec<EventLogIssueSample> = Vec::new();
    let mut total = RootCounts::default();
    let mut seen_file_paths: HashSet<PathBuf> = HashSet::new();
    let mut seen_events = EventSeenState::default();

    for root in roots {
        let mut counts = RootCounts::default();
        let status = if root.path.exists() {
            inspect_existing_root(
                &root,
                &args,
                &mut counts,
                &mut issue_samples,
                &mut seen_file_paths,
                &mut seen_events,
            )?
        } else {
            "missing".to_string()
        };
        add_counts(&mut total, &counts);
        root_summaries.push(EventLogRootSummary {
            root_alias: root.alias,
            status,
            checked_file_count: counts.checked_file_count,
            jsonl_file_count: counts.jsonl_file_count,
            event_record_count: counts.event_record_count,
            malformed_jsonl_row_count: counts.malformed_jsonl_row_count,
            invalid_utf8_row_count: counts.invalid_utf8_row_count,
            oversized_jsonl_row_count: counts.oversized_jsonl_row_count,
            non_object_row_count: counts.non_object_row_count,
            missing_required_field_count: counts.missing_required_field_count,
            invalid_field_value_count: counts.invalid_field_value_count,
            duplicate_event_id_count: counts.duplicate_event_id_count,
            duplicate_dedupe_key_count: counts.duplicate_dedupe_key_count,
            unsafe_string_count: counts.unsafe_string_count,
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

    let issue_count = total.malformed_jsonl_row_count
        + total.invalid_utf8_row_count
        + total.oversized_jsonl_row_count
        + total.non_object_row_count
        + total.missing_required_field_count
        + total.invalid_field_value_count
        + total.duplicate_event_id_count
        + total.duplicate_dedupe_key_count
        + total.unsafe_string_count;

    Ok(EventLogCheckSummary {
        schema_version: "dad_event_log_check.v0_1".to_string(),
        root_count: root_summaries.len(),
        checked_file_count: total.checked_file_count,
        jsonl_file_count: total.jsonl_file_count,
        event_record_count: total.event_record_count,
        malformed_jsonl_row_count: total.malformed_jsonl_row_count,
        invalid_utf8_row_count: total.invalid_utf8_row_count,
        oversized_jsonl_row_count: total.oversized_jsonl_row_count,
        non_object_row_count: total.non_object_row_count,
        missing_required_field_count: total.missing_required_field_count,
        invalid_field_value_count: total.invalid_field_value_count,
        duplicate_event_id_count: total.duplicate_event_id_count,
        duplicate_dedupe_key_count: total.duplicate_dedupe_key_count,
        unsafe_string_count: total.unsafe_string_count,
        issue_count,
        roots: root_summaries,
        issue_samples,
        no_mutation_performed: true,
        authority_boundary: concat!(
            "Rust event-log check is read-only structural evidence. ",
            "Python DAD event collection, policy, release, and response-state logic remain authoritative."
        )
        .to_string(),
        authoritative_gate: "events collect/report plus validate".to_string(),
        semantic_checks_not_performed: vec![
            "source visibility policy canonicalization".to_string(),
            "public release approval".to_string(),
            "notice target/source authorization".to_string(),
            "response-state transition ownership".to_string(),
            "repo adoption or enrollment decisions".to_string(),
        ],
    })
}

fn validate_args(args: &EventLogCheckArgs) -> Result<()> {
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

fn root_specs(args: &EventLogCheckArgs) -> Result<Vec<RootSpec>> {
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
    args: &EventLogCheckArgs,
    counts: &mut RootCounts,
    issue_samples: &mut Vec<EventLogIssueSample>,
    seen_file_paths: &mut HashSet<PathBuf>,
    seen_events: &mut EventSeenState,
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
        counts.checked_file_count += 1;
        if is_jsonl(&path) {
            counts.jsonl_file_count += 1;
            let logical = logical_path(root, &path)?;
            inspect_jsonl(&path, &logical, args, counts, issue_samples, seen_events)?;
        }
    }
    Ok("checked".to_string())
}

fn inspect_jsonl(
    path: &Path,
    logical_path: &str,
    args: &EventLogCheckArgs,
    counts: &mut RootCounts,
    issue_samples: &mut Vec<EventLogIssueSample>,
    seen_events: &mut EventSeenState,
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
        if std::str::from_utf8(trimmed).is_err() {
            counts.invalid_utf8_row_count += 1;
            push_issue_sample(
                issue_samples,
                args.max_samples,
                "invalid_utf8_row",
                logical_path.to_string(),
                Some(line_number),
                "row is not valid UTF-8",
            );
            continue;
        }
        let parsed = match serde_json::from_slice::<Value>(trimmed) {
            Ok(value) => value,
            Err(_) => {
                counts.malformed_jsonl_row_count += 1;
                push_issue_sample(
                    issue_samples,
                    args.max_samples,
                    "malformed_jsonl",
                    logical_path.to_string(),
                    Some(line_number),
                    "row is not valid JSON",
                );
                continue;
            }
        };
        let Some(object) = parsed.as_object() else {
            counts.non_object_row_count += 1;
            push_issue_sample(
                issue_samples,
                args.max_samples,
                "non_object_jsonl_row",
                logical_path.to_string(),
                Some(line_number),
                "event row is not a JSON object",
            );
            continue;
        };

        counts.event_record_count += 1;
        validate_event_object(
            object,
            logical_path,
            line_number,
            counts,
            issue_samples,
            args.max_samples,
            seen_events,
        );
    }
    Ok(())
}

fn validate_event_object(
    object: &serde_json::Map<String, Value>,
    logical_path: &str,
    line_number: usize,
    counts: &mut RootCounts,
    issue_samples: &mut Vec<EventLogIssueSample>,
    max_samples: usize,
    seen_events: &mut EventSeenState,
) {
    for field in REQUIRED_FIELDS {
        if !object.contains_key(*field) {
            counts.invalid_field_value_count += 1;
            push_issue_sample(
                issue_samples,
                max_samples,
                "missing_required_field",
                logical_path.to_string(),
                Some(line_number),
                field,
            );
        }
    }
    validate_enum_field(
        object,
        "event_type",
        EVENT_TYPES,
        logical_path,
        line_number,
        counts,
        issue_samples,
        max_samples,
    );
    validate_enum_field(
        object,
        "source_visibility",
        VISIBILITIES,
        logical_path,
        line_number,
        counts,
        issue_samples,
        max_samples,
    );
    validate_enum_field(
        object,
        "target_visibility",
        VISIBILITIES,
        logical_path,
        line_number,
        counts,
        issue_samples,
        max_samples,
    );
    validate_enum_field(
        object,
        "response_state",
        RESPONSE_STATES,
        logical_path,
        line_number,
        counts,
        issue_samples,
        max_samples,
    );
    validate_enum_field(
        object,
        "sensitivity",
        SENSITIVITIES,
        logical_path,
        line_number,
        counts,
        issue_samples,
        max_samples,
    );
    validate_string_field(
        object,
        "event_id",
        logical_path,
        line_number,
        counts,
        issue_samples,
        max_samples,
    );
    validate_string_field(
        object,
        "dedupe_key",
        logical_path,
        line_number,
        counts,
        issue_samples,
        max_samples,
    );
    validate_string_field(
        object,
        "source_repo",
        logical_path,
        line_number,
        counts,
        issue_samples,
        max_samples,
    );
    if let Some(event_type) = object.get("event_type").and_then(Value::as_str)
        && event_type.starts_with("dad_notice_")
        && object
            .get("notice_id")
            .and_then(Value::as_str)
            .unwrap_or("")
            .is_empty()
    {
        counts.missing_required_field_count += 1;
        push_issue_sample(
            issue_samples,
            max_samples,
            "missing_required_field",
            logical_path.to_string(),
            Some(line_number),
            "notice_id",
        );
    }
    for (field, value) in object {
        check_value_safety(
            value,
            field,
            logical_path,
            line_number,
            counts,
            issue_samples,
            max_samples,
        );
    }
    check_duplicate(
        object,
        "event_id",
        logical_path,
        line_number,
        &mut seen_events.event_ids,
        &mut counts.duplicate_event_id_count,
        issue_samples,
        max_samples,
        "duplicate_event_id",
    );
    check_duplicate(
        object,
        "dedupe_key",
        logical_path,
        line_number,
        &mut seen_events.dedupe_keys,
        &mut counts.duplicate_dedupe_key_count,
        issue_samples,
        max_samples,
        "duplicate_dedupe_key",
    );
}

#[allow(clippy::too_many_arguments)]
fn validate_enum_field(
    object: &serde_json::Map<String, Value>,
    field: &str,
    allowed: &[&str],
    logical_path: &str,
    line_number: usize,
    counts: &mut RootCounts,
    issue_samples: &mut Vec<EventLogIssueSample>,
    max_samples: usize,
) {
    let Some(value) = object.get(field) else {
        return;
    };
    if value.is_null() {
        return;
    }
    match value.as_str() {
        Some(text) if allowed.contains(&text) => {}
        _ => {
            counts.invalid_field_value_count += 1;
            push_issue_sample(
                issue_samples,
                max_samples,
                "invalid_field_value",
                logical_path.to_string(),
                Some(line_number),
                field,
            );
        }
    }
}

fn validate_string_field(
    object: &serde_json::Map<String, Value>,
    field: &str,
    logical_path: &str,
    line_number: usize,
    counts: &mut RootCounts,
    issue_samples: &mut Vec<EventLogIssueSample>,
    max_samples: usize,
) {
    match object.get(field).and_then(Value::as_str) {
        Some(text) if !text.trim().is_empty() => {}
        _ => {
            counts.missing_required_field_count += 1;
            push_issue_sample(
                issue_samples,
                max_samples,
                "missing_required_field",
                logical_path.to_string(),
                Some(line_number),
                field,
            );
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn check_duplicate(
    object: &serde_json::Map<String, Value>,
    field: &str,
    logical_path: &str,
    line_number: usize,
    seen: &mut HashMap<String, SeenEventRef>,
    count: &mut usize,
    issue_samples: &mut Vec<EventLogIssueSample>,
    max_samples: usize,
    issue_type: &str,
) {
    let Some(value) = object.get(field).and_then(Value::as_str) else {
        return;
    };
    if value.is_empty() {
        return;
    }
    if let Some(first_seen) = seen.get(value) {
        *count += 1;
        push_issue_sample(
            issue_samples,
            max_samples,
            issue_type,
            logical_path.to_string(),
            Some(line_number),
            &format!(
                "{field} was already seen at {}:{}",
                first_seen.logical_path, first_seen.line_number
            ),
        );
    } else {
        seen.insert(
            value.to_string(),
            SeenEventRef {
                logical_path: logical_path.to_string(),
                line_number,
            },
        );
    }
}

fn check_value_safety(
    value: &Value,
    field_path: &str,
    logical_path: &str,
    line_number: usize,
    counts: &mut RootCounts,
    issue_samples: &mut Vec<EventLogIssueSample>,
    max_samples: usize,
) {
    match value {
        Value::String(text) => {
            if unsafe_string_reason(text).is_some() {
                counts.unsafe_string_count += 1;
                push_issue_sample(
                    issue_samples,
                    max_samples,
                    "unsafe_string",
                    logical_path.to_string(),
                    Some(line_number),
                    field_path,
                );
            }
        }
        Value::Array(items) => {
            for (index, item) in items.iter().enumerate() {
                check_value_safety(
                    item,
                    &format!("{field_path}[{index}]"),
                    logical_path,
                    line_number,
                    counts,
                    issue_samples,
                    max_samples,
                );
            }
        }
        Value::Object(map) => {
            for (key, item) in map {
                check_value_safety(
                    item,
                    &format!("{field_path}.{key}"),
                    logical_path,
                    line_number,
                    counts,
                    issue_samples,
                    max_samples,
                );
            }
        }
        _ => {}
    }
}

fn unsafe_string_reason(text: &str) -> Option<&'static str> {
    let lower = text.to_ascii_lowercase().replace('\\', "/");
    if text.chars().count() > MAX_STRING_CHARS {
        return Some("long string");
    }
    if lower.contains("c:/users/")
        || lower.contains("/users/")
        || lower.contains("appdata/")
        || lower.contains("git projects/")
        || lower.contains("onedrive/")
    {
        return Some("local path marker");
    }
    if lower.contains("aws_secret_access_key")
        || lower.contains("aws_access_key_id")
        || lower.contains("-----begin ")
        || lower.contains("password=")
        || lower.contains("token=")
        || lower.contains("secret=")
        || lower.starts_with("postgres://")
        || lower.starts_with("postgresql://")
        || lower.starts_with("mysql://")
        || lower.starts_with("mongodb://")
    {
        return Some("credential marker");
    }
    if looks_like_table_row(text) {
        return Some("table-like row");
    }
    None
}

fn looks_like_table_row(text: &str) -> bool {
    if text.contains('\n') || text.contains('\r') {
        return true;
    }
    let comma_count = text.matches(',').count();
    let pipe_count = text.matches('|').count();
    let tab_count = text.matches('\t').count();
    comma_count >= 4 || pipe_count >= 4 || tab_count >= 1
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

fn logical_path(root: &RootSpec, path: &Path) -> Result<String> {
    let relative = path
        .strip_prefix(&root.path)
        .with_context(|| format!("derive logical path under {}", root.alias))?
        .to_string_lossy()
        .replace('\\', "/");
    Ok(format!("{}/{}", root.alias.trim_end_matches('/'), relative))
}

fn push_issue_sample(
    samples: &mut Vec<EventLogIssueSample>,
    max_samples: usize,
    issue_type: &str,
    logical_path: String,
    line_number: Option<usize>,
    detail: &str,
) {
    if samples.len() >= max_samples {
        return;
    }
    samples.push(EventLogIssueSample {
        issue_type: issue_type.to_string(),
        logical_path,
        line_number,
        detail: detail.to_string(),
    });
}

fn add_counts(left: &mut RootCounts, right: &RootCounts) {
    left.checked_file_count += right.checked_file_count;
    left.jsonl_file_count += right.jsonl_file_count;
    left.event_record_count += right.event_record_count;
    left.malformed_jsonl_row_count += right.malformed_jsonl_row_count;
    left.invalid_utf8_row_count += right.invalid_utf8_row_count;
    left.oversized_jsonl_row_count += right.oversized_jsonl_row_count;
    left.non_object_row_count += right.non_object_row_count;
    left.missing_required_field_count += right.missing_required_field_count;
    left.invalid_field_value_count += right.invalid_field_value_count;
    left.duplicate_event_id_count += right.duplicate_event_id_count;
    left.duplicate_dedupe_key_count += right.duplicate_dedupe_key_count;
    left.unsafe_string_count += right.unsafe_string_count;
}
