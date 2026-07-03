use crate::models::{ScanLocalArgs, SkippedPath};
use anyhow::Result;
use globset::{Glob, GlobMatcher};
use std::path::PathBuf;
use walkdir::WalkDir;

pub struct Discovery {
    pub included: Vec<PathBuf>,
    pub skipped: Vec<SkippedPath>,
    pub bounded: bool,
}

const DEFAULT_EXCLUDES: &[(&str, &str)] = &[
    ("**/.git/**", "git metadata"),
    ("**/.pytest_cache/**", "pytest cache"),
    ("**/.ruff_cache/**", "ruff cache"),
    ("**/.mypy_cache/**", "mypy cache"),
    ("**/.nox/**", "nox cache"),
    ("**/target/**", "rust build output"),
    ("**/__pycache__/**", "python bytecode cache"),
    ("**/.venv/**", "python virtual environment"),
    ("**/node_modules/**", "node dependency folder"),
    ("**/.DS_Store", "macOS metadata"),
    ("**/Thumbs.db", "Windows thumbnail metadata"),
    ("**/desktop.ini", "Windows folder metadata"),
];

pub fn discover_files(args: &ScanLocalArgs) -> Result<Discovery> {
    let mut matchers: Vec<(GlobMatcher, String)> = Vec::new();
    for (pattern, reason) in DEFAULT_EXCLUDES {
        matchers.push((Glob::new(pattern)?.compile_matcher(), (*reason).to_string()));
    }
    for pattern in &args.excludes {
        matchers.push((Glob::new(pattern)?.compile_matcher(), "user exclude".to_string()));
    }

    let mut included = Vec::new();
    let mut skipped = Vec::new();
    let mut bounded = false;

    let walker = WalkDir::new(&args.source).follow_links(args.follow_symlinks).into_iter();
    for entry in walker.filter_map(|item| item.ok()) {
        let path = entry.path();
        if path == args.source {
            continue;
        }
        let rel = path.strip_prefix(&args.source).unwrap_or(path);
        let rel_str = rel.to_string_lossy().replace('\\', "/");
        if entry.file_type().is_symlink() && !args.follow_symlinks {
            skipped.push(skip(args, &rel_str, "symlink refused"));
            continue;
        }
        if let Some(reason) = first_match_reason(&matchers, &rel_str) {
            skipped.push(skip(args, &rel_str, reason));
            continue;
        }
        if entry.file_type().is_file() {
            included.push(path.to_path_buf());
            if let Some(max) = args.max_files {
                if included.len() >= max {
                    bounded = true;
                    break;
                }
            }
        }
    }
    included.sort();
    Ok(Discovery { included, skipped, bounded })
}

fn first_match_reason<'a>(matchers: &'a [(GlobMatcher, String)], rel: &str) -> Option<&'a str> {
    matchers
        .iter()
        .find_map(|(matcher, reason)| matcher.is_match(rel).then_some(reason.as_str()))
}

fn skip(args: &ScanLocalArgs, rel: &str, reason: &str) -> SkippedPath {
    SkippedPath {
        logical_path: format!("{}/{}", args.path_alias.trim_end_matches('/'), rel),
        reason: reason.to_string(),
    }
}
