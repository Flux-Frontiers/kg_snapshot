# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-04-04

### Added
- `SnapshotManager.prune_snapshots(dry_run=False)` — intelligent cleanup command that sweeps vestigial snapshots in three passes: (1) metric-duplicate interior entries (unchanged vs. prior kept entry per `_metrics_changed`), (2) broken manifest entries with missing JSON files, (3) orphaned JSON files on disk not referenced by the manifest. Baseline and latest entries are always preserved. Returns `PruneResult` with categorised removal lists and a `total_cleaned` property.
- `PruneResult` dataclass (`removed`, `orphaned_files`, `broken_entries`, `dry_run`, `total_cleaned`) exported from public API.
- 8 new tests covering all prune scenarios: metric-duplicate removal, baseline/latest protection, broken entry removal, orphaned file removal, dry-run no-op, `total_cleaned` accounting, single-snapshot no-op, and `_metrics_changed` override respect.

## [0.2.0] - 2026-04-03

### Added
- `SnapshotManager._metrics_changed(new, old)` hook — subclasses can override to define what constitutes a meaningful metric change (default: full equality)
- `save_snapshot(force=False)` dedup logic: if version and metrics are unchanged vs. the latest snapshot, the existing entry is refreshed in-place (tree hash, timestamp, branch updated; old JSON removed) instead of polluting history with a new entry
- `pylint` pre-commit hook (`^src/` only, `--rcfile=pyproject.toml`)
- Dev dependencies aligned with code_kg / doc_kg / kgrag: `pytest-cov`, `pre-commit`, `detect-secrets`, `pylint`, `pdoc`, `code-kg` (git), `doc-kg` (git)
- 4 new tests covering the dedup behaviour: refresh-in-place, changed-metrics appends, `force=True` override, and `_metrics_changed` subclass hook (22 total, all passing)
- `[tool.pylint.messages_control]` and `[tool.pytest.ini_options]` added to `pyproject.toml` to match sibling repos
- `__version__ = "0.2.0"` added to `src/kg_snapshot/__init__.py`
- `scripts/pre-commit-hook` — versioned KG-aware pre-commit hook (rebuilds CodeKG + DocKG indices, saves snapshots, then runs pre-commit framework checks)
- `scripts/install-hooks.sh` — installs `scripts/pre-commit-hook` into `.git/hooks/pre-commit`; re-run after any `pre-commit install` overwrites it
- `.gitignore` entries for `.codekg/` and `.dockg/` transient artifacts (lancedb, sqlite, models) mirroring code_kg; snapshots remain tracked

### Fixed
- `mypy` and `pytest` pre-commit hooks now invoke `.venv/bin/mypy` / `.venv/bin/pytest` directly, bypassing a Poetry env-detection issue on macOS where `poetry run` resolved to the system Python instead of the in-project `.venv`

## [0.1.0] - 2026-04-03

### Added
- `Snapshot`, `SnapshotManifest`, and `SnapshotManager` core classes in `src/kg_snapshot/snapshots.py` — zero-dependency snapshot engine extracted from kg-rag so domain KG packages can subclass without taking a hard dependency
- Package scaffolding: `pyproject.toml`, `poetry.toml`, `poetry.lock` with Python ≥3.12 and dev deps (pytest, ruff, mypy)
- Pre-commit hooks: trailing-whitespace, end-of-file-fixer, check-yaml/toml, detect-secrets, ruff, ruff-format, mypy, pytest, poetry-check
- GitHub Actions CI workflow: lint, type-check, and test jobs across Python 3.12 and 3.13
- GitHub Actions publish workflow for PyPI releases triggered by version tags
- `tests/test_snapshot_base.py` baseline test suite for core snapshot classes
- `scripts/run_tests.sh` helper for local test execution
- `HANDOFF.md` and `SNAPSHOTS.md` project documentation
