"""
test_snapshot_base.py — Unit tests for kg_snapshot base classes.

Covers Snapshot, SnapshotManifest, and SnapshotManager directly —
before any domain subclass is involved.  These must pass before
running domain-level tests in code_kg, doc_kg, diary_kg, ftree_kg.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from kg_snapshot import PruneResult, Snapshot, SnapshotManager, SnapshotManifest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def snap_dir(tmp_path: Path) -> Path:
    d = tmp_path / "snapshots"
    d.mkdir()
    return d


@pytest.fixture
def mgr(snap_dir: Path) -> SnapshotManager:
    return SnapshotManager(snap_dir, package_name="kg-snapshot")


@pytest.fixture
def graph_stats() -> dict:
    return {
        "total_nodes": 100,
        "total_edges": 150,
        "node_counts": {"function": 40, "class": 10, "method": 50},
        "edge_counts": {"CALLS": 80, "CONTAINS": 50, "IMPORTS": 20},
    }


# ---------------------------------------------------------------------------
# Snapshot dataclass
# ---------------------------------------------------------------------------


def test_snapshot_key_is_tree_hash() -> None:
    snap = Snapshot(
        branch="main", timestamp="2026-01-01T00:00:00+00:00", metrics={}, tree_hash="abc123"
    )
    assert snap.key == "abc123"


def test_snapshot_round_trip() -> None:
    snap = Snapshot(
        branch="main",
        timestamp="2026-01-01T00:00:00+00:00",
        version="1.0.0",
        metrics={"total_nodes": 10, "total_edges": 5},
        hotspots=[{"name": "f", "callers": 3}],
        issues=["missing docstring"],
        tree_hash="deadbeef",
    )
    d = snap.to_dict()
    loaded = Snapshot.from_dict(d)
    assert loaded.tree_hash == snap.tree_hash
    assert loaded.branch == snap.branch
    assert loaded.metrics == snap.metrics
    assert loaded.hotspots == snap.hotspots
    assert loaded.issues == snap.issues


def test_snapshot_from_dict_legacy_tree_hash_key() -> None:
    """Snapshots written before 'key' field existed used 'tree_hash'."""
    data = {
        "tree_hash": "legacy123",
        "branch": "main",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "version": "0.1.0",
        "metrics": {"total_nodes": 5, "total_edges": 2},
    }
    snap = Snapshot.from_dict(data)
    assert snap.tree_hash == "legacy123"
    assert snap.key == "legacy123"


# ---------------------------------------------------------------------------
# SnapshotManifest
# ---------------------------------------------------------------------------


def test_manifest_round_trip() -> None:
    m = SnapshotManifest(
        format_version="1.0",
        last_update="2026-01-01T00:00:00+00:00",
        snapshots=[{"key": "abc", "timestamp": "2026-01-01T00:00:00+00:00"}],
    )
    loaded = SnapshotManifest.from_dict(m.to_dict())
    assert loaded.format_version == "1.0"
    assert len(loaded.snapshots) == 1
    assert loaded.snapshots[0]["key"] == "abc"


# ---------------------------------------------------------------------------
# SnapshotManager — capture
# ---------------------------------------------------------------------------


def test_capture_returns_snapshot(mgr: SnapshotManager, graph_stats: dict) -> None:
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        snap = mgr.capture(version="1.0.0", graph_stats_dict=graph_stats)
    assert isinstance(snap, Snapshot)
    assert snap.branch == "main"
    assert snap.tree_hash == "hash001"
    assert snap.metrics["total_nodes"] == 100


def test_capture_extra_metrics_merged(mgr: SnapshotManager) -> None:
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        snap = mgr.capture(
            graph_stats_dict={"total_nodes": 10, "total_edges": 5},
            coverage=0.85,
            custom_field="hello",
        )
    assert snap.metrics["coverage"] == 0.85
    assert snap.metrics["custom_field"] == "hello"


# ---------------------------------------------------------------------------
# SnapshotManager — save / load
# ---------------------------------------------------------------------------


def test_save_and_load_round_trip(mgr: SnapshotManager, graph_stats: dict, snap_dir: Path) -> None:
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        snap = mgr.capture(version="1.0.0", graph_stats_dict=graph_stats)
    mgr.save_snapshot(snap)

    loaded = mgr.load_snapshot("hash001")
    assert loaded is not None
    assert loaded.tree_hash == "hash001"
    assert loaded.metrics["total_nodes"] == 100

    # JSON file exists on disk
    assert (snap_dir / "hash001.json").exists()


def test_load_latest(mgr: SnapshotManager, graph_stats: dict) -> None:
    for i, h in enumerate(["hash001", "hash002"]):
        with (
            patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
            patch.object(SnapshotManager, "_get_current_tree_hash", return_value=h),
        ):
            snap = mgr.capture(version=f"1.0.{i}", graph_stats_dict=graph_stats)
        mgr.save_snapshot(snap)

    loaded = mgr.load_snapshot("latest")
    assert loaded is not None
    assert loaded.tree_hash == "hash002"


def test_save_rejects_zero_nodes(mgr: SnapshotManager) -> None:
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash000"),
    ):
        snap = mgr.capture(graph_stats_dict={"total_nodes": 0, "total_edges": 0})
    with pytest.raises(ValueError, match="0 nodes"):
        mgr.save_snapshot(snap)


def test_load_missing_returns_none(mgr: SnapshotManager) -> None:
    assert mgr.load_snapshot("doesnotexist") is None


# ---------------------------------------------------------------------------
# SnapshotManager — deltas
# ---------------------------------------------------------------------------


def test_vs_previous_backfilled_on_load(mgr: SnapshotManager) -> None:
    """vs_previous is backfilled from manifest when loading, not at capture time.

    capture() only computes vs_previous when the *current* tree_hash is already
    in the manifest (i.e. a re-capture of an existing snapshot).  For a brand-new
    key the delta is backfilled by load_snapshot() from adjacent manifest entries.
    """
    stats_a = {"total_nodes": 100, "total_edges": 150}
    stats_b = {"total_nodes": 120, "total_edges": 170}

    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        snap_a = mgr.capture(graph_stats_dict=stats_a)
    mgr.save_snapshot(snap_a)

    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash002"),
    ):
        snap_b = mgr.capture(graph_stats_dict=stats_b)
    mgr.save_snapshot(snap_b)

    # After saving, loading back gives backfilled vs_previous
    loaded = mgr.load_snapshot("hash002")
    assert loaded is not None
    assert loaded.vs_previous is not None
    assert loaded.vs_previous["nodes"] == 20
    assert loaded.vs_previous["edges"] == 20


def test_vs_baseline_set_when_prior_snapshot_exists(mgr: SnapshotManager) -> None:
    """vs_baseline is computed at capture time against the oldest saved snapshot."""
    stats_a = {"total_nodes": 50, "total_edges": 60}
    stats_b = {"total_nodes": 80, "total_edges": 90}

    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        snap_a = mgr.capture(graph_stats_dict=stats_a)
    mgr.save_snapshot(snap_a)

    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash002"),
    ):
        snap_b = mgr.capture(graph_stats_dict=stats_b)

    # vs_baseline is computed at capture time (baseline = hash001)
    assert snap_b.vs_baseline is not None
    assert snap_b.vs_baseline["nodes"] == 30
    assert snap_b.vs_baseline["edges"] == 30


# ---------------------------------------------------------------------------
# SnapshotManager — list / diff
# ---------------------------------------------------------------------------


def test_list_snapshots_reverse_chronological(mgr: SnapshotManager) -> None:
    for i, h in enumerate(["hash001", "hash002", "hash003"]):
        with (
            patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
            patch.object(SnapshotManager, "_get_current_tree_hash", return_value=h),
        ):
            snap = mgr.capture(graph_stats_dict={"total_nodes": 10 + i, "total_edges": 5})
        mgr.save_snapshot(snap)

    listing = mgr.list_snapshots()
    assert len(listing) == 3
    assert listing[0]["key"] == "hash003"
    assert listing[-1]["key"] == "hash001"


def test_list_snapshots_limit(mgr: SnapshotManager) -> None:
    for i, h in enumerate(["hash001", "hash002", "hash003"]):
        with (
            patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
            patch.object(SnapshotManager, "_get_current_tree_hash", return_value=h),
        ):
            snap = mgr.capture(graph_stats_dict={"total_nodes": 10 + i, "total_edges": 5})
        mgr.save_snapshot(snap)

    assert len(mgr.list_snapshots(limit=2)) == 2


def test_diff_snapshots(mgr: SnapshotManager) -> None:
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        mgr.save_snapshot(mgr.capture(graph_stats_dict={"total_nodes": 50, "total_edges": 60}))
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash002"),
    ):
        mgr.save_snapshot(mgr.capture(graph_stats_dict={"total_nodes": 80, "total_edges": 90}))

    diff = mgr.diff_snapshots("hash001", "hash002")
    assert diff["delta"]["nodes"] == 30
    assert diff["delta"]["edges"] == 30


def test_diff_missing_snapshot(mgr: SnapshotManager) -> None:
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        mgr.save_snapshot(mgr.capture(graph_stats_dict={"total_nodes": 10, "total_edges": 5}))

    result = mgr.diff_snapshots("hash001", "missing")
    assert "error" in result


# ---------------------------------------------------------------------------
# SnapshotManager — dedup / refresh-in-place behaviour
# ---------------------------------------------------------------------------


def test_save_identical_snapshot_refreshes_in_place(
    mgr: SnapshotManager, graph_stats: dict, snap_dir: Path
) -> None:
    """Saving a second snapshot with identical version+metrics replaces the
    latest entry in the manifest rather than appending a new one."""
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        snap1 = mgr.capture(version="1.0.0", graph_stats_dict=graph_stats)
    mgr.save_snapshot(snap1)

    # Same version + metrics, different tree hash (e.g. whitespace-only commit)
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash002"),
    ):
        snap2 = mgr.capture(version="1.0.0", graph_stats_dict=graph_stats)
    mgr.save_snapshot(snap2)

    manifest = mgr.load_manifest()
    assert len(manifest.snapshots) == 1, "identical snapshot must not grow history"
    assert manifest.snapshots[0]["key"] == "hash002"
    assert not (snap_dir / "hash001.json").exists(), "old file must be removed"
    assert (snap_dir / "hash002.json").exists()


def test_save_changed_metrics_appends_new_entry(mgr: SnapshotManager, snap_dir: Path) -> None:
    """Saving a snapshot with different metrics creates a new history entry."""
    stats_a = {"total_nodes": 100, "total_edges": 150}
    stats_b = {"total_nodes": 110, "total_edges": 160}

    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        mgr.save_snapshot(mgr.capture(version="1.0.0", graph_stats_dict=stats_a))

    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash002"),
    ):
        mgr.save_snapshot(mgr.capture(version="1.0.0", graph_stats_dict=stats_b))

    manifest = mgr.load_manifest()
    assert len(manifest.snapshots) == 2
    assert (snap_dir / "hash001.json").exists()
    assert (snap_dir / "hash002.json").exists()


def test_save_force_always_appends(mgr: SnapshotManager, graph_stats: dict) -> None:
    """force=True writes a new history entry even when nothing changed."""
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        mgr.save_snapshot(mgr.capture(version="1.0.0", graph_stats_dict=graph_stats))

    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash002"),
    ):
        mgr.save_snapshot(mgr.capture(version="1.0.0", graph_stats_dict=graph_stats), force=True)

    assert len(mgr.load_manifest().snapshots) == 2


def test_metrics_changed_override(mgr: SnapshotManager, snap_dir: Path) -> None:
    """Subclass _metrics_changed override controls what counts as a real change."""

    class ThresholdManager(SnapshotManager):
        def _metrics_changed(self, new: dict, old: dict) -> bool:
            # Only record if node count changes by more than 5
            return abs(new.get("total_nodes", 0) - old.get("total_nodes", 0)) > 5

    tmgr = ThresholdManager(snap_dir / "threshold", package_name="kg-snapshot")
    base_stats = {"total_nodes": 100, "total_edges": 150}
    small_change = {"total_nodes": 103, "total_edges": 153}  # delta=3, below threshold
    big_change = {"total_nodes": 115, "total_edges": 165}  # delta=15, above threshold

    with (
        patch.object(ThresholdManager, "_get_current_branch", return_value="main"),
        patch.object(ThresholdManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        tmgr.save_snapshot(tmgr.capture(version="1.0.0", graph_stats_dict=base_stats))

    with (
        patch.object(ThresholdManager, "_get_current_branch", return_value="main"),
        patch.object(ThresholdManager, "_get_current_tree_hash", return_value="hash002"),
    ):
        tmgr.save_snapshot(tmgr.capture(version="1.0.0", graph_stats_dict=small_change))

    assert len(tmgr.load_manifest().snapshots) == 1, "small change must be suppressed"

    with (
        patch.object(ThresholdManager, "_get_current_branch", return_value="main"),
        patch.object(ThresholdManager, "_get_current_tree_hash", return_value="hash003"),
    ):
        tmgr.save_snapshot(tmgr.capture(version="1.0.0", graph_stats_dict=big_change))

    assert len(tmgr.load_manifest().snapshots) == 2, "big change must be recorded"


# ---------------------------------------------------------------------------
# SnapshotManager — git helpers (inherited by all subclasses)
# ---------------------------------------------------------------------------


def test_git_helpers_return_strings(snap_dir: Path) -> None:
    mgr = SnapshotManager(snap_dir)
    branch = mgr._get_current_branch()
    tree_hash = mgr._get_current_tree_hash()
    assert isinstance(branch, str) and len(branch) > 0
    assert isinstance(tree_hash, str) and len(tree_hash) > 0


# ---------------------------------------------------------------------------
# SnapshotManager — prune_snapshots
# ---------------------------------------------------------------------------


def _make_snap(mgr: SnapshotManager, tree_hash: str, nodes: int, version: str = "1.0.0") -> None:
    """Helper: capture + save a snapshot with controlled inputs."""
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value=tree_hash),
    ):
        mgr.save_snapshot(
            mgr.capture(
                version=version,
                graph_stats_dict={"total_nodes": nodes, "total_edges": nodes},
            ),
            force=True,  # bypass dedup so we can test prune explicitly
        )


def test_prune_removes_metric_duplicates(mgr: SnapshotManager, snap_dir: Path) -> None:
    """Interior snapshots with unchanged metrics are pruned; baseline and latest kept."""
    _make_snap(mgr, "h1", 100)
    _make_snap(mgr, "h2", 100)  # same as h1 — duplicate
    _make_snap(mgr, "h3", 100)  # same — duplicate
    _make_snap(mgr, "h4", 110)  # changed — keep
    _make_snap(mgr, "h5", 110)  # same as h4 — latest, keep

    result = mgr.prune_snapshots()

    assert set(result.removed) == {"h2", "h3"}
    assert result.broken_entries == []
    assert result.orphaned_files == []
    assert not result.dry_run

    manifest = mgr.load_manifest()
    surviving_keys = {e["key"] for e in manifest.snapshots}
    assert surviving_keys == {"h1", "h4", "h5"}
    assert not (snap_dir / "h2.json").exists()
    assert not (snap_dir / "h3.json").exists()


def test_prune_always_keeps_baseline_and_latest(mgr: SnapshotManager) -> None:
    """Even when baseline == latest metrics, both ends are preserved."""
    _make_snap(mgr, "h1", 100)
    _make_snap(mgr, "h2", 100)

    result = mgr.prune_snapshots()

    assert result.removed == []
    assert len(mgr.load_manifest().snapshots) == 2


def test_prune_removes_broken_manifest_entries(mgr: SnapshotManager, snap_dir: Path) -> None:
    """Manifest entries whose JSON file is missing are removed."""
    _make_snap(mgr, "h1", 100)
    _make_snap(mgr, "h2", 110)

    # Manually delete h2's JSON to simulate a broken entry.
    (snap_dir / "h2.json").unlink()

    result = mgr.prune_snapshots()

    assert "h2" in result.broken_entries
    surviving_keys = {e["key"] for e in mgr.load_manifest().snapshots}
    assert "h2" not in surviving_keys


def test_prune_removes_orphaned_json_files(mgr: SnapshotManager, snap_dir: Path) -> None:
    """JSON files on disk that are not in the manifest are deleted."""
    _make_snap(mgr, "h1", 100)

    orphan = snap_dir / "orphan_abc123.json"
    orphan.write_text('{"key": "orphan_abc123"}', encoding="utf-8")

    result = mgr.prune_snapshots()

    assert "orphan_abc123.json" in result.orphaned_files
    assert not orphan.exists()


def test_prune_dry_run_deletes_nothing(mgr: SnapshotManager, snap_dir: Path) -> None:
    """dry_run=True reports findings but leaves everything intact."""
    _make_snap(mgr, "h1", 100)
    _make_snap(mgr, "h2", 100)  # duplicate
    _make_snap(mgr, "h3", 110)

    orphan = snap_dir / "ghost.json"
    orphan.write_text("{}", encoding="utf-8")

    result = mgr.prune_snapshots(dry_run=True)

    assert result.dry_run is True
    assert "h2" in result.removed
    assert "ghost.json" in result.orphaned_files
    # Nothing actually deleted
    assert (snap_dir / "h2.json").exists()
    assert orphan.exists()
    assert len(mgr.load_manifest().snapshots) == 3


def test_prune_total_cleaned(mgr: SnapshotManager, snap_dir: Path) -> None:
    """total_cleaned sums all three removal categories."""
    _make_snap(mgr, "h1", 100)
    _make_snap(mgr, "h2", 100)  # duplicate
    _make_snap(mgr, "h3", 110)
    (snap_dir / "h3.json").unlink()  # make h3 broken
    (snap_dir / "stray.json").write_text("{}", encoding="utf-8")  # orphan

    result = mgr.prune_snapshots(dry_run=True)

    assert result.total_cleaned == len(result.removed) + len(result.broken_entries) + len(result.orphaned_files)


def test_prune_noop_with_few_snapshots(mgr: SnapshotManager) -> None:
    """Prune is a no-op when only one snapshot exists."""
    _make_snap(mgr, "h1", 100)

    result = mgr.prune_snapshots()

    assert result.removed == []
    assert result.broken_entries == []
    assert result.orphaned_files == []
    assert result.total_cleaned == 0


def test_prune_respects_metrics_changed_override(snap_dir: Path) -> None:
    """Subclass _metrics_changed threshold is honoured during pruning."""

    class ThresholdManager(SnapshotManager):
        def _metrics_changed(self, new: dict, old: dict) -> bool:
            return abs(new.get("total_nodes", 0) - old.get("total_nodes", 0)) > 5

    tmgr = ThresholdManager(snap_dir / "threshold", package_name="kg-snapshot")

    _make_snap(tmgr, "h1", 100)
    _make_snap(tmgr, "h2", 103)  # delta=3, below threshold → duplicate
    _make_snap(tmgr, "h3", 120)  # delta=17, above threshold → keep
    _make_snap(tmgr, "h4", 122)  # delta=2, below threshold but latest → keep

    result = tmgr.prune_snapshots()

    assert set(result.removed) == {"h2"}
    surviving = {e["key"] for e in tmgr.load_manifest().snapshots}
    assert surviving == {"h1", "h3", "h4"}


# ---------------------------------------------------------------------------
# kg_rag shim — backwards compat
# ---------------------------------------------------------------------------


def test_public_api_complete() -> None:
    """kg_snapshot exposes the full public API without any external deps."""
    from kg_snapshot import Snapshot, SnapshotManager, SnapshotManifest

    assert Snapshot.__name__ == "Snapshot"
    assert SnapshotManifest.__name__ == "SnapshotManifest"
    assert SnapshotManager.__name__ == "SnapshotManager"

    # Round-trip sanity: no kg_rag needed
    snap = Snapshot(
        branch="main",
        timestamp="2026-01-01T00:00:00+00:00",
        metrics={"total_nodes": 1, "total_edges": 0},
        tree_hash="abc",
    )
    loaded = Snapshot.from_dict(snap.to_dict())
    assert loaded.tree_hash == "abc"
