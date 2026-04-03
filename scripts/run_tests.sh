#!/usr/bin/env bash
# run_tests.sh — Full test suite for kg-snapshot extraction
#
# Runs tests in dependency order:
#   1. kg_snapshot base (no domain deps)
#   2. code_kg, doc_kg, diary_kg, metabo_kg, ftree_kg domain suites
#   3. Import chain smoke-test across all repos
#
# Usage:
#   cd /Users/egs/repos/kg_snapshot
#   bash scripts/run_tests.sh
#
# Exit code: 0 if all pass, 1 if any fail.

set -uo pipefail  # no -e: let failures accumulate rather than aborting early

PASS=0
FAIL=0
ERRORS=()

run_pytest() {
    local repo="$1"
    local testpath="${2:-$repo/tests}"   # optional: pass a specific file/dir
    local label
    label=$(basename "$repo")
    echo ""
    echo "══════════════════════════════════════════════"
    echo "  pytest: $label  ($testpath)"
    echo "══════════════════════════════════════════════"

    if [ ! -e "$testpath" ]; then
        echo "  [SKIP] $testpath not found"
        return
    fi

    # Use the repo's own venv if present, else fall through to active env
    local python="python"
    if [ -f "$repo/.venv/bin/python" ]; then
        python="$repo/.venv/bin/python"
    fi

    if $python -m pytest "$testpath" -v --tb=short 2>&1; then
        ((PASS++))
    else
        ((FAIL++))
        ERRORS+=("$label")
    fi
}

# ---------------------------------------------------------------------------
# Phase 1: base package tests (must pass before anything else)
# ---------------------------------------------------------------------------
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Phase 1 — kg_snapshot base tests            ║"
echo "╚══════════════════════════════════════════════╝"
run_pytest /Users/egs/repos/kg_snapshot

# ---------------------------------------------------------------------------
# Phase 2: domain subclass tests
# ---------------------------------------------------------------------------
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Phase 2 — domain subclass tests             ║"
echo "╚══════════════════════════════════════════════╝"

# code_kg and doc_kg: run full snapshot test files
run_pytest /Users/egs/repos/code_kg  /Users/egs/repos/code_kg/tests/test_snapshots.py
run_pytest /Users/egs/repos/doc_kg   /Users/egs/repos/doc_kg/tests/test_snapshots.py

# diary_kg and metabo_kg: run only the new subclass test to avoid pre-existing
# failures caused by missing optional deps (spacy, etc.) in the snapshot venv
run_pytest /Users/egs/repos/diary_kg  /Users/egs/repos/diary_kg/tests/test_snapshot_subclass.py
run_pytest /Users/egs/repos/metabo_kg /Users/egs/repos/metabo_kg/tests/test_snapshot_subclass.py

# ftree_kg: run full snapshot test file if present, else full suite
FTREE_SNAP=/Users/egs/repos/FTreeKG/tests/test_snapshots.py
FTREE_SUB=/Users/egs/repos/FTreeKG/tests/test_snapshot_subclass.py
if [ -f "$FTREE_SNAP" ]; then
    run_pytest /Users/egs/repos/FTreeKG "$FTREE_SNAP"
elif [ -f "$FTREE_SUB" ]; then
    run_pytest /Users/egs/repos/FTreeKG "$FTREE_SUB"
else
    run_pytest /Users/egs/repos/FTreeKG
fi

# ---------------------------------------------------------------------------
# Phase 3: import chain smoke-test — one check per repo venv
# ---------------------------------------------------------------------------
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Phase 3 — import chain smoke-test           ║"
echo "╚══════════════════════════════════════════════╝"

smoke_fail=0

run_smoke() {
    local label="$1"
    local repo="$2"
    local stmt="$3"
    local py="python"
    [ -f "$repo/.venv/bin/python" ] && py="$repo/.venv/bin/python"
    if $py -c "$stmt" 2>/dev/null; then
        echo "  [OK]  $label"
    else
        echo "  [FAIL] $label"
        smoke_fail=1
    fi
}

run_smoke "kg_snapshot base" \
    /Users/egs/repos/kg_snapshot \
    "from kg_snapshot import Snapshot, SnapshotManifest, SnapshotManager"

run_smoke "kg_rag shim exports SnapshotManager" \
    /Users/egs/repos/kgrag \
    "from kg_rag.snapshots import SnapshotManager; assert SnapshotManager.__name__ == 'SnapshotManager'"

run_smoke "code_kg subclass" \
    /Users/egs/repos/code_kg \
    "from code_kg.snapshots import SnapshotManager as M; from kg_snapshot import SnapshotManager as B; assert issubclass(M, B)"

run_smoke "doc_kg subclass" \
    /Users/egs/repos/doc_kg \
    "from doc_kg.snapshots import SnapshotManager as M; from kg_snapshot import SnapshotManager as B; assert issubclass(M, B)"

run_smoke "diary_kg subclass" \
    /Users/egs/repos/diary_kg \
    "from diary_kg.snapshots import DiarySnapshotManager as M; from kg_snapshot import SnapshotManager as B; assert issubclass(M, B)"

run_smoke "metabo_kg subclass" \
    /Users/egs/repos/metabo_kg \
    "from metabokg.snapshots import SnapshotManager as M; from kg_snapshot import SnapshotManager as B; assert issubclass(M, B)"

if [ $smoke_fail -ne 0 ]; then
    ((FAIL++))
    ERRORS+=("import-chain")
fi

# ---------------------------------------------------------------------------
# Phase 4: load real on-disk snapshots — one check per repo venv
# ---------------------------------------------------------------------------
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Phase 4 — load real on-disk snapshots       ║"
echo "╚══════════════════════════════════════════════╝"

disk_fail=0

run_disk_check() {
    local label="$1"
    local repo="$2"
    local module="$3"
    local cls_name="$4"
    local snap_dir="$5"
    local py="python"
    [ -f "$repo/.venv/bin/python" ] && py="$repo/.venv/bin/python"

    if [ ! -d "$snap_dir" ]; then
        echo "  [SKIP] $label: no snapshots dir"
        return
    fi
    if $py - <<PYEOF 2>/dev/null
import importlib, sys
from pathlib import Path
mod = importlib.import_module("$module")
cls = getattr(mod, "$cls_name")
mgr = cls(Path("$snap_dir"))
snaps = mgr.list_snapshots(limit=3)
latest = mgr.load_snapshot("latest")
assert latest is not None
print(f"  [OK]  $label: {len(snaps)} snapshots, latest loaded OK")
PYEOF
    then
        :
    else
        echo "  [FAIL] $label"
        disk_fail=1
    fi
}

run_disk_check "code_kg"  /Users/egs/repos/code_kg  "code_kg.snapshots"  "SnapshotManager"      /Users/egs/repos/code_kg/.codekg/snapshots
run_disk_check "doc_kg"   /Users/egs/repos/doc_kg   "doc_kg.snapshots"   "SnapshotManager"      /Users/egs/repos/doc_kg/.dockg/snapshots
run_disk_check "diary_kg" /Users/egs/repos/diary_kg "diary_kg.snapshots" "DiarySnapshotManager" /Users/egs/repos/diary_kg/.diarykg/snapshots

if [ $disk_fail -ne 0 ]; then
    ((FAIL++))
    ERRORS+=("on-disk-load")
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Results                                     ║"
echo "╚══════════════════════════════════════════════╝"
echo "  Passed: $PASS"
echo "  Failed: $FAIL"

if [ ${#ERRORS[@]} -gt 0 ]; then
    echo "  Failed in: ${ERRORS[*]}"
    exit 1
else
    echo "  All checks passed."
    exit 0
fi
