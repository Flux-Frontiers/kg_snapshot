# kg-snapshot Extraction — Handoff Notes

## What Was Done

The shared snapshot infrastructure (`Snapshot`, `SnapshotManifest`, `SnapshotManager`) was
extracted from `kg-rag` into a new zero-dependency package `kg-snapshot`.  This breaks a
latent circular dependency where domain KG packages (`code-kg`, `doc-kg`, etc.) subclassed
`SnapshotManager` from `kg-rag`, while `kg-rag` itself depended on those same packages.

## New Package

**Repo:** `../kg_snapshot` (https://github.com/Flux-Frontiers/kg_snapshot)

```
kg_snapshot/
├── pyproject.toml               # name=kg-snapshot, stdlib-only, no third-party deps
└── src/
    └── kg_snapshot/
        ├── __init__.py          # exports Snapshot, SnapshotManifest, SnapshotManager
        └── snapshots.py        # canonical implementation (moved verbatim from kg_rag)
```

**Install in any repo:**
```toml
kg-snapshot = {path = "../kg_snapshot", develop = true}
```

## Dependency Graph (After)

```
kg-snapshot   (zero deps — stdlib only)
    ▲
    ├── kg-rag        (re-export shim for backwards compat)
    ├── code-kg       (subclasses SnapshotManager directly)
    ├── doc-kg        (subclasses SnapshotManager directly)
    ├── diary-kg      (subclasses SnapshotManager directly)
    ├── ftree-kg      (subclasses SnapshotManager directly)
    └── metabo-kg     (subclasses SnapshotManager directly)
```

## Changes Per Repo

### kg-rag
- `src/kg_rag/snapshots.py` — replaced with a 3-line re-export shim.
  All existing `from kg_rag.snapshots import ...` call-sites continue to work unchanged.
- `pyproject.toml` — added `kg-snapshot` dep.

### code-kg
- `src/code_kg/snapshots.py` — changed 3 import lines from `kg_rag.snapshots` → `kg_snapshot.snapshots`.
  All domain types (`SnapshotMetrics`, `SnapshotDelta`) and the `SnapshotManager` subclass unchanged.
- `pyproject.toml` — added `kg-snapshot` dep.

### doc-kg
- `src/doc_kg/snapshots.py` — changed 3 import lines from `kg_rag.snapshots` → `kg_snapshot.snapshots`.
- `pyproject.toml` — added `kg-snapshot` as a main (non-dev) dep.

### diary-kg
- `src/diary_kg/snapshots.py` — added `kg_snapshot` import; `DiarySnapshotManager` now subclasses
  `_BaseSnapshotManager`.  All domain types (`DiarySnapshotMetrics`, `DiarySnapshotDelta`,
  `DiarySnapshot`, `DiarySnapshotManifest`) and all manager methods are **unchanged** — this was
  a deliberate Option A migration (inherit git helpers only, leave everything else alone).
  Deleted ~25 lines of duplicated `_get_current_tree_hash` / `_get_current_branch` git helpers.
- `pyproject.toml` — added `kg-snapshot` dep.

### ftree-kg
- `src/ftree_kg/snapshots.py` — replaced try/except guard around `kg_rag.snapshots` with a direct
  `kg_snapshot.snapshots` import.  `kg-snapshot` is now a real dep, not guarded optional.
- `pyproject.toml` — added `kg-snapshot` dep.

### metabo-kg
- `src/metabokg/snapshots.py` — added `kg_snapshot` import; `SnapshotManager` now subclasses
  `_BaseSnapshotManager`.  All domain types (`SnapshotMetrics`, `SnapshotDelta`, `Snapshot`,
  `SnapshotManifest`) and all manager methods are **unchanged** — Option A migration.
  Deleted ~25 lines of duplicated git helpers.  Removed `subprocess` import.
- `pyproject.toml` — added `kg-snapshot` dep.

## Rebuild Order

`kg-snapshot` must be installed before all others:

```
cd kg_snapshot && poetry install
# then in parallel:
cd code_kg   && poetry install
cd doc_kg    && poetry install
cd diary_kg  && poetry install
cd FTreeKG   && poetry install
cd metabo_kg && poetry install
# last (depends on all of the above):
cd kgrag     && poetry install
```

## Design Decisions

- **Option A for diary-kg** — `DiarySnapshot.metrics` is a typed dataclass, not a free-form dict.
  Migrating to base `Snapshot` would require changing every call-site from `snap.metrics.chunk_count`
  to `snap.metrics["chunk_count"]`.  Deferred to a future Option B/C migration.
- **`_KG_RAG_AVAILABLE` guard removed** in ftree-kg — the try/except existed because `kg-rag` was
  optional.  `kg-snapshot` has no heavy deps so there is no reason to guard it.
- **kg-rag shim preserved** — any external code or scripts that do `from kg_rag.snapshots import`
  will continue to work via the re-export.

## Future Work

- **Option B for diary-kg and metabo-kg** — unify their local `SnapshotManifest` classes with
  the base (they are structurally identical).  Safe incremental step, no caller changes needed.
- **doc-kg enrichment pipeline** — `diary-kg` has enrichment passes (topic counts, context counts,
  temporal span) that `doc-kg` lacks.  The snapshot infrastructure is now in place to track those
  metrics once the pipeline is added.
- **Publish to PyPI** — once stable, publish `kg-snapshot` as a standalone package so external
  KG modules can depend on it without a git path dep.
