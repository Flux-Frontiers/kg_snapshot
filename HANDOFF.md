# kg-snapshot — Project Handoff

*Last updated: 2026-04-03 (updated: pre-commit working)*
*Author: Eric G. Suchanek, PhD — Flux-Frontiers*

---

## What This Is

`kg-snapshot` is a zero-dependency (stdlib-only) Python package extracted from `kg-rag` to
hold the shared snapshot infrastructure for the entire KGRAG framework.  It contains exactly
three public classes:

- `Snapshot` — point-in-time metrics dataclass, keyed by git tree hash
- `SnapshotManifest` — JSON manifest index of all snapshots
- `SnapshotManager` — capture / persist / compare / diff engine; subclass per domain

**Why it exists:** domain KG packages (`code-kg`, `doc-kg`, etc.) need to subclass
`SnapshotManager` to add domain-specific metrics.  But `kg-rag` depends on those same
packages.  Putting `SnapshotManager` in `kg-rag` created a latent circular dependency.
Extracting it into a package with no third-party deps breaks the cycle cleanly.

---

## State of the Work (as of handoff)

### Completed

| Task | Status |
|------|--------|
| Package scaffolded (`pyproject.toml`, `__init__.py`, `snapshots.py`) | ✅ |
| `kg_rag/snapshots.py` replaced with 3-line re-export shim | ✅ |
| `code_kg/snapshots.py` imports patched | ✅ |
| `doc_kg/snapshots.py` imports patched | ✅ |
| `diary_kg/snapshots.py` — Option A migration (subclass, git helpers inherited) | ✅ |
| `ftree_kg/snapshots.py` — try/except guard replaced with direct import | ✅ |
| `metabo_kg/snapshots.py` — Option A migration (subclass, git helpers inherited) | ✅ |
| `kg-snapshot` dep added to all 6 `pyproject.toml` files | ✅ |
| Base test suite — 18 tests, no domain deps | ✅ passing |
| Domain subclass tests — `diary_kg` (7), `metabo_kg` (8) | ✅ passing |
| `code_kg` full snapshot suite (48 tests) | ✅ passing |
| `doc_kg` full snapshot suite (58 tests) | ✅ passing |
| `scripts/run_tests.sh` — 4-phase cross-repo runner | ✅ |
| CI workflows (ci.yml, publish.yml) | ✅ written, not yet triggered |
| README.md | ✅ |
| SNAPSHOTS.md — technical extraction notes | ✅ |
| CHANGELOG.md | ✅ created (v0.1.0 entry) |
| Pre-commit hooks | ✅ installed and fully passing — ruff, ruff-format, mypy, pytest, poetry-check, detect-secrets, standard file hygiene |
| `poetry.toml` — `virtualenvs.in-project = true` | ✅ in-project `.venv` configured |
| `.secrets.baseline` | ✅ generated |

### Not Done / Known Gaps

| Item | Notes |
|------|-------|
| **GitHub CI — first push** | Workflows written but never triggered. First push to `main` will run the lint + test matrix on py3.12 and py3.13. |
| **Logos** | `README.md` references `assets/logo.png` — does not exist yet. Remove the `<img>` block or create a logo before the first public push. Same gap exists in kg-rag, code-kg, doc-kg, waverider READMEs. |
| `ftree_kg` test suite | No `tests/` directory in FTreeKG yet. `run_tests.sh` skips it. Write `tests/test_snapshot_subclass.py` there when ready. |
| Option B migrations | `diary_kg` and `metabo_kg` both have their own `SnapshotManifest` dataclasses that are structurally identical to the base. Safe next step: replace with base class, remove ~20 lines each. No caller changes needed. |
| Option C migrations | `diary_kg` uses typed `DiarySnapshotMetrics` for attribute access (`snap.metrics.chunk_count`). `metabo_kg` same. Migrating to free-form dict requires changing every caller. Deferred intentionally — low priority. |
| PyPI publish | Currently local path deps (`{path = "../kg_snapshot", develop = true}`). Once the repo is public and stable, publish to PyPI and switch all deps to `kg-snapshot = "^0.1.0"`. |
| `kg-rag` shim identity test | `test_kg_rag_shim_exports_same_class_names` was replaced with `test_public_api_complete` because `is` identity only holds when both packages are loaded from the same editable install. The functional round-trip test is sufficient. |

---

## Repo Layout

```
kg_snapshot/
├── README.md                     # Public-facing docs
├── SNAPSHOTS.md                  # Technical extraction notes (full dep graph, per-repo changes)
├── HANDOFF.md                    # This file
├── pyproject.toml                # name=kg-snapshot, stdlib-only, no deps
├── poetry.lock
├── src/
│   └── kg_snapshot/
│       ├── __init__.py           # Exports: Snapshot, SnapshotManifest, SnapshotManager
│       └── snapshots.py          # Canonical implementation
├── tests/
│   └── test_snapshot_base.py     # 18 unit tests — all stdlib, no domain deps
├── scripts/
│   └── run_tests.sh              # Cross-repo 4-phase test runner
└── .github/
    └── workflows/
        ├── ci.yml                # Lint + type-check + test (py3.12, py3.13)
        └── publish.yml           # Build + release on v* tag
```

---

## How Each Repo Uses It

### Repos that subclass `SnapshotManager` for domain delta fields

| Repo | Class | Domain-specific delta fields |
|------|-------|------------------------------|
| `code_kg` | `SnapshotManager` (in `code_kg.snapshots`) | `coverage_delta`, `critical_issues_delta`, per-module node counts |
| `doc_kg` | `SnapshotManager` (in `doc_kg.snapshots`) | `coverage_delta`, `issues_delta` |
| `diary_kg` | `DiarySnapshotManager` | `chunks`, `entries` (typed `DiarySnapshotDelta`) |
| `ftree_kg` | `FtreeSnapshotManager` | `files_delta`, `dirs_delta` |
| `metabo_kg` | `SnapshotManager` (in `metabokg.snapshots`) | `kinetic_params_delta`, `pathway_delta` (typed `SnapshotDelta`) |

### Repos that re-export for backwards compat

| Repo | What it does |
|------|-------------|
| `kg-rag` | `kg_rag/snapshots.py` re-exports all three classes — `from kg_rag.snapshots import ...` still works |

---

## Running the Tests

```bash
# Phase 1 only (no domain installs needed)
cd /path/to/kg_snapshot
python -m pytest tests/ -v

# Full cross-repo suite (requires all repo venvs built)
bash scripts/run_tests.sh
```

Expected output (all passing):

```
Phase 1 — kg_snapshot base tests:      18 passed
Phase 2 — code_kg snapshot tests:      48 passed
Phase 2 — doc_kg snapshot tests:       58 passed
Phase 2 — diary_kg subclass tests:      7 passed
Phase 2 — metabo_kg subclass tests:     8 passed
Phase 3 — import chain smoke-test:      6 OK
Phase 4 — on-disk snapshot loads:       3 OK
```

---

## Rebuild Order (after any structural change)

`kg-snapshot` must be installed before anything else:

```bash
cd kg_snapshot && poetry install           # first, always
cd code_kg    && poetry install            # then domain packages (order within this group doesn't matter)
cd doc_kg     && poetry install
cd diary_kg   && poetry install
cd FTreeKG    && poetry install
cd metabo_kg  && poetry install
cd kgrag      && poetry install            # last — depends on all of the above
```

---

## Next Steps (Recommended)

1. **Create a logo.** Even a simple wordmark PNG at `assets/logo.png` is enough to unblock
   the READMEs. Same need exists across kg-rag, code-kg, doc-kg, waverider.

2. **Push to GitHub and verify CI.** The workflows are written but have never run. First push
   to `main` will trigger the lint + test matrix.

3. **Option B migration for diary_kg and metabo_kg.** Replace their local `SnapshotManifest`
   dataclasses with the base class. Purely mechanical, no caller changes.

4. **Write `ftree_kg/tests/test_snapshot_subclass.py`.** Copy the metabo_kg version as a
   template, swap in `FtreeSnapshotManager` and ftree-specific delta fields.

5. **Switch pyproject deps from path to PyPI once published.** Replace
   `{path = "../kg_snapshot", develop = true}` with `"^0.1.0"` in all 6 repos.

6. **doc-kg enrichment pipeline.** `diary_kg` has enrichment passes (topic counts, context
   counts, temporal span) that `doc-kg` currently lacks. The snapshot infrastructure now
   supports tracking those metrics — the pipeline work is the remaining piece.

---

## Key Design Decisions (and Why)

**Option A migration for diary_kg and metabo_kg** — both use typed dataclasses for metrics
(`DiarySnapshotMetrics`, `SnapshotMetrics`) so attribute access like `snap.metrics.chunk_count`
works throughout the codebase. Migrating to the base's free-form dict would require changing
every caller. The Option A approach (inherit git helpers only, leave domain types alone) gives
all the benefits of the shared base with zero risk to working code.

**`_KG_RAG_AVAILABLE` guard removed from ftree_kg** — the original try/except existed because
`kg-rag` was an optional dep. `kg-snapshot` has no heavy deps so it is always available; the
guard is misleading and was dropped.

**`vs_previous` is backfilled on load, not at capture time** — `capture()` only computes
`vs_previous` when the current tree hash is already in the manifest (a re-capture). For a
brand-new snapshot the delta is backfilled by `load_snapshot()` from adjacent manifest entries.
Tests verify the loaded snapshot, not the just-captured one.

**The kg_rag shim test uses name equality, not object identity** — `is` identity only holds
when both packages load from the same editable install. In a non-editable or cross-venv
scenario they are different objects. The test was changed to verify class names and a
functional round-trip instead.
