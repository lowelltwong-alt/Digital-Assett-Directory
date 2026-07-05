use crate::models::{
    RepoInventoryProbeArgs, RepoInventoryProbeRecord, RepoInventoryProbeRootSummary,
    RepoInventoryProbeSummary, RepoInventorySkippedDir,
};
use anyhow::{Context, Result, bail};
use serde_json::Value;
use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

const CONTRACT_MAX_BYTES: u64 = 64_000;
const POSIX_USER_SHIMS: [&str; 2] = ["~/.dad/bin/asset-dir", "$HOME/.dad/bin/asset-dir"];
const WINDOWS_USER_SHIMS: [&str; 3] = [
    "~/.dad/bin/asset-dir.ps1",
    "$HOME/.dad/bin/asset-dir.ps1",
    "$HOME\\.dad\\bin\\asset-dir.ps1",
];
const RAW_CHECKOUT_FALLBACKS: [&str; 4] = [
    "PYTHONPATH=src python -m digital_asset_directory.cli",
    "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli",
    "$env:PYTHONPATH=\"src\"; python -m digital_asset_directory.cli",
    "set PYTHONPATH=src && python -m digital_asset_directory.cli",
];

#[derive(Debug)]
struct RootSpec {
    path: PathBuf,
    alias: String,
}

#[derive(Debug, Default)]
struct RootProbe {
    repos: Vec<RepoInventoryProbeRecord>,
    skipped_dirs: Vec<RepoInventorySkippedDir>,
}

#[derive(Debug, Clone)]
struct RepoIntegrationContractProbe {
    present: bool,
    parse_status: String,
    schema_version_present: bool,
    repo_id_present: bool,
    capture_surface_version_present: bool,
    cli_fallback_present: bool,
    stable_user_shim_present: bool,
    windows_user_shim_present: bool,
    raw_checkout_fallback_present: bool,
    stable_shim_before_raw_checkout: bool,
    structural_pass: bool,
    issue_codes: Vec<String>,
}

pub fn probe_repo_inventory(args: RepoInventoryProbeArgs) -> Result<RepoInventoryProbeSummary> {
    validate_args(&args)?;
    let roots = root_specs(&args);
    let mut root_summaries = Vec::with_capacity(roots.len());
    let mut repos = Vec::new();
    let mut skipped_dirs = Vec::new();

    for root in roots {
        let probe = if root.path.exists() {
            inspect_root(&root, &args)?
        } else {
            RootProbe::default()
        };
        let status = if root.path.exists() {
            if root.path.is_dir() {
                "checked"
            } else {
                "not_directory"
            }
        } else {
            "missing"
        };
        root_summaries.push(RepoInventoryProbeRootSummary {
            root_alias: root.alias.clone(),
            status: status.to_string(),
            repo_count: probe.repos.len(),
            skipped_dir_count: probe.skipped_dirs.len(),
        });
        repos.extend(probe.repos);
        skipped_dirs.extend(probe.skipped_dirs);
    }

    root_summaries.sort_by(|left, right| left.root_alias.cmp(&right.root_alias));
    repos.sort_by(|left, right| left.logical_path.cmp(&right.logical_path));
    skipped_dirs.sort_by(|left, right| left.logical_path.cmp(&right.logical_path));

    Ok(RepoInventoryProbeSummary {
        schema_version: "dad_repo_inventory_probe.v0_2".to_string(),
        root_count: root_summaries.len(),
        repo_count: repos.len(),
        skipped_dir_count: skipped_dirs.len(),
        roots: root_summaries,
        repos,
        skipped_dirs,
        no_mutation_performed: true,
        authority_boundary: concat!(
            "Rust repo-inventory probing reports read-only structural facts only. ",
            "Python DAD deployment doctor and inventory remain authoritative for ",
            "policy, classification, public-safe redaction, enrollment, delivery, ",
            "readiness, and human gates."
        )
        .to_string(),
    })
}

fn validate_args(args: &RepoInventoryProbeArgs) -> Result<()> {
    if args.roots.is_empty() {
        bail!("provide at least one --root");
    }
    if args.roots.len() != args.root_aliases.len() {
        bail!("provide exactly one --root-alias for each --root");
    }
    if args.max_depth == 0 {
        bail!("--max-depth must be greater than zero");
    }
    if args.follow_symlinks {
        bail!("--follow-symlinks is disabled until external target provenance is implemented");
    }
    let mut aliases = BTreeSet::new();
    for alias in &args.root_aliases {
        validate_alias(alias)?;
        if !aliases.insert(alias.as_str()) {
            bail!("--root-alias values must be unique");
        }
    }
    Ok(())
}

fn root_specs(args: &RepoInventoryProbeArgs) -> Vec<RootSpec> {
    args.roots
        .iter()
        .zip(args.root_aliases.iter())
        .map(|(path, alias)| RootSpec {
            path: path.canonicalize().unwrap_or_else(|_| path.to_path_buf()),
            alias: alias.to_string(),
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

fn inspect_root(root: &RootSpec, args: &RepoInventoryProbeArgs) -> Result<RootProbe> {
    let mut probe = RootProbe::default();
    if !root.path.is_dir() {
        return Ok(probe);
    }
    let mut walker = WalkDir::new(&root.path)
        .follow_links(false)
        .max_depth(args.max_depth + 1)
        .into_iter();

    while let Some(item) = walker.next() {
        let entry = match item {
            Ok(entry) => entry,
            Err(error) => {
                if let Some(path) = error.path() {
                    let logical_path =
                        logical_path(root, path).unwrap_or_else(|_| root.alias.clone());
                    probe.skipped_dirs.push(RepoInventorySkippedDir {
                        root_alias: root.alias.clone(),
                        logical_path,
                        reason: "walk error".to_string(),
                    });
                }
                continue;
            }
        };
        if !entry.file_type().is_dir() {
            continue;
        }
        if entry.depth() > 0
            && let Some(reason) = skip_dir_reason(&entry.file_name().to_string_lossy())
        {
            probe.skipped_dirs.push(RepoInventorySkippedDir {
                root_alias: root.alias.clone(),
                logical_path: logical_path(root, entry.path())?,
                reason: reason.to_string(),
            });
            walker.skip_current_dir();
            continue;
        }
        if entry.depth() > args.max_depth {
            continue;
        }
        if let Some(marker_type) = git_marker_type(entry.path()) {
            let contract = inspect_integration_contract(entry.path());
            probe.repos.push(RepoInventoryProbeRecord {
                root_alias: root.alias.clone(),
                logical_path: logical_path(root, entry.path())?,
                depth: entry.depth(),
                git_marker_type: marker_type.to_string(),
                contract_present: contract.present,
                contract_parse_status: contract.parse_status,
                contract_schema_version_present: contract.schema_version_present,
                contract_repo_id_present: contract.repo_id_present,
                contract_capture_surface_version_present: contract.capture_surface_version_present,
                contract_cli_fallback_present: contract.cli_fallback_present,
                contract_stable_user_shim_present: contract.stable_user_shim_present,
                contract_windows_user_shim_present: contract.windows_user_shim_present,
                contract_raw_checkout_fallback_present: contract.raw_checkout_fallback_present,
                contract_stable_shim_before_raw_checkout: contract.stable_shim_before_raw_checkout,
                contract_structural_pass: contract.structural_pass,
                contract_issue_codes: contract.issue_codes,
                no_mutation_performed: true,
            });
        }
    }
    Ok(probe)
}

fn inspect_integration_contract(repo_path: &Path) -> RepoIntegrationContractProbe {
    let contract_path = repo_path
        .join(".digital-asset")
        .join("dad-integration.json");
    let mut probe = RepoIntegrationContractProbe {
        present: contract_path.is_file(),
        parse_status: "missing".to_string(),
        schema_version_present: false,
        repo_id_present: false,
        capture_surface_version_present: false,
        cli_fallback_present: false,
        stable_user_shim_present: false,
        windows_user_shim_present: false,
        raw_checkout_fallback_present: false,
        stable_shim_before_raw_checkout: false,
        structural_pass: false,
        issue_codes: Vec::new(),
    };

    if !probe.present {
        probe.issue_codes.push("contract_missing".to_string());
        return probe;
    }

    match fs::metadata(&contract_path) {
        Ok(metadata) if metadata.len() > CONTRACT_MAX_BYTES => {
            probe.parse_status = "oversized".to_string();
            probe.issue_codes.push("contract_oversized".to_string());
            return probe;
        }
        Ok(_) => {}
        Err(_) => {
            probe.parse_status = "read_error".to_string();
            probe.issue_codes.push("contract_read_error".to_string());
            return probe;
        }
    }

    let text = match fs::read_to_string(&contract_path) {
        Ok(text) => text,
        Err(_) => {
            probe.parse_status = "read_error".to_string();
            probe.issue_codes.push("contract_read_error".to_string());
            return probe;
        }
    };
    let value: Value = match serde_json::from_str(&text) {
        Ok(value) => value,
        Err(_) => {
            probe.parse_status = "malformed_json".to_string();
            probe
                .issue_codes
                .push("contract_malformed_json".to_string());
            return probe;
        }
    };
    let Some(object) = value.as_object() else {
        probe.parse_status = "non_object_json".to_string();
        probe
            .issue_codes
            .push("contract_non_object_json".to_string());
        return probe;
    };

    probe.parse_status = "present_parseable".to_string();
    probe.schema_version_present = non_empty_string(object.get("schema_version"));
    probe.repo_id_present = non_empty_string(object.get("repo_id"));
    let capture = object.get("capture").and_then(Value::as_object);
    probe.capture_surface_version_present = capture
        .and_then(|capture| capture.get("surface_version"))
        .is_some_and(|value| non_empty_string(Some(value)));
    let cli_fallback = capture
        .and_then(|capture| capture.get("cli_fallback"))
        .and_then(Value::as_str)
        .unwrap_or("");
    probe.cli_fallback_present = !cli_fallback.trim().is_empty();
    let posix_user_shim_index = first_index_without_suffix(cli_fallback, &POSIX_USER_SHIMS, ".ps1");
    let windows_user_shim_index = first_index_of_any(cli_fallback, &WINDOWS_USER_SHIMS);
    let raw_checkout_fallback_index = first_index_of_any(cli_fallback, &RAW_CHECKOUT_FALLBACKS);
    probe.stable_user_shim_present = posix_user_shim_index.is_some();
    probe.windows_user_shim_present = windows_user_shim_index.is_some();
    probe.raw_checkout_fallback_present = raw_checkout_fallback_index.is_some();
    probe.stable_shim_before_raw_checkout = posix_user_shim_index
        .zip(windows_user_shim_index)
        .zip(raw_checkout_fallback_index)
        .is_some_and(|((posix, windows), raw)| posix < raw && windows < raw);

    if !probe.schema_version_present {
        probe
            .issue_codes
            .push("contract_missing_schema_version".to_string());
    }
    if !probe.repo_id_present {
        probe
            .issue_codes
            .push("contract_missing_repo_id".to_string());
    }
    if !probe.capture_surface_version_present {
        probe
            .issue_codes
            .push("contract_missing_capture_surface_version".to_string());
    }
    if !probe.cli_fallback_present {
        probe
            .issue_codes
            .push("contract_missing_cli_fallback".to_string());
    }
    if !probe.stable_user_shim_present {
        probe
            .issue_codes
            .push("contract_missing_stable_user_shim".to_string());
    }
    if !probe.windows_user_shim_present {
        probe
            .issue_codes
            .push("contract_missing_windows_user_shim".to_string());
    }
    if !probe.raw_checkout_fallback_present {
        probe
            .issue_codes
            .push("contract_missing_raw_checkout_fallback".to_string());
    }
    if !probe.stable_shim_before_raw_checkout {
        probe
            .issue_codes
            .push("contract_stable_shim_not_before_raw_checkout".to_string());
    }
    probe.issue_codes.sort();
    probe.structural_pass = probe.issue_codes.is_empty();
    probe
}

fn non_empty_string(value: Option<&Value>) -> bool {
    value
        .and_then(Value::as_str)
        .is_some_and(|value| !value.trim().is_empty())
}

fn first_index_of_any(haystack: &str, needles: &[&str]) -> Option<usize> {
    needles
        .iter()
        .filter_map(|needle| haystack.find(needle))
        .min()
}

fn first_index_without_suffix(
    haystack: &str,
    needles: &[&str],
    excluded_suffix: &str,
) -> Option<usize> {
    needles
        .iter()
        .filter_map(|needle| {
            let mut search_start = 0;
            while search_start < haystack.len() {
                let offset = haystack[search_start..].find(needle)?;
                let index = search_start + offset;
                let suffix_start = index + needle.len();
                if !haystack[suffix_start..].starts_with(excluded_suffix) {
                    return Some(index);
                }
                search_start = suffix_start;
            }
            None
        })
        .min()
}

fn skip_dir_reason(name: &str) -> Option<&'static str> {
    let lowered = name.to_ascii_lowercase();
    if matches!(
        lowered.as_str(),
        ".git"
            | ".hg"
            | ".svn"
            | ".venv"
            | "venv"
            | "env"
            | "node_modules"
            | "dist"
            | "build"
            | ".next"
            | "coverage"
            | "__pycache__"
            | ".pytest_cache"
            | ".ruff_cache"
            | ".mypy_cache"
            | ".nox"
            | ".tox"
            | ".pytest-tmp-root"
            | "_codex_worktrees"
            | ".worktrees"
            | "target"
    ) {
        return Some("repo discovery skip directory");
    }
    if lowered.starts_with("pytest-of-")
        || lowered.starts_with("pytest_tmp")
        || lowered.starts_with("pytest-tmp")
    {
        return Some("pytest temp workspace");
    }
    None
}

fn git_marker_type(path: &Path) -> Option<&'static str> {
    let marker = path.join(".git");
    if marker.is_dir() {
        Some("directory")
    } else if marker.is_file() {
        Some("file")
    } else {
        None
    }
}

fn logical_path(root: &RootSpec, path: &Path) -> Result<String> {
    let relative = path
        .strip_prefix(&root.path)
        .with_context(|| format!("derive logical path under {}", root.alias))?;
    let segments = relative
        .components()
        .filter_map(|component| match component {
            std::path::Component::Normal(segment) => {
                Some(public_safe_segment(&segment.to_string_lossy()))
            }
            _ => None,
        })
        .collect::<Vec<_>>();
    if segments.is_empty() {
        Ok(root.alias.clone())
    } else {
        Ok(format!(
            "{}/{}",
            root.alias.trim_end_matches('/'),
            segments.join("/")
        ))
    }
}

fn public_safe_segment(raw: &str) -> String {
    let mut out = String::with_capacity(raw.len());
    let mut previous_dash = false;
    for character in raw.chars() {
        let mapped = if character.is_ascii_alphanumeric() || matches!(character, '-' | '_' | '.') {
            character.to_ascii_lowercase()
        } else {
            '-'
        };
        if mapped == '-' {
            if !previous_dash {
                out.push(mapped);
            }
            previous_dash = true;
        } else {
            out.push(mapped);
            previous_dash = false;
        }
    }
    let cleaned = out.trim_matches('-').to_string();
    if cleaned.is_empty() || cleaned == "." || cleaned == ".." {
        "unnamed".to_string()
    } else {
        cleaned
    }
}
