use crate::models::{
    Phase8EvidenceCheckArgs, Phase8EvidenceCheckSummary, Phase8EvidenceIssueSample,
};
use anyhow::{Context, Result, bail};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

const SCHEMA_VERSION: &str = "dad_phase8_evidence_check.v0_1";
const COMMAND_EVIDENCE_SCHEMA_VERSION: &str = "dad.phase8.command-evidence.v1";

const REQUIRED_COMMANDS: &[&str] = &[
    "python -m pytest tests/test_dad_local_deployment.py -q",
    "python -m digital_asset_directory.cli doctor --hub . --scope deployment",
    "user-shim asset-dir doctor --scope deployment from two non-DAD repos",
    "user-shim asset-dir doctor --scope deployment from Mock Trial4.26 and LawFirm-os-intake without target worktree changes",
    "user-shim asset-dir agent preflight --repo . --agent codex --task \"Goal 1 deployment smoke from outside DAD\"",
];

#[derive(Debug, Default)]
struct Counts {
    observed_command_count: usize,
    passed_required_command_count: usize,
    missing_required_command_count: usize,
    non_passed_required_command_count: usize,
    schema_issue_count: usize,
    unsafe_string_count: usize,
}

pub fn check_phase8_evidence(args: Phase8EvidenceCheckArgs) -> Result<Phase8EvidenceCheckSummary> {
    validate_args(&args)?;
    let mut issue_samples = Vec::new();
    let mut counts = Counts::default();
    let mut human_review_status = String::new();

    let checked_file_status = if !args.commands.exists() {
        counts.schema_issue_count += 1;
        push_issue_sample(
            &mut issue_samples,
            args.max_samples,
            "missing_file",
            &args.commands_alias,
            "command evidence file is missing",
        );
        "missing".to_string()
    } else if !args.commands.is_file() {
        counts.schema_issue_count += 1;
        push_issue_sample(
            &mut issue_samples,
            args.max_samples,
            "not_file",
            &args.commands_alias,
            "command evidence path is not a file",
        );
        "not_file".to_string()
    } else {
        let text = fs::read_to_string(&args.commands)
            .with_context(|| format!("read {}", args.commands.display()))?;
        match serde_json::from_str::<Value>(&text) {
            Ok(Value::Object(object)) => {
                inspect_payload(
                    &object,
                    &args,
                    &mut counts,
                    &mut issue_samples,
                    &mut human_review_status,
                );
            }
            Ok(_) => {
                counts.schema_issue_count += 1;
                push_issue_sample(
                    &mut issue_samples,
                    args.max_samples,
                    "non_object_json",
                    &args.commands_alias,
                    "command evidence must be a JSON object",
                );
            }
            Err(_) => {
                counts.schema_issue_count += 1;
                push_issue_sample(
                    &mut issue_samples,
                    args.max_samples,
                    "malformed_json",
                    &args.commands_alias,
                    "command evidence is not valid JSON",
                );
            }
        }
        "checked".to_string()
    };

    issue_samples.sort_by(|left, right| {
        left.logical_path
            .cmp(&right.logical_path)
            .then(left.issue_type.cmp(&right.issue_type))
            .then(left.detail.cmp(&right.detail))
    });
    if issue_samples.len() > args.max_samples {
        issue_samples.truncate(args.max_samples);
    }

    let issue_count = counts.missing_required_command_count
        + counts.non_passed_required_command_count
        + counts.schema_issue_count
        + counts.unsafe_string_count;
    let structural_clean = checked_file_status == "checked" && issue_count == 0;
    let human_review_pending = human_review_status == "pending";

    Ok(Phase8EvidenceCheckSummary {
        schema_version: SCHEMA_VERSION.to_string(),
        checked_file_alias: args.commands_alias,
        checked_file_status,
        required_command_count: REQUIRED_COMMANDS.len(),
        observed_command_count: counts.observed_command_count,
        passed_required_command_count: counts.passed_required_command_count,
        missing_required_command_count: counts.missing_required_command_count,
        non_passed_required_command_count: counts.non_passed_required_command_count,
        schema_issue_count: counts.schema_issue_count,
        unsafe_string_count: counts.unsafe_string_count,
        issue_count,
        human_review_status,
        human_review_pending,
        phase8_evidence_structural_clean: structural_clean,
        phase8_human_gate_satisfied: false,
        issue_samples,
        no_mutation_performed: true,
        authority_boundary: concat!(
            "Rust Phase 8 evidence check is read-only structural evidence. ",
            "Python roadmap validation and human gate review remain authoritative."
        )
        .to_string(),
        authoritative_gate: "roadmap check plus human gate review".to_string(),
        semantic_checks_not_performed: vec![
            "human gate approval".to_string(),
            "live command rerun".to_string(),
            "cross-repo write authorization".to_string(),
            "public release approval".to_string(),
        ],
    })
}

fn inspect_payload(
    object: &serde_json::Map<String, Value>,
    args: &Phase8EvidenceCheckArgs,
    counts: &mut Counts,
    issue_samples: &mut Vec<Phase8EvidenceIssueSample>,
    human_review_status: &mut String,
) {
    validate_top_level_fields(object, args, counts, issue_samples);
    check_strings_for_unsafe_markers(
        &Value::Object(object.clone()),
        "root",
        args,
        counts,
        issue_samples,
    );

    *human_review_status = object
        .get("human_review_status")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    if human_review_status != "pending" {
        counts.schema_issue_count += 1;
        push_issue_sample(
            issue_samples,
            args.max_samples,
            "unexpected_human_review_status",
            &args.commands_alias,
            "human_review_status must be pending until human gates are recorded elsewhere",
        );
    }

    let authority_boundary = object
        .get("authority_boundary")
        .and_then(Value::as_str)
        .unwrap_or("");
    let lower_boundary = authority_boundary.to_ascii_lowercase();
    if lower_boundary.contains("satisfy human gates") && !lower_boundary.contains("does not") {
        counts.schema_issue_count += 1;
        push_issue_sample(
            issue_samples,
            args.max_samples,
            "false_authority_claim",
            &args.commands_alias,
            "authority boundary appears to claim human gate satisfaction",
        );
    }

    let mut observed: BTreeMap<String, String> = BTreeMap::new();
    match object.get("commands") {
        Some(Value::Array(commands)) => {
            counts.observed_command_count = commands.len();
            for (index, command_value) in commands.iter().enumerate() {
                let Some(command_object) = command_value.as_object() else {
                    counts.schema_issue_count += 1;
                    push_issue_sample(
                        issue_samples,
                        args.max_samples,
                        "invalid_field_value",
                        &format!("{}/commands/{index}", args.commands_alias),
                        "command evidence row must be an object",
                    );
                    continue;
                };
                let command = command_object
                    .get("command")
                    .and_then(Value::as_str)
                    .unwrap_or("");
                let status = command_object
                    .get("status")
                    .and_then(Value::as_str)
                    .unwrap_or("");
                if command.is_empty() || status.is_empty() {
                    counts.schema_issue_count += 1;
                    push_issue_sample(
                        issue_samples,
                        args.max_samples,
                        "missing_required_field",
                        &format!("{}/commands/{index}", args.commands_alias),
                        "command rows require command and status",
                    );
                    continue;
                }
                observed.insert(command.to_string(), status.to_string());
            }
        }
        _ => {
            counts.schema_issue_count += 1;
            push_issue_sample(
                issue_samples,
                args.max_samples,
                "missing_required_field",
                &args.commands_alias,
                "commands array is required",
            );
        }
    }

    let required: BTreeSet<&str> = REQUIRED_COMMANDS.iter().copied().collect();
    for required_command in required {
        match observed.get(required_command) {
            Some(status) if status == "passed" => counts.passed_required_command_count += 1,
            Some(_) => {
                counts.non_passed_required_command_count += 1;
                push_issue_sample(
                    issue_samples,
                    args.max_samples,
                    "non_passed_required_command",
                    &args.commands_alias,
                    required_command,
                );
            }
            None => {
                counts.missing_required_command_count += 1;
                push_issue_sample(
                    issue_samples,
                    args.max_samples,
                    "missing_required_command",
                    &args.commands_alias,
                    required_command,
                );
            }
        }
    }
}

fn validate_top_level_fields(
    object: &serde_json::Map<String, Value>,
    args: &Phase8EvidenceCheckArgs,
    counts: &mut Counts,
    issue_samples: &mut Vec<Phase8EvidenceIssueSample>,
) {
    let required_fields = [
        "schema_version",
        "authority_boundary",
        "commands",
        "created_at",
        "human_review_status",
    ];
    for field in required_fields {
        if !object.contains_key(field) {
            counts.schema_issue_count += 1;
            push_issue_sample(
                issue_samples,
                args.max_samples,
                "missing_required_field",
                &args.commands_alias,
                field,
            );
        }
    }
    if object.get("schema_version").and_then(Value::as_str) != Some(COMMAND_EVIDENCE_SCHEMA_VERSION)
    {
        counts.schema_issue_count += 1;
        push_issue_sample(
            issue_samples,
            args.max_samples,
            "invalid_field_value",
            &args.commands_alias,
            "schema_version",
        );
    }
    if object
        .get("authority_boundary")
        .and_then(Value::as_str)
        .unwrap_or("")
        .trim()
        .is_empty()
    {
        counts.schema_issue_count += 1;
        push_issue_sample(
            issue_samples,
            args.max_samples,
            "missing_required_field",
            &args.commands_alias,
            "authority_boundary",
        );
    }
}

fn check_strings_for_unsafe_markers(
    value: &Value,
    field_path: &str,
    args: &Phase8EvidenceCheckArgs,
    counts: &mut Counts,
    issue_samples: &mut Vec<Phase8EvidenceIssueSample>,
) {
    match value {
        Value::String(text) => {
            if unsafe_string_reason(text).is_some() {
                counts.unsafe_string_count += 1;
                push_issue_sample(
                    issue_samples,
                    args.max_samples,
                    "unsafe_string",
                    &args.commands_alias,
                    field_path,
                );
            }
        }
        Value::Array(items) => {
            for (index, item) in items.iter().enumerate() {
                check_strings_for_unsafe_markers(
                    item,
                    &format!("{field_path}[{index}]"),
                    args,
                    counts,
                    issue_samples,
                );
            }
        }
        Value::Object(map) => {
            for (key, item) in map {
                check_strings_for_unsafe_markers(
                    item,
                    &format!("{field_path}.{key}"),
                    args,
                    counts,
                    issue_samples,
                );
            }
        }
        _ => {}
    }
}

fn unsafe_string_reason(text: &str) -> Option<&'static str> {
    let lower = text.to_ascii_lowercase().replace('\\', "/");
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
    None
}

fn validate_args(args: &Phase8EvidenceCheckArgs) -> Result<()> {
    validate_alias(&args.commands_alias)?;
    Ok(())
}

fn validate_alias(alias: &str) -> Result<()> {
    if alias.is_empty() || alias.trim() != alias {
        bail!("--commands-alias must be a non-empty public-safe relative alias");
    }
    if alias.contains('\\') || alias.contains(':') || Path::new(alias).is_absolute() {
        bail!("--commands-alias must use forward-slash relative segments only");
    }
    for segment in alias.split('/') {
        if segment.is_empty() || segment == "." || segment == ".." {
            bail!("--commands-alias must not contain empty, current, or parent segments");
        }
    }
    if !alias
        .chars()
        .all(|value| value.is_ascii_alphanumeric() || matches!(value, '/' | '-' | '_' | '.'))
    {
        bail!("--commands-alias contains unsupported characters");
    }
    Ok(())
}

fn push_issue_sample(
    samples: &mut Vec<Phase8EvidenceIssueSample>,
    max_samples: usize,
    issue_type: &str,
    logical_path: &str,
    detail: &str,
) {
    if samples.len() >= max_samples {
        return;
    }
    samples.push(Phase8EvidenceIssueSample {
        issue_type: issue_type.to_string(),
        logical_path: logical_path.to_string(),
        detail: detail.to_string(),
    });
}
