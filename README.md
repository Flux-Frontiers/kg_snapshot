[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![License: Elastic-2.0](https://img.shields.io/badge/License-Elastic%202.0-blue.svg)](https://www.elastic.co/licensing/elastic-license)
[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/Flux-Frontiers/kg_snapshot/releases)
[![CI](https://github.com/Flux-Frontiers/kg_snapshot/actions/workflows/ci.yml/badge.svg)](https://github.com/Flux-Frontiers/kg_snapshot/actions/workflows/ci.yml)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)

**kg-snapshot** — Shared Snapshot Infrastructure for the KGRAG Framework

*Author: Eric G. Suchanek, PhD*

*Flux-Frontiers, Liberty TWP, OH*

---

## Overview

`kg-snapshot` is a **zero-dependency, stdlib-only** package providing the canonical snapshot
infrastructure shared across all KGRAG domain knowledge graph packages — `code-kg`, `doc-kg`,
`diary-kg`, `ftree-kg`, `metabo-kg`, and others.

It was extracted from `kg-rag` to break a structural circular dependency: domain KG packages
need to subclass `SnapshotManager` to capture domain-specific metrics, but they cannot depend
on `kg-rag` if `kg-rag` itself depends on them.

By depending only on the Python standard library, `kg-snapshot` can sit at the base of the
entire KGRAG dependency tree with no conflicts.

---

## What's Inside

| Class | Purpose |
|-------|---------|
| `Snapshot` | Point-in-time metrics dataclass — keyed by git tree hash, holds free-form `metrics` dict plus `vs_previous` / `vs_baseline` deltas |
| `SnapshotManifest` | JSON manifest index — tracks all snapshots with fast lookup by key |
| `SnapshotManager` | Capture, persist, retrieve, compare, and diff snapshots — subclass to add domain-specific delta fields |

All three are importable directly from `kg_snapshot`:

```python
from kg_snapshot import Snapshot, SnapshotManifest, SnapshotManager
```

---

## Design

### Free-form metrics

`Snapshot.metrics` is a plain `dict` so each domain stores whatever fields it needs
without touching shared code:

```python
# code-kg stores node/edge counts by kind
metrics = {"total_nodes": 342, "total_edges": 5711, "node_counts": {"function": 70, ...}}

# doc-kg stores coverage and chunk info
metrics = {"total_nodes": 800, "coverage_score": 0.91, "chunk_count": 640}

# metabo-kg stores pathway and kinetic parameter counts
metrics = {"total_nodes": 500, "pathway_count": 50, "kinetic_params": 1200}
```

The only required keys are `total_nodes` and `total_edges` — used for universal delta computation.

### Subclass for domain deltas

Override `_compute_delta_from_metrics` to add domain-specific delta fields:

```python
from kg_snapshot import SnapshotManager

class MyKGSnapshotManager(SnapshotManager):
    def _compute_delta_from_metrics(self, new_m, old_m):
        base = super()._compute_delta_from_metrics(new_m, old_m)
        base["coverage_delta"] = new_m.get("coverage", 0) - old_m.get("coverage", 0)
        return base
```

### Git helpers included

`SnapshotManager` provides `_get_current_tree_hash()` and `_get_current_branch()` as
`@staticmethod` methods so subclasses inherit them for free — no duplication across repos.

---

## Quick Start

### Install

```bash
# From PyPI (once published)
pip install kg-snapshot

# From source (editable, for local development)
pip install -e /path/to/kg_snapshot
```

Or in a Poetry project's `pyproject.toml`:

```toml
[tool.poetry.dependencies]
kg-snapshot = {path = "../kg_snapshot", develop = true}
```

### Capture and save a snapshot

```python
from kg_snapshot import SnapshotManager

mgr = SnapshotManager(".mykg/snapshots", package_name="my-kg")

# Capture — graph_stats_dict from your KG's stats() method
# Any additional kwargs are merged into the metrics dict
snapshot = mgr.capture(
    version="1.0.0",
    graph_stats_dict={"total_nodes": 500, "total_edges": 800},
    coverage=0.87,
)
mgr.save_snapshot(snapshot)
```

### Query snapshots

```python
# Load specific or latest
snap = mgr.load_snapshot("latest")
print(snap.metrics["total_nodes"])
print(snap.vs_previous)   # delta from previous snapshot (backfilled on load)

# List in reverse chronological order
for entry in mgr.list_snapshots(limit=10):
    print(entry["timestamp"], entry["metrics"]["total_nodes"])

# Diff two snapshots
diff = mgr.diff_snapshots(key_a, key_b)
print(diff["delta"])
```

---

## Dependency Graph

```
kg-snapshot   (zero deps — stdlib only)
    ▲
    ├── kg-rag        (re-exports for backwards compat)
    ├── code-kg       (CodeKGSnapshotManager subclass)
    ├── doc-kg        (DocKGSnapshotManager subclass)
    ├── diary-kg      (DiarySnapshotManager subclass)
    ├── ftree-kg      (FtreeSnapshotManager subclass)
    └── metabo-kg     (SnapshotManager subclass)
```

`kg-rag` re-exports `Snapshot`, `SnapshotManifest`, and `SnapshotManager` from `kg_snapshot`
via a thin compatibility shim — all existing `from kg_rag.snapshots import ...` call-sites
continue to work unchanged.

---

## Requirements

- Python ≥ 3.12, < 3.14
- No third-party dependencies (stdlib only: `dataclasses`, `json`, `pathlib`, `subprocess`, `datetime`, `importlib.metadata`)

---

## Development

```bash
git clone https://github.com/Flux-Frontiers/kg_snapshot.git
cd kg_snapshot
poetry install
poetry run pytest tests/ -v
```

### Running the full KGRAG test suite

The `scripts/run_tests.sh` script runs all snapshot-related tests across every domain package
in dependency order:

```bash
bash scripts/run_tests.sh
```

| Phase | What it does |
|-------|-------------|
| **1** | `kg_snapshot` base tests — 18 tests, no domain deps required |
| **2** | Domain subclass tests in each repo's own venv |
| **3** | Import chain smoke-test per repo |
| **4** | Load real on-disk snapshots from built KG instances |

---

## Project Structure

```
kg_snapshot/
├── README.md
├── SNAPSHOTS.md              # Full extraction handoff notes
├── pyproject.toml
├── src/
│   └── kg_snapshot/
│       ├── __init__.py       # Public API: Snapshot, SnapshotManifest, SnapshotManager
│       └── snapshots.py      # Full implementation (stdlib only)
├── tests/
│   └── test_snapshot_base.py # 18 tests — round-trip, deltas, manifest, git helpers
└── scripts/
    └── run_tests.sh          # Full KGRAG-wide snapshot test runner
```

---

## Related Projects

- **[KGRAG](https://github.com/Flux-Frontiers/KGRAG)** — Unified orchestration layer (re-exports kg-snapshot for compatibility)
- **[CodeKG](https://github.com/Flux-Frontiers/code_kg)** — Structural knowledge graph for Python codebases
- **[DocKG](https://github.com/Flux-Frontiers/doc_kg)** — Semantic knowledge graph for document corpora
- **[MetaKG](https://github.com/Flux-Frontiers/metabo_kg)** — Metabolic pathway knowledge graph

---

## License

[Elastic License 2.0](https://www.elastic.co/licensing/elastic-license) — see [LICENSE](LICENSE).

Free to use, modify, and distribute. You may not offer the software as a hosted or managed service to third parties. Commercial use internally is permitted.
