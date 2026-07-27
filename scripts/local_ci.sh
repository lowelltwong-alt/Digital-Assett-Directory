#!/usr/bin/env bash
# Local equivalent of the GitHub `validate` + `dad-contract-check` workflows.
#
# Runs the same commands CI runs, so you can gate changes locally without
# spending GitHub Actions minutes. CI itself only wraps these commands plus a
# Linux runner and a merge gate; nothing here is checked that CI checks
# differently. See .github/workflows/validate.yml and dad-contract-check.yml.
#
# Usage:  bash scripts/local_ci.sh [--base <ref>] [--merge-gate]
#   --base        base ref to diff against (default: origin/main)
#   --merge-gate  authoritative mode for merging on local evidence: every
#                 suite the CI selector would run becomes a HARD gate, and the
#                 full pytest suite runs in a clean temp clone of HEAD outside
#                 any OneDrive-synced path (the local analog of CI's fresh
#                 Linux checkout). Commit your work first: the clone tests the
#                 committed tree, exactly like CI would.
#
# Exit code is non-zero if any required check fails. The contract-check step is
# advisory (mirrors CI continue-on-error) and never fails the run.
set -uo pipefail

BASE="origin/main"
MERGE_GATE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --base) BASE="$2"; shift 2 ;;
    --merge-gate) MERGE_GATE=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

cd "$(git rev-parse --show-toplevel)"
export PYTHONPATH=src
fail=0
run() { echo; echo "===== $1 ====="; shift; "$@"; local rc=$?; [ $rc -ne 0 ] && { echo ">>> FAILED (exit $rc)"; fail=1; }; return 0; }

# 1. ci-contract: CI module-boundary contract + suite selection.
#    Mirrors the selector job including the --base-manifest comparison, which
#    fail-closes on silent scope broadening of .ci/module-boundaries.yaml.
base_manifest_args=()
if git cat-file -e "${BASE}:.ci/module-boundaries.yaml" 2>/dev/null; then
  git show "${BASE}:.ci/module-boundaries.yaml" > /tmp/dad-base-module-boundaries.yaml
  [ -s /tmp/dad-base-module-boundaries.yaml ] \
    && base_manifest_args=(--base-manifest /tmp/dad-base-module-boundaries.yaml)
fi
run "ci-contract: module-boundary validate" \
  python scripts/validate_ci_module_boundaries.py --repo . validate \
    --provider github-actions --manifest .ci/module-boundaries.yaml \
    "${base_manifest_args[@]}"
git diff --name-status "${BASE}...HEAD" > /tmp/dad-changed-paths.txt 2>/dev/null \
  || git diff --name-status "${BASE}" > /tmp/dad-changed-paths.txt
echo; echo "===== ci-contract: suite selection (evaluate) ====="
if python scripts/validate_ci_module_boundaries.py --repo . evaluate \
    --manifest .ci/module-boundaries.yaml \
    --changes-file /tmp/dad-changed-paths.txt \
    | tee /tmp/dad-ci-selection.json; then
  :
else
  echo ">>> FAILED (suite selection)"; fail=1
fi
selected_suites="$(python -c 'import json;print(" ".join(sorted(json.load(open("/tmp/dad-ci-selection.json",encoding="utf-8"))["selected_suites"])))' 2>/dev/null || echo "")"
echo "selected suites: ${selected_suites:-<none>}"

# 2. governance-contracts: catalog validation + roadmap gate.
#    In --merge-gate mode these run inside the clean clone below instead:
#    validators such as branch-disposition liveness read LOCAL branch state,
#    so an in-place run on a many-branch checkout is stricter than CI's fresh
#    checkout and can fail on hygiene unrelated to the change under review.
if [ "$MERGE_GATE" != "1" ]; then
  run "governance-contracts: validate" \
    python -m digital_asset_directory.cli validate --hub .
  run "governance-contracts: roadmap check" \
    python -m digital_asset_directory.cli roadmap check --hub . --no-update
fi

# 3. python-control-plane: full test suite.
#    CI runs `python -m pytest` as a HARD gate on a fresh Linux checkout.
#
#    On this Windows/OneDrive checkout the in-place full suite is pervasively
#    flaky (documented in dad-test-suite-flakes): sqlite/catalog file-lock
#    TimeoutErrors, scan-timestamp ordering, latency budgets, and Rich
#    terminal-width wrapping in CliRunner. The SAME suite is green on a clean
#    checkout, which is what CI tests.
#
#    --merge-gate reproduces CI's fresh-checkout property locally: it clones
#    HEAD into a temp directory OUTSIDE OneDrive and hard-gates the full suite
#    there. The clone is labeled lineage evidence and deleted afterward; it is
#    never a second source of truth. Without --merge-gate, in-place pytest is
#    advisory (set DAD_STRICT_PYTEST=1 to enforce in place).
if [ "$MERGE_GATE" = "1" ]; then
  echo; echo "===== python-control-plane: pytest in clean clone (merge gate, hard) ====="
  head_sha="$(git rev-parse HEAD)"
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo ">>> NOTE: uncommitted changes present; the merge gate tests committed HEAD ${head_sha:0:9} only."
  fi
  clone_root="$(mktemp -d "${TMPDIR:-/tmp}/dad-merge-gate.XXXXXX")"
  clone_ok=1
  case "$clone_root" in
    *[Oo]ne[Dd]rive*) echo ">>> FAILED: temp dir resolves inside OneDrive; set TMPDIR elsewhere."; fail=1; clone_ok=0 ;;
  esac
  if [ $clone_ok -eq 1 ]; then
    echo "lineage: clone of ${head_sha} at ${clone_root}/repo (disposable evidence copy)"
    if git clone --quiet --no-hardlinks . "$clone_root/repo"; then
      ( cd "$clone_root/repo" \
        && git -c advice.detachedHead=false checkout --quiet "$head_sha" \
        && PYTHONPATH=src python -m pytest -q --cache-clear )
      pytest_rc=$?
      if [ $pytest_rc -ne 0 ]; then
        echo ">>> FAILED: full suite failed in the clean clone (exit $pytest_rc)."
        echo "    This is the same signal CI would give; do not merge."
        fail=1
      else
        echo ">>> pytest passed in clean clone (CI-equivalent)."
      fi
      echo; echo "===== governance-contracts in clean clone (merge gate, hard) ====="
      ( cd "$clone_root/repo" \
        && PYTHONPATH=src python -m digital_asset_directory.cli validate --hub . )
      validate_rc=$?
      [ $validate_rc -ne 0 ] && { echo ">>> FAILED: validate failed in clean clone (exit $validate_rc)."; fail=1; }
      ( cd "$clone_root/repo" \
        && PYTHONPATH=src python -m digital_asset_directory.cli roadmap check --hub . --no-update )
      roadmap_rc=$?
      [ $roadmap_rc -ne 0 ] && { echo ">>> FAILED: roadmap check failed in clean clone (exit $roadmap_rc)."; fail=1; }
    else
      echo ">>> FAILED: could not clone HEAD for the merge gate."; fail=1
    fi
    rm -rf "$clone_root"
  fi
else
  echo; echo "===== python-control-plane: pytest (advisory on this environment) ====="
  strict="${DAD_STRICT_PYTEST:-0}"
  if python -m pytest -q --cache-clear; then
    echo ">>> pytest passed"
  else
    echo ">>> pytest reported failures."
    echo "    On this OneDrive/Windows tree these are almost always environment"
    echo "    flakes (file-lock/timing/latency/Rich-width) that pass on a clean"
    echo "    checkout. Review the FAILED lines above; if any touch YOUR change,"
    echo "    run that file targeted: PYTHONPATH=src python -m pytest tests/<file>.py -q"
    echo "    For the CI-equivalent hard gate, run: bash scripts/local_ci.sh --merge-gate"
    if [ "$strict" = "1" ]; then
      echo ">>> DAD_STRICT_PYTEST=1: treating pytest failures as a hard gate."
      fail=1
    else
      echo ">>> Advisory mode: not failing the gate on pytest (set DAD_STRICT_PYTEST=1 to enforce)."
    fi
  fi
fi

# 4. rust-scan: mirrors .github/workflows/rust-ci-pr.yml, which CI runs when
#    the selector picks the rust-scan suite. Hard in --merge-gate when
#    selected; skipped (with a warning) when cargo is unavailable outside the
#    merge gate.
case " ${selected_suites} " in
  *" rust-scan "*)
    echo; echo "===== rust-scan: cargo + bridge tests (selected by CI contract) ====="
    if command -v cargo >/dev/null 2>&1; then
      run "rust-scan: cargo fmt" \
        cargo fmt --manifest-path tools/dad_scan_core/Cargo.toml --check
      run "rust-scan: cargo check" \
        cargo check --manifest-path tools/dad_scan_core/Cargo.toml
      run "rust-scan: cargo clippy" \
        cargo clippy --manifest-path tools/dad_scan_core/Cargo.toml --all-targets --all-features -- -D warnings
      run "rust-scan: cargo test" \
        cargo test --manifest-path tools/dad_scan_core/Cargo.toml
      run "rust-scan: python wrapper help" \
        python scripts/run_dad_scan_core.py --help
      run "rust-scan: python rust bridge tests" \
        python -m pytest tests/test_rust_bridge_dad_scan_core.py tests/test_rust_rollout.py -q
    else
      if [ "$MERGE_GATE" = "1" ]; then
        echo ">>> FAILED: rust-scan suite selected but cargo is not installed;"
        echo "    cannot certify CI equivalence for this change. Install the"
        echo "    stable Rust toolchain (rustup) and re-run."
        fail=1
      else
        echo ">>> WARNING: rust-scan selected but cargo missing; CI would run it."
      fi
    fi
    ;;
esac

# 5. dad-contract-check (advisory / non-blocking, like CI continue-on-error)
echo; echo "===== dad-contract-check-advisory (non-blocking) ====="
python scripts/contract_check.py --hub . --repo . --base "${BASE}" --mode policy || true

echo
if [ $fail -ne 0 ]; then
  echo "LOCAL CI: FAILED (see FAILED lines above)"
  exit 1
fi
if [ "$MERGE_GATE" = "1" ]; then
  echo "LOCAL CI (MERGE GATE): all CI-equivalent checks passed - local-green is merge-grade"
else
  echo "LOCAL CI: all required checks passed"
fi
