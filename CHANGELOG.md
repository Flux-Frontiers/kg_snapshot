# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
