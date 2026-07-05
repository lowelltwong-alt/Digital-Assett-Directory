use std::collections::BTreeSet;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use dad_scan_core::{
    MailSpoolCheckArgs, MailSpoolCheckSummary, Observation, QuarantineReport,
    RepoInventoryProbeArgs, RepoInventoryProbeSummary, ScanLocalArgs, ScanSummary,
};
use serde::de::DeserializeOwned;

static CWD_LOCK: Mutex<()> = Mutex::new(());

struct CurrentDirGuard(std::path::PathBuf);

impl Drop for CurrentDirGuard {
    fn drop(&mut self) {
        let _ = env::set_current_dir(&self.0);
    }
}

fn default_args(source: impl Into<PathBuf>, out_dir: &Path) -> ScanLocalArgs {
    ScanLocalArgs {
        source: source.into(),
        source_id: "fixture".to_string(),
        path_alias: "fixture".to_string(),
        out: out_dir.join("observations.jsonl"),
        summary_out: out_dir.join("summary.json"),
        quarantine_out: out_dir.join("quarantine.json"),
        max_files: Some(10),
        max_content_hash_bytes: 1024 * 1024,
        follow_symlinks: false,
        excludes: vec![],
    }
}

fn read_json<T: DeserializeOwned>(path: &Path) -> T {
    serde_json::from_str(&fs::read_to_string(path).expect("json file")).expect("valid json")
}

fn read_observations(path: &Path) -> Vec<Observation> {
    fs::read_to_string(path)
        .expect("jsonl file")
        .lines()
        .map(|line| serde_json::from_str(line).expect("valid observation json"))
        .collect()
}

fn read_observation_values(path: &Path) -> Vec<serde_json::Value> {
    fs::read_to_string(path)
        .expect("jsonl file")
        .lines()
        .map(|line| serde_json::from_str(line).expect("valid observation json"))
        .collect()
}

fn mail_spool_args(root: impl Into<PathBuf>, alias: &str) -> MailSpoolCheckArgs {
    MailSpoolCheckArgs {
        roots: vec![root.into()],
        root_aliases: vec![alias.to_string()],
        max_jsonl_row_bytes: 1024,
        max_samples: 25,
    }
}

fn repo_probe_args(root: impl Into<PathBuf>, alias: &str) -> RepoInventoryProbeArgs {
    RepoInventoryProbeArgs {
        roots: vec![root.into()],
        root_aliases: vec![alias.to_string()],
        max_depth: 5,
        follow_symlinks: false,
    }
}

#[cfg(unix)]
fn create_file_symlink(target: &Path, link: &Path) -> std::io::Result<()> {
    std::os::unix::fs::symlink(target, link)
}

#[cfg(windows)]
fn create_file_symlink(target: &Path, link: &Path) -> std::io::Result<()> {
    std::os::windows::fs::symlink_file(target, link)
}

#[test]
fn scan_tiny_fixture_emits_observations() {
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    let out = temp.path().join("out").join("observations.jsonl");
    let summary = temp.path().join("out").join("summary.json");
    let quarantine = temp.path().join("out").join("quarantine.json");
    fs::create_dir_all(&source).expect("source dir");
    fs::write(source.join("README.md"), "# Demo\n").expect("write readme");

    let args = dad_scan_core::ScanLocalArgs {
        source,
        source_id: "fixture".to_string(),
        path_alias: "fixture".to_string(),
        out: out.clone(),
        summary_out: summary.clone(),
        quarantine_out: quarantine.clone(),
        max_files: Some(10),
        max_content_hash_bytes: 1024 * 1024,
        follow_symlinks: false,
        excludes: vec![],
    };
    let result = dad_scan_core::scan_local(args).expect("scan");
    assert_eq!(result.included_count, 1);
    let jsonl = fs::read_to_string(out).expect("jsonl");
    assert!(jsonl.contains("dad_scan_observation.v0_1"));
    assert!(jsonl.contains("no_mutation_performed"));
    assert!(summary.exists());
    assert!(quarantine.exists());
}

#[test]
fn scan_outputs_alias_only_structured_records() {
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    let out_dir = temp.path().join("out");
    fs::create_dir_all(source.join("docs")).expect("source dir");
    fs::write(source.join("docs").join("README.md"), "# Demo\n").expect("write readme");

    let args = default_args(&source, &out_dir);
    let out_path = args.out.clone();
    let summary_path = args.summary_out.clone();
    let quarantine_path = args.quarantine_out.clone();
    let result = dad_scan_core::scan_local(args).expect("scan");

    assert_eq!(result.source, "fixture");
    assert_eq!(result.output_jsonl, "observations.jsonl");
    assert_eq!(result.quarantine_report, "quarantine.json");
    assert!(result.no_mutation_performed);

    let observations = read_observations(&out_path);
    assert_eq!(observations.len(), 1);
    assert_eq!(observations[0].logical_path, "fixture/docs/README.md");
    assert_eq!(observations[0].source_id, "fixture");
    assert_eq!(observations[0].path_alias, "fixture");
    assert_eq!(observations[0].observation_type, "local_file_candidate");
    assert!(observations[0].no_mutation_performed);

    let summary: ScanSummary = read_json(&summary_path);
    assert_eq!(summary.included_count, 1);
    assert_eq!(summary.skipped_count, 0);
    assert!(!summary.bounded);

    let quarantine: QuarantineReport = read_json(&quarantine_path);
    assert_eq!(quarantine.skipped_count, 0);
    assert!(quarantine.no_mutation_performed);

    let temp_path = temp.path().to_string_lossy();
    assert!(
        !fs::read_to_string(&out_path)
            .expect("jsonl")
            .contains(temp_path.as_ref())
    );
    assert!(
        !fs::read_to_string(summary_path)
            .expect("summary")
            .contains(temp_path.as_ref())
    );
    assert!(
        !fs::read_to_string(quarantine_path)
            .expect("quarantine")
            .contains(temp_path.as_ref())
    );

    let values = read_observation_values(&out_path);
    let keys: BTreeSet<&str> = values[0]
        .as_object()
        .expect("observation object")
        .keys()
        .map(String::as_str)
        .collect();
    assert_eq!(
        keys,
        BTreeSet::from([
            "asset_type_hint",
            "content_hash_mode",
            "content_sha256",
            "extract_method",
            "logical_path",
            "metadata_sha256",
            "modified_unix_seconds",
            "no_mutation_performed",
            "observation_type",
            "path_alias",
            "schema_version",
            "size_bytes",
            "source_id",
        ])
    );
}

#[test]
fn scan_applies_user_excludes_and_records_quarantine_reason() {
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    let out_dir = temp.path().join("out");
    fs::create_dir_all(source.join("logs")).expect("source dir");
    fs::write(source.join("keep.md"), "keep\n").expect("write keep");
    fs::write(source.join("logs").join("private.secret"), "do not scan\n").expect("write secret");

    let mut args = default_args(&source, &out_dir);
    args.excludes.push("**/*.secret".to_string());
    let quarantine_path = args.quarantine_out.clone();
    let result = dad_scan_core::scan_local(args).expect("scan");

    assert_eq!(result.included_count, 1);
    assert_eq!(result.skipped_count, 1);
    let quarantine: QuarantineReport = read_json(&quarantine_path);
    assert_eq!(
        quarantine.skipped[0].logical_path,
        "fixture/logs/private.secret"
    );
    assert_eq!(quarantine.skipped[0].reason, "user exclude");
}

#[test]
fn scan_marks_bounded_when_max_files_limits_output() {
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    let out_dir = temp.path().join("out");
    fs::create_dir_all(&source).expect("source dir");
    fs::write(source.join("a.md"), "a\n").expect("write a");
    fs::write(source.join("b.md"), "b\n").expect("write b");
    fs::write(source.join("c.md"), "c\n").expect("write c");

    let mut args = default_args(&source, &out_dir);
    args.max_files = Some(2);
    let out_path = args.out.clone();
    let result = dad_scan_core::scan_local(args).expect("scan");

    assert_eq!(result.included_count, 2);
    assert!(result.bounded);
    assert_eq!(read_observations(&out_path).len(), 2);
}

#[test]
fn scan_max_files_selects_first_n_logical_paths_deterministically() {
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    let out_dir = temp.path().join("out");
    fs::create_dir_all(&source).expect("source dir");
    fs::write(source.join("z-last.md"), "z\n").expect("write z");
    fs::write(source.join("m-middle.md"), "m\n").expect("write m");
    fs::write(source.join("a-first.md"), "a\n").expect("write a");

    let mut args = default_args(&source, &out_dir);
    args.max_files = Some(2);
    let out_path = args.out.clone();
    dad_scan_core::scan_local(args).expect("scan");

    let logical_paths: Vec<String> = read_observations(&out_path)
        .into_iter()
        .map(|observation| observation.logical_path)
        .collect();
    assert_eq!(
        logical_paths,
        vec!["fixture/a-first.md", "fixture/m-middle.md"]
    );
}

#[test]
fn scan_emits_observations_in_deterministic_logical_path_order() {
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    let out_dir = temp.path().join("out");
    fs::create_dir_all(source.join("nested")).expect("source dir");
    fs::write(source.join("z-last.md"), "z\n").expect("write z");
    fs::write(source.join("a-first.md"), "a\n").expect("write a");
    fs::write(source.join("nested").join("middle.md"), "m\n").expect("write m");

    let args = default_args(&source, &out_dir);
    let out_path = args.out.clone();
    dad_scan_core::scan_local(args).expect("scan");

    let logical_paths: Vec<String> = read_observations(&out_path)
        .into_iter()
        .map(|observation| observation.logical_path)
        .collect();
    assert_eq!(
        logical_paths,
        vec![
            "fixture/a-first.md",
            "fixture/nested/middle.md",
            "fixture/z-last.md",
        ]
    );
}

#[test]
fn scan_applies_default_excludes_for_repo_noise() {
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    let out_dir = temp.path().join("out");
    fs::create_dir_all(source.join(".git")).expect("git dir");
    fs::create_dir_all(source.join("target").join("debug")).expect("target dir");
    fs::create_dir_all(source.join("__pycache__")).expect("pycache dir");
    fs::write(source.join("keep.md"), "keep\n").expect("write keep");
    fs::write(source.join(".git").join("config"), "[core]\n").expect("write git config");
    fs::write(
        source.join("target").join("debug").join("build.txt"),
        "build\n",
    )
    .expect("write target output");
    fs::write(source.join("__pycache__").join("module.pyc"), "bytecode\n").expect("write pycache");

    let args = default_args(&source, &out_dir);
    let quarantine_path = args.quarantine_out.clone();
    let result = dad_scan_core::scan_local(args).expect("scan");

    assert_eq!(result.included_count, 1);
    assert_eq!(result.skipped_count, 3);
    let quarantine: QuarantineReport = read_json(&quarantine_path);
    let reasons: Vec<(String, String)> = quarantine
        .skipped
        .into_iter()
        .map(|skipped| (skipped.logical_path, skipped.reason))
        .collect();
    assert_eq!(
        reasons,
        vec![
            ("fixture/.git".to_string(), "git metadata".to_string()),
            (
                "fixture/__pycache__".to_string(),
                "python bytecode cache".to_string(),
            ),
            (
                "fixture/target".to_string(),
                "rust build output".to_string(),
            ),
        ]
    );
}

#[test]
fn scan_applies_default_excludes_for_private_and_dad_surfaces() {
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    let out_dir = temp.path().join("out");
    fs::create_dir_all(source.join(".digital-asset").join("mail")).expect("mail dir");
    fs::create_dir_all(source.join("raw").join("local")).expect("raw dir");
    fs::create_dir_all(source.join("processed").join("reports")).expect("processed dir");
    fs::create_dir_all(source.join("state")).expect("state dir");
    fs::create_dir_all(source.join("audit").join("events")).expect("audit dir");
    fs::write(source.join("keep.md"), "keep\n").expect("write keep");
    fs::write(
        source
            .join(".digital-asset")
            .join("mail")
            .join("outbox.jsonl"),
        "mail candidate\n",
    )
    .expect("write outbox");
    fs::write(source.join("raw").join("local").join("secret.txt"), "raw\n").expect("write raw");
    fs::write(
        source.join("processed").join("reports").join("report.json"),
        "{}\n",
    )
    .expect("write report");
    fs::write(source.join("state").join("session.sqlite3"), "state\n").expect("write state");
    fs::write(
        source.join("audit").join("events").join("event.jsonl"),
        "audit\n",
    )
    .expect("write audit");
    fs::write(source.join(".env"), "TOKEN=secret\n").expect("write env");
    fs::write(source.join("server.pem"), "key\n").expect("write pem");
    fs::write(source.join("private.key"), "key\n").expect("write key");
    fs::write(source.join("id_rsa"), "key\n").expect("write ssh key");

    let args = default_args(&source, &out_dir);
    let out_path = args.out.clone();
    let quarantine_path = args.quarantine_out.clone();
    let result = dad_scan_core::scan_local(args).expect("scan");

    assert_eq!(result.included_count, 1);
    assert_eq!(
        read_observations(&out_path)[0].logical_path,
        "fixture/keep.md"
    );
    let quarantine: QuarantineReport = read_json(&quarantine_path);
    let reasons: Vec<(String, String)> = quarantine
        .skipped
        .into_iter()
        .map(|skipped| (skipped.logical_path, skipped.reason))
        .collect();
    assert_eq!(
        reasons,
        vec![
            (
                "fixture/.digital-asset".to_string(),
                "DAD repo-local control surface".to_string(),
            ),
            (
                "fixture/.env".to_string(),
                "environment/secrets file".to_string(),
            ),
            ("fixture/audit".to_string(), "DAD audit surface".to_string()),
            (
                "fixture/id_rsa".to_string(),
                "private key material".to_string(),
            ),
            (
                "fixture/private.key".to_string(),
                "key/certificate material".to_string(),
            ),
            (
                "fixture/processed".to_string(),
                "DAD processed evidence surface".to_string(),
            ),
            (
                "fixture/raw".to_string(),
                "DAD raw evidence surface".to_string()
            ),
            (
                "fixture/server.pem".to_string(),
                "key/certificate material".to_string(),
            ),
            ("fixture/state".to_string(), "DAD state surface".to_string()),
        ]
    );
}

#[test]
fn mail_spool_check_reports_alias_only_dirty_spool_signals() {
    let temp = tempfile::tempdir().expect("tempdir");
    let root = temp.path().join("mail-root");
    let inbox = root.join("processed").join("mail").join("inbox");
    let mailbox = root.join(".digital-asset").join("mail");
    let rust = root
        .join("mail")
        .join("outbox")
        .join("rust_rollout")
        .join("non_logos");
    fs::create_dir_all(&inbox).expect("inbox dir");
    fs::create_dir_all(&mailbox).expect("mailbox dir");
    fs::create_dir_all(&rust).expect("rust dir");
    fs::write(inbox.join("good.jsonl"), "{\"ok\": true}\n").expect("good jsonl");
    fs::write(inbox.join("bad.jsonl"), "{\"bad\"\n").expect("bad jsonl");
    fs::write(mailbox.join(".outbox.jsonl.lock"), "{}\n").expect("lock");
    fs::write(mailbox.join(".inbox.jsonl.tmp"), "partial\n").expect("tmp");
    fs::write(rust.join("repo.json"), "{\"packet\": true}\n").expect("rust packet");

    let summary = dad_scan_core::check_mail_spools(mail_spool_args(&root, "dad/mail"))
        .expect("mail spool check");
    let text = serde_json::to_string_pretty(&summary).expect("summary json");

    assert_eq!(summary.schema_version, "dad_mail_spool_check.v0_1");
    assert_eq!(summary.root_count, 1);
    assert_eq!(summary.jsonl_file_count, 2);
    assert_eq!(summary.lock_file_count, 1);
    assert_eq!(summary.temp_fragment_count, 1);
    assert_eq!(summary.rust_packet_count, 1);
    assert_eq!(summary.malformed_jsonl_row_count, 1);
    assert_eq!(summary.issue_count, 3);
    assert!(summary.no_mutation_performed);
    assert_eq!(summary.authoritative_gate, "mail doctor");
    assert!(
        summary
            .authority_boundary
            .contains("Python mail doctor remains the authoritative")
    );
    assert!(
        summary
            .semantic_checks_not_performed
            .contains(&"delivery log hash verification".to_string())
    );
    assert!(summary.issue_samples.iter().any(|sample| {
        sample.issue_type == "malformed_jsonl"
            && sample.logical_path == "dad/mail/processed/mail/inbox/bad.jsonl"
            && sample.line_number == Some(1)
    }));
    assert!(summary.issue_samples.iter().any(|sample| {
        sample.issue_type == "jsonl_lock"
            && sample.logical_path == "dad/mail/.digital-asset/mail/.outbox.jsonl.lock"
    }));
    assert!(!text.contains(temp.path().to_string_lossy().as_ref()));
}

#[test]
fn mail_spool_check_flags_oversized_rows_without_raw_content() {
    let temp = tempfile::tempdir().expect("tempdir");
    let root = temp.path().join("mail-root");
    fs::create_dir_all(&root).expect("root dir");
    fs::write(root.join("outbox.jsonl"), "{\"long\":\"abcdef\"}\n").expect("jsonl");

    let mut args = mail_spool_args(&root, "repo/mail");
    args.max_jsonl_row_bytes = 8;
    let summary = dad_scan_core::check_mail_spools(args).expect("mail spool check");
    let text = serde_json::to_string_pretty(&summary).expect("summary json");

    assert_eq!(summary.oversized_jsonl_row_count, 1);
    assert_eq!(
        summary.issue_samples[0].issue_type,
        "oversized_jsonl_record"
    );
    assert!(!text.contains("abcdef"));
}

#[test]
fn mail_spool_check_rejects_unsafe_aliases_and_mismatched_roots() {
    let temp = tempfile::tempdir().expect("tempdir");
    let root = temp.path().join("mail-root");
    fs::create_dir_all(&root).expect("root dir");

    let mut unsafe_alias = mail_spool_args(&root, "../mail");
    assert!(dad_scan_core::check_mail_spools(unsafe_alias.clone()).is_err());

    unsafe_alias.root_aliases = vec!["C:/mail".to_string()];
    assert!(dad_scan_core::check_mail_spools(unsafe_alias.clone()).is_err());

    unsafe_alias.root_aliases = vec![];
    assert!(dad_scan_core::check_mail_spools(unsafe_alias).is_err());
}

#[test]
fn mail_spool_check_is_deterministic_and_reports_missing_roots() {
    let temp = tempfile::tempdir().expect("tempdir");
    let first = temp.path().join("z-root");
    let second = temp.path().join("a-root");
    fs::create_dir_all(&first).expect("first root");
    fs::write(first.join("z.jsonl"), "{\"z\": true}\n").expect("z");
    fs::write(first.join("a.jsonl"), "not json\n").expect("a");

    let summary: MailSpoolCheckSummary = dad_scan_core::check_mail_spools(MailSpoolCheckArgs {
        roots: vec![first, second],
        root_aliases: vec!["z/root".to_string(), "a/root".to_string()],
        max_jsonl_row_bytes: 1024,
        max_samples: 25,
    })
    .expect("mail spool check");

    assert_eq!(
        summary
            .roots
            .iter()
            .map(|root| (root.root_alias.as_str(), root.status.as_str()))
            .collect::<Vec<_>>(),
        vec![("a/root", "missing"), ("z/root", "checked")]
    );
    assert_eq!(summary.issue_samples[0].logical_path, "z/root/a.jsonl");
}

#[test]
fn mail_spool_check_counts_overlapping_roots_once() {
    let temp = tempfile::tempdir().expect("tempdir");
    let central_mail = temp.path().join("processed").join("mail");
    let staging = central_mail
        .join("staged")
        .join("rust_rollout")
        .join("non_logos");
    fs::create_dir_all(&staging).expect("staging dir");
    fs::write(staging.join("repo.json"), "{\"packet\": true}\n").expect("rust packet");

    let summary: MailSpoolCheckSummary = dad_scan_core::check_mail_spools(MailSpoolCheckArgs {
        roots: vec![central_mail, staging],
        root_aliases: vec![
            "dad/central-mail".to_string(),
            "dad/rust-rollout-staging".to_string(),
        ],
        max_jsonl_row_bytes: 1024,
        max_samples: 25,
    })
    .expect("mail spool check");

    assert_eq!(summary.rust_packet_count, 1);
    assert_eq!(summary.checked_file_count, 1);
}

#[test]
fn repo_inventory_probe_discovers_git_roots_alias_only() {
    let temp = tempfile::tempdir().expect("tempdir");
    let root = temp.path().join("workspace");
    let repo = root.join("repo-a");
    let nested = root.join("parent").join("vendor").join("repo-b");
    fs::create_dir_all(repo.join(".git")).expect("repo git");
    fs::create_dir_all(repo.join(".digital-asset")).expect("repo contract dir");
    fs::write(
        repo.join(".digital-asset").join("dad-integration.json"),
        "{\"repo_id\":\"repo-a\"}\n",
    )
    .expect("contract");
    fs::create_dir_all(nested.join(".git")).expect("nested git");
    fs::create_dir_all(root.join("node_modules").join("hidden").join(".git")).expect("node git");
    fs::create_dir_all(
        root.join("pytest_tmp_dirty_mail")
            .join("hidden")
            .join(".git"),
    )
    .expect("pytest git");

    let summary = dad_scan_core::probe_repo_inventory(repo_probe_args(&root, "local/workspace"))
        .expect("repo probe");
    let text = serde_json::to_string_pretty(&summary).expect("summary json");
    let logical_paths: Vec<String> = summary
        .repos
        .iter()
        .map(|repo| repo.logical_path.clone())
        .collect();

    assert_eq!(summary.schema_version, "dad_repo_inventory_probe.v0_2");
    assert_eq!(summary.repo_count, 2);
    assert_eq!(
        logical_paths,
        vec![
            "local/workspace/parent/vendor/repo-b".to_string(),
            "local/workspace/repo-a".to_string(),
        ]
    );
    assert!(
        summary
            .repos
            .iter()
            .any(|item| item.logical_path == "local/workspace/repo-a"
                && item.contract_present
                && item.git_marker_type == "directory")
    );
    assert!(
        summary
            .skipped_dirs
            .iter()
            .any(|item| item.logical_path == "local/workspace/node_modules")
    );
    assert!(
        summary
            .skipped_dirs
            .iter()
            .any(|item| item.logical_path == "local/workspace/pytest_tmp_dirty_mail")
    );
    assert!(summary.skipped_dirs.iter().all(|item| matches!(
        item.reason.as_str(),
        "repo discovery skip directory" | "pytest temp workspace" | "walk error"
    )));
    assert!(!text.contains(temp.path().to_string_lossy().as_ref()));
}

#[test]
fn repo_inventory_probe_reports_contract_surface_without_raw_values() {
    let temp = tempfile::tempdir().expect("tempdir");
    let root = temp.path().join("workspace");
    let valid = root.join("valid-repo");
    let malformed = root.join("malformed-repo");
    let missing = root.join("missing-repo");
    fs::create_dir_all(valid.join(".git")).expect("valid git");
    fs::create_dir_all(valid.join(".digital-asset")).expect("valid contract dir");
    fs::write(
        valid.join(".digital-asset").join("dad-integration.json"),
        r#"{
          "schema_version": "dad.repo_integration.v1",
          "repo_id": "repo-valid-secret-ish-id",
          "capture": {
            "surface_version": "dad-capture.v1",
            "cli_fallback": "~/.dad/bin/asset-dir or ~/.dad/bin/asset-dir.ps1; PYTHONPATH=src python -m digital_asset_directory.cli"
          }
        }"#,
    )
    .expect("valid contract");
    fs::create_dir_all(malformed.join(".git")).expect("malformed git");
    fs::create_dir_all(malformed.join(".digital-asset")).expect("malformed contract dir");
    fs::write(
        malformed
            .join(".digital-asset")
            .join("dad-integration.json"),
        "{not json",
    )
    .expect("malformed contract");
    fs::create_dir_all(missing.join(".git")).expect("missing git");

    let summary = dad_scan_core::probe_repo_inventory(repo_probe_args(&root, "local/workspace"))
        .expect("repo probe");
    let text = serde_json::to_string_pretty(&summary).expect("summary json");
    let valid_record = summary
        .repos
        .iter()
        .find(|item| item.logical_path == "local/workspace/valid-repo")
        .expect("valid record");
    let malformed_record = summary
        .repos
        .iter()
        .find(|item| item.logical_path == "local/workspace/malformed-repo")
        .expect("malformed record");
    let missing_record = summary
        .repos
        .iter()
        .find(|item| item.logical_path == "local/workspace/missing-repo")
        .expect("missing record");

    assert!(valid_record.contract_present);
    assert_eq!(valid_record.contract_parse_status, "present_parseable");
    assert!(valid_record.contract_structural_pass);
    assert!(valid_record.contract_issue_codes.is_empty());
    assert!(valid_record.contract_stable_user_shim_present);
    assert!(valid_record.contract_windows_user_shim_present);
    assert!(valid_record.contract_raw_checkout_fallback_present);
    assert!(valid_record.contract_stable_shim_before_raw_checkout);

    assert!(malformed_record.contract_present);
    assert_eq!(malformed_record.contract_parse_status, "malformed_json");
    assert_eq!(
        malformed_record.contract_issue_codes,
        vec!["contract_malformed_json".to_string()]
    );

    assert!(!missing_record.contract_present);
    assert_eq!(missing_record.contract_parse_status, "missing");
    assert_eq!(
        missing_record.contract_issue_codes,
        vec!["contract_missing".to_string()]
    );
    assert!(!text.contains("repo-valid-secret-ish-id"));
    assert!(!text.contains(temp.path().to_string_lossy().as_ref()));
}

#[test]
fn repo_inventory_probe_contract_surface_rejects_shim_false_greens() {
    let temp = tempfile::tempdir().expect("tempdir");
    let root = temp.path().join("workspace");
    let cases = [
        (
            "only-windows-shim",
            Some("dad.repo_integration.v1"),
            "~/.dad/bin/asset-dir.ps1; PYTHONPATH=src python -m digital_asset_directory.cli",
            vec![
                "contract_missing_stable_user_shim",
                "contract_stable_shim_not_before_raw_checkout",
            ],
        ),
        (
            "only-posix-shim",
            Some("dad.repo_integration.v1"),
            "~/.dad/bin/asset-dir; PYTHONPATH=src python -m digital_asset_directory.cli",
            vec![
                "contract_missing_windows_user_shim",
                "contract_stable_shim_not_before_raw_checkout",
            ],
        ),
        (
            "raw-first",
            Some("dad.repo_integration.v1"),
            "PYTHONPATH=src python -m digital_asset_directory.cli; ~/.dad/bin/asset-dir; ~/.dad/bin/asset-dir.ps1",
            vec!["contract_stable_shim_not_before_raw_checkout"],
        ),
        (
            "missing-schema",
            None,
            "~/.dad/bin/asset-dir; ~/.dad/bin/asset-dir.ps1; PYTHONPATH=src python -m digital_asset_directory.cli",
            vec!["contract_missing_schema_version"],
        ),
    ];

    for (name, schema_version, cli_fallback, _expected_codes) in &cases {
        let repo = root.join(*name);
        fs::create_dir_all(repo.join(".git")).expect("git");
        fs::create_dir_all(repo.join(".digital-asset")).expect("contract dir");
        let schema_row = (*schema_version)
            .map(|schema| format!(r#""schema_version": "{schema}","#))
            .unwrap_or_default();
        fs::write(
            repo.join(".digital-asset").join("dad-integration.json"),
            format!(
                r#"{{
                  {schema_row}
                  "repo_id": "{name}",
                  "capture": {{
                    "surface_version": "dad-capture.v1",
                    "cli_fallback": "{cli_fallback}"
                  }}
                }}"#
            ),
        )
        .expect("contract");
    }

    let summary = dad_scan_core::probe_repo_inventory(repo_probe_args(&root, "local/workspace"))
        .expect("repo probe");
    for (name, _schema_version, _cli_fallback, expected_codes) in &cases {
        let record = summary
            .repos
            .iter()
            .find(|item| item.logical_path == format!("local/workspace/{}", *name))
            .expect("repo record");
        let expected_codes: Vec<String> = expected_codes
            .iter()
            .map(|code| (*code).to_string())
            .collect();
        assert!(record.contract_present);
        assert_eq!(record.contract_parse_status, "present_parseable");
        assert!(!record.contract_structural_pass);
        assert_eq!(record.contract_issue_codes, expected_codes);
    }
}

#[test]
fn repo_inventory_probe_contract_surface_reports_non_object_and_oversized() {
    let temp = tempfile::tempdir().expect("tempdir");
    let root = temp.path().join("workspace");
    let non_object = root.join("non-object");
    let oversized = root.join("oversized");
    fs::create_dir_all(non_object.join(".git")).expect("non object git");
    fs::create_dir_all(non_object.join(".digital-asset")).expect("non object contract dir");
    fs::write(
        non_object
            .join(".digital-asset")
            .join("dad-integration.json"),
        "[]",
    )
    .expect("non object contract");
    fs::create_dir_all(oversized.join(".git")).expect("oversized git");
    fs::create_dir_all(oversized.join(".digital-asset")).expect("oversized contract dir");
    fs::write(
        oversized
            .join(".digital-asset")
            .join("dad-integration.json"),
        " ".repeat(64_001),
    )
    .expect("oversized contract");

    let summary = dad_scan_core::probe_repo_inventory(repo_probe_args(&root, "local/workspace"))
        .expect("repo probe");
    let non_object_record = summary
        .repos
        .iter()
        .find(|item| item.logical_path == "local/workspace/non-object")
        .expect("non object record");
    let oversized_record = summary
        .repos
        .iter()
        .find(|item| item.logical_path == "local/workspace/oversized")
        .expect("oversized record");

    assert_eq!(non_object_record.contract_parse_status, "non_object_json");
    assert_eq!(
        non_object_record.contract_issue_codes,
        vec!["contract_non_object_json".to_string()]
    );
    assert_eq!(oversized_record.contract_parse_status, "oversized");
    assert_eq!(
        oversized_record.contract_issue_codes,
        vec!["contract_oversized".to_string()]
    );
}

#[test]
fn repo_inventory_probe_normalizes_raw_segments_and_sorted_skips() {
    let temp = tempfile::tempdir().expect("tempdir");
    let root = temp.path().join("workspace");
    fs::create_dir_all(root.join("Mock Trial4.26 (active)").join(".git")).expect("mock git");
    fs::create_dir_all(root.join("Z Repo").join(".git")).expect("z repo git");
    fs::create_dir_all(
        root.join("A Repo")
            .join("target")
            .join("hidden")
            .join(".git"),
    )
    .expect("target git");
    fs::create_dir_all(
        root.join("A Repo")
            .join("node_modules")
            .join("hidden")
            .join(".git"),
    )
    .expect("node git");

    let summary = dad_scan_core::probe_repo_inventory(repo_probe_args(&root, "local/workspace"))
        .expect("repo probe");
    let logical_paths: Vec<String> = summary
        .repos
        .iter()
        .map(|repo| repo.logical_path.clone())
        .collect();
    let skipped_paths: Vec<String> = summary
        .skipped_dirs
        .iter()
        .map(|repo| repo.logical_path.clone())
        .collect();

    assert_eq!(
        logical_paths,
        vec![
            "local/workspace/mock-trial4.26-active".to_string(),
            "local/workspace/z-repo".to_string(),
        ]
    );
    assert_eq!(
        skipped_paths,
        vec![
            "local/workspace/a-repo/node_modules".to_string(),
            "local/workspace/a-repo/target".to_string(),
            "local/workspace/mock-trial4.26-active/.git".to_string(),
            "local/workspace/z-repo/.git".to_string(),
        ]
    );
    assert!(
        summary
            .repos
            .iter()
            .map(|item| item.logical_path.as_str())
            .chain(
                summary
                    .skipped_dirs
                    .iter()
                    .map(|item| item.logical_path.as_str())
            )
            .all(|path| !path.contains(' ')
                && !path.contains('(')
                && !path.contains(')')
                && !path.contains('\\'))
    );
}

#[test]
fn repo_inventory_probe_reports_git_file_and_max_depth() {
    let temp = tempfile::tempdir().expect("tempdir");
    let root = temp.path().join("workspace");
    let shallow = root.join("shallow");
    let deep = root.join("a").join("b").join("deep");
    fs::create_dir_all(&shallow).expect("shallow");
    fs::write(shallow.join(".git"), "gitdir: ../real.git\n").expect("git file");
    fs::create_dir_all(deep.join(".git")).expect("deep git");

    let mut args = repo_probe_args(&root, "local/workspace");
    args.max_depth = 1;
    let summary = dad_scan_core::probe_repo_inventory(args).expect("repo probe");

    assert_eq!(summary.repo_count, 1);
    assert_eq!(summary.repos[0].logical_path, "local/workspace/shallow");
    assert_eq!(summary.repos[0].git_marker_type, "file");
}

#[test]
fn repo_inventory_probe_rejects_unsafe_alias_and_follow_symlinks() {
    let temp = tempfile::tempdir().expect("tempdir");
    let root = temp.path().join("workspace");
    fs::create_dir_all(&root).expect("root");

    let mut args = repo_probe_args(&root, "../workspace");
    assert!(dad_scan_core::probe_repo_inventory(args.clone()).is_err());

    args.root_aliases = vec!["C:/workspace".to_string()];
    assert!(dad_scan_core::probe_repo_inventory(args.clone()).is_err());

    args.root_aliases = vec!["local/workspace".to_string()];
    args.follow_symlinks = true;
    assert!(dad_scan_core::probe_repo_inventory(args).is_err());
}

#[test]
fn repo_inventory_probe_rejects_duplicate_root_aliases_before_walk() {
    let temp = tempfile::tempdir().expect("tempdir");
    let first = temp.path().join("first");
    let second = temp.path().join("second");
    fs::create_dir_all(first.join("repo-a").join(".git")).expect("first git");
    fs::create_dir_all(second.join("repo-b").join(".git")).expect("second git");

    let error = dad_scan_core::probe_repo_inventory(RepoInventoryProbeArgs {
        roots: vec![first, second],
        root_aliases: vec!["local/workspace".to_string(), "local/workspace".to_string()],
        max_depth: 5,
        follow_symlinks: false,
    })
    .expect_err("duplicate aliases rejected");

    assert!(
        error
            .to_string()
            .contains("root-alias values must be unique")
    );
}

#[test]
fn repo_inventory_probe_sorts_roots_and_reports_missing_roots() {
    let temp = tempfile::tempdir().expect("tempdir");
    let existing = temp.path().join("z-root");
    let missing = temp.path().join("a-root");
    fs::create_dir_all(existing.join("repo").join(".git")).expect("git");

    let summary: RepoInventoryProbeSummary =
        dad_scan_core::probe_repo_inventory(RepoInventoryProbeArgs {
            roots: vec![existing, missing],
            root_aliases: vec!["z/root".to_string(), "a/root".to_string()],
            max_depth: 3,
            follow_symlinks: false,
        })
        .expect("repo probe");

    assert_eq!(
        summary
            .roots
            .iter()
            .map(|root| (root.root_alias.as_str(), root.status.as_str()))
            .collect::<Vec<_>>(),
        vec![("a/root", "missing"), ("z/root", "checked")]
    );
    assert_eq!(summary.repos[0].logical_path, "z/root/repo");
}

#[test]
fn scan_records_content_hash_and_asset_type_hints() {
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    let out_dir = temp.path().join("out");
    fs::create_dir_all(&source).expect("source dir");
    fs::write(source.join("script.py"), "hello\n").expect("write python");
    fs::write(source.join("lib.rs"), "fn main() {}\n").expect("write rust");

    let args = default_args(&source, &out_dir);
    let out_path = args.out.clone();
    dad_scan_core::scan_local(args).expect("scan");

    let observations = read_observations(&out_path);
    let python = observations
        .iter()
        .find(|observation| observation.logical_path == "fixture/script.py")
        .expect("python observation");
    let rust = observations
        .iter()
        .find(|observation| observation.logical_path == "fixture/lib.rs")
        .expect("rust observation");
    assert_eq!(python.asset_type_hint, "python_code");
    assert_eq!(python.content_hash_mode, "content_sha256");
    assert_eq!(
        python.content_sha256.as_deref(),
        Some("5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03")
    );
    assert_eq!(rust.asset_type_hint, "rust_code");
    assert_eq!(rust.content_hash_mode, "content_sha256");
    assert!(rust.content_sha256.is_some());
}

#[test]
fn scan_uses_metadata_only_when_file_exceeds_content_hash_limit() {
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    let out_dir = temp.path().join("out");
    fs::create_dir_all(&source).expect("source dir");
    fs::write(source.join("large.txt"), "0123456789").expect("write large");

    let mut args = default_args(&source, &out_dir);
    args.max_content_hash_bytes = 3;
    let out_path = args.out.clone();
    let result = dad_scan_core::scan_local(args).expect("scan");

    assert_eq!(result.included_count, 1);
    let observations = read_observations(&out_path);
    assert_eq!(observations[0].content_hash_mode, "oversize_metadata_only");
    assert!(observations[0].content_sha256.is_none());
    assert!(!observations[0].metadata_sha256.is_empty());
}

#[test]
fn scan_refuses_invalid_output_arguments_before_writing() {
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    let out_dir = temp.path().join("out");
    fs::create_dir_all(&source).expect("source dir");
    fs::write(source.join("README.md"), "# Demo\n").expect("write readme");

    let mut duplicate_args = default_args(&source, &out_dir);
    duplicate_args.quarantine_out = duplicate_args.summary_out.clone();
    let duplicate_error =
        dad_scan_core::scan_local(duplicate_args).expect_err("duplicate output refused");
    assert!(
        duplicate_error
            .to_string()
            .contains("output paths must be distinct")
    );
    assert!(!out_dir.exists());

    let mut wrong_extension_args = default_args(&source, &out_dir);
    wrong_extension_args.out = out_dir.join("observations.txt");
    let extension_error =
        dad_scan_core::scan_local(wrong_extension_args).expect_err("wrong extension refused");
    assert!(
        extension_error
            .to_string()
            .contains("must use .jsonl extension")
    );
    assert!(!out_dir.exists());

    let mut zero_hash_args = default_args(&source, &out_dir);
    zero_hash_args.max_content_hash_bytes = 0;
    let zero_hash_error =
        dad_scan_core::scan_local(zero_hash_args).expect_err("zero hash limit refused");
    assert!(
        zero_hash_error
            .to_string()
            .contains("--max-content-hash-bytes must be greater than zero")
    );
    assert!(!out_dir.exists());
}

#[test]
fn scan_refuses_unsafe_path_alias_before_writing() {
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    fs::create_dir_all(&source).expect("source dir");
    fs::write(source.join("README.md"), "# Demo\n").expect("write readme");

    let invalid_aliases = [
        "",
        "/absolute",
        "C:/private",
        "dad\\tools",
        "dad/../secret",
        "dad//tools",
        "dad/tools ",
        "dad://hub/repo",
    ];
    for (index, alias) in invalid_aliases.iter().enumerate() {
        let out_dir = temp.path().join(format!("out-{index}"));
        let mut args = default_args(&source, &out_dir);
        args.path_alias = (*alias).to_string();
        let error = dad_scan_core::scan_local(args).expect_err("unsafe alias refused");

        assert!(
            error.to_string().contains("--path-alias"),
            "unexpected error for alias {alias:?}: {error}"
        );
        assert!(!out_dir.exists());
    }
}

#[test]
fn scan_refuses_normalized_duplicate_output_paths_before_writing() {
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    let out_dir = temp.path().join("out");
    fs::create_dir_all(&source).expect("source dir");
    fs::write(source.join("README.md"), "# Demo\n").expect("write readme");

    let mut args = default_args(&source, &out_dir);
    args.summary_out = out_dir.join("nested").join("..").join("same.json");
    args.quarantine_out = out_dir.join("same.json");
    let error = dad_scan_core::scan_local(args).expect_err("normalized duplicate refused");

    assert!(
        error.to_string().contains("output paths must be distinct"),
        "unexpected error: {error}"
    );
    assert!(!out_dir.exists());
}

#[test]
fn scan_refuses_zero_max_files_before_writing() {
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    let out_dir = temp.path().join("out");
    fs::create_dir_all(&source).expect("source dir");
    fs::write(source.join("README.md"), "# Demo\n").expect("write readme");

    let mut args = default_args(&source, &out_dir);
    args.max_files = Some(0);
    let error = dad_scan_core::scan_local(args).expect_err("zero max files refused");

    assert!(
        error
            .to_string()
            .contains("--max-files must be greater than zero")
    );
    assert!(!out_dir.exists());
}

#[test]
fn scan_refuses_existing_output_paths() {
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    let out = temp.path().join("out").join("observations.jsonl");
    let summary = temp.path().join("out").join("summary.json");
    let quarantine = temp.path().join("out").join("quarantine.json");
    fs::create_dir_all(&source).expect("source dir");
    fs::create_dir_all(out.parent().expect("out parent")).expect("out dir");
    fs::write(source.join("README.md"), "# Demo\n").expect("write readme");
    fs::write(&out, "do not overwrite\n").expect("preexisting output");

    let args = dad_scan_core::ScanLocalArgs {
        source,
        source_id: "fixture".to_string(),
        path_alias: "fixture".to_string(),
        out: out.clone(),
        summary_out: summary,
        quarantine_out: quarantine,
        max_files: Some(10),
        max_content_hash_bytes: 1024 * 1024,
        follow_symlinks: false,
        excludes: vec![],
    };
    let error = dad_scan_core::scan_local(args).expect_err("existing output is refused");

    assert!(error.to_string().contains("refusing to overwrite"));
    assert_eq!(
        fs::read_to_string(out).expect("preexisting output remains"),
        "do not overwrite\n"
    );
}

#[test]
fn scan_refuses_relative_output_inside_source_with_missing_parent() {
    let _guard = CWD_LOCK.lock().expect("cwd lock");
    let _cwd_guard = CurrentDirGuard(env::current_dir().expect("current dir"));
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    fs::create_dir_all(&source).expect("source dir");
    fs::write(source.join("README.md"), "# Demo\n").expect("write readme");
    env::set_current_dir(temp.path()).expect("switch cwd");

    let args = dad_scan_core::ScanLocalArgs {
        source: "source".into(),
        source_id: "fixture".to_string(),
        path_alias: "fixture".to_string(),
        out: "source/generated/observations.jsonl".into(),
        summary_out: "source/generated/summary.json".into(),
        quarantine_out: "source/generated/quarantine.json".into(),
        max_files: Some(10),
        max_content_hash_bytes: 1024 * 1024,
        follow_symlinks: false,
        excludes: vec![],
    };
    let error = dad_scan_core::scan_local(args).expect_err("output inside source is refused");

    assert!(
        error
            .to_string()
            .contains("output path appears to be inside the scanned source")
    );
    assert!(!source.join("generated").exists());
}

#[test]
fn scan_refuses_invalid_exclude_glob_before_writing() {
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    let out_dir = temp.path().join("out");
    fs::create_dir_all(&source).expect("source dir");
    fs::write(source.join("README.md"), "# Demo\n").expect("write readme");

    let mut args = default_args(&source, &out_dir);
    args.excludes.push("[bad".to_string());
    let error = dad_scan_core::scan_local(args).expect_err("invalid glob refused");

    assert!(error.to_string().contains("unclosed character class"));
    assert!(!out_dir.exists());
}

#[test]
fn scan_quarantines_child_symlink_without_hashing_target() {
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    let out_dir = temp.path().join("out");
    fs::create_dir_all(&source).expect("source dir");
    let target = temp.path().join("private-target.md");
    fs::write(&target, "target should not be hashed\n").expect("write target");
    let link = source.join("link.md");
    if create_file_symlink(&target, &link).is_err() {
        return;
    }

    let args = default_args(&source, &out_dir);
    let out_path = args.out.clone();
    let quarantine_path = args.quarantine_out.clone();
    let result = dad_scan_core::scan_local(args).expect("scan");

    assert_eq!(result.included_count, 0);
    assert_eq!(result.skipped_count, 1);
    assert!(read_observations(&out_path).is_empty());
    let quarantine: QuarantineReport = read_json(&quarantine_path);
    assert_eq!(quarantine.skipped[0].logical_path, "fixture/link.md");
    assert_eq!(quarantine.skipped[0].reason, "symlink refused");
}

#[test]
fn scan_refuses_follow_symlinks_until_provenance_exists() {
    let temp = tempfile::tempdir().expect("tempdir");
    let source = temp.path().join("source");
    let out = temp.path().join("out").join("observations.jsonl");
    let summary = temp.path().join("out").join("summary.json");
    let quarantine = temp.path().join("out").join("quarantine.json");
    fs::create_dir_all(&source).expect("source dir");
    fs::write(source.join("README.md"), "# Demo\n").expect("write readme");

    let args = dad_scan_core::ScanLocalArgs {
        source,
        source_id: "fixture".to_string(),
        path_alias: "fixture".to_string(),
        out,
        summary_out: summary,
        quarantine_out: quarantine,
        max_files: Some(10),
        max_content_hash_bytes: 1024 * 1024,
        follow_symlinks: true,
        excludes: vec![],
    };
    let error = dad_scan_core::scan_local(args).expect_err("follow symlinks is refused");

    assert!(error.to_string().contains("--follow-symlinks is disabled"));
}
