use std::fs;

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
