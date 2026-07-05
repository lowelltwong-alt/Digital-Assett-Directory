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
    (".git/**", "git metadata"),
    ("**/.git/**", "git metadata"),
    (".pytest_cache/**", "pytest cache"),
    ("**/.pytest_cache/**", "pytest cache"),
    (".ruff_cache/**", "ruff cache"),
    ("**/.ruff_cache/**", "ruff cache"),
    (".mypy_cache/**", "mypy cache"),
    ("**/.mypy_cache/**", "mypy cache"),
    (".nox/**", "nox cache"),
    ("**/.nox/**", "nox cache"),
    (".digital-asset/**", "DAD repo-local control surface"),
    ("**/.digital-asset/**", "DAD repo-local control surface"),
    ("raw/**", "DAD raw evidence surface"),
    ("processed/**", "DAD processed evidence surface"),
    ("state/**", "DAD state surface"),
    ("audit/**", "DAD audit surface"),
    ("target/**", "rust build output"),
    ("**/target/**", "rust build output"),
    ("__pycache__/**", "python bytecode cache"),
    ("**/__pycache__/**", "python bytecode cache"),
    (".venv/**", "python virtual environment"),
    ("**/.venv/**", "python virtual environment"),
    ("node_modules/**", "node dependency folder"),
    ("**/node_modules/**", "node dependency folder"),
    (".env", "environment/secrets file"),
    (".env.*", "environment/secrets file"),
    ("**/.env", "environment/secrets file"),
    ("**/.env.*", "environment/secrets file"),
    (".netrc", "credential config"),
    ("**/.netrc", "credential config"),
    (".npmrc", "credential config"),
    ("**/.npmrc", "credential config"),
    (".pypirc", "credential config"),
    ("**/.pypirc", "credential config"),
    ("id_rsa", "private key material"),
    ("**/id_rsa", "private key material"),
    ("id_ed25519", "private key material"),
    ("**/id_ed25519", "private key material"),
    ("*.pem", "key/certificate material"),
    ("**/*.pem", "key/certificate material"),
    ("*.key", "key/certificate material"),
    ("**/*.key", "key/certificate material"),
    ("*.p12", "key/certificate material"),
    ("**/*.p12", "key/certificate material"),
    ("*.pfx", "key/certificate material"),
    ("**/*.pfx", "key/certificate material"),
    ("*.crt", "certificate material"),
    ("**/*.crt", "certificate material"),
    ("*.cer", "certificate material"),
    ("**/*.cer", "certificate material"),
    ("*.der", "certificate material"),
    ("**/*.der", "certificate material"),
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
        matchers.push((
            Glob::new(pattern)?.compile_matcher(),
            "user exclude".to_string(),
        ));
    }

    let mut included = Vec::new();
    let mut skipped = Vec::new();
    let mut bounded = false;

    let mut walker = WalkDir::new(&args.source)
        .follow_links(args.follow_symlinks)
        .into_iter();
    while let Some(item) = walker.next() {
        let entry = match item {
            Ok(entry) => entry,
            Err(error) => {
                let rel = error
                    .path()
                    .and_then(|path| path.strip_prefix(&args.source).ok())
                    .map(|path| path.to_string_lossy().replace('\\', "/"))
                    .unwrap_or_else(|| "<unknown>".to_string());
                skipped.push(skip(args, &rel, &format!("walk error: {error}")));
                continue;
            }
        };
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
            if entry.file_type().is_dir() {
                skipped.push(skip(args, &rel_str, reason));
                walker.skip_current_dir();
            } else if entry.file_type().is_file() {
                skipped.push(skip(args, &rel_str, reason));
            }
            continue;
        }
        if entry.file_type().is_file() {
            included.push(path.to_path_buf());
        }
    }
    included.sort();
    skipped.sort_by(|left, right| left.logical_path.cmp(&right.logical_path));
    if let Some(max) = args.max_files
        && included.len() > max
    {
        included.truncate(max);
        bounded = true;
    }
    Ok(Discovery {
        included,
        skipped,
        bounded,
    })
}

fn first_match_reason<'a>(matchers: &'a [(GlobMatcher, String)], rel: &str) -> Option<&'a str> {
    if let Some(reason) = default_segment_reason(rel) {
        return Some(reason);
    }
    matchers
        .iter()
        .find_map(|(matcher, reason)| matcher.is_match(rel).then_some(reason.as_str()))
}

fn default_segment_reason(rel: &str) -> Option<&'static str> {
    match rel.split('/').next() {
        Some(".digital-asset") => return Some("DAD repo-local control surface"),
        Some("raw") => return Some("DAD raw evidence surface"),
        Some("processed") => return Some("DAD processed evidence surface"),
        Some("state") => return Some("DAD state surface"),
        Some("audit") => return Some("DAD audit surface"),
        _ => {}
    }
    for segment in rel.split('/') {
        match segment {
            ".git" => return Some("git metadata"),
            ".pytest_cache" => return Some("pytest cache"),
            ".ruff_cache" => return Some("ruff cache"),
            ".mypy_cache" => return Some("mypy cache"),
            ".nox" => return Some("nox cache"),
            ".digital-asset" => return Some("DAD repo-local control surface"),
            "target" => return Some("rust build output"),
            "__pycache__" => return Some("python bytecode cache"),
            ".venv" => return Some("python virtual environment"),
            "node_modules" => return Some("node dependency folder"),
            _ => {}
        }
    }
    None
}

fn skip(args: &ScanLocalArgs, rel: &str, reason: &str) -> SkippedPath {
    SkippedPath {
        logical_path: format!("{}/{}", args.path_alias.trim_end_matches('/'), rel),
        reason: reason.to_string(),
    }
}
