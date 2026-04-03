#!/usr/bin/env bash
# install-hooks.sh — Install the KG-aware git pre-commit hook for kg-snapshot.
#
# Replaces the standard pre-commit stub with a wrapper that:
#   1. Rebuilds the CodeKG index (if .codekg/ exists) and saves a snapshot
#   2. Rebuilds the DocKG index  (if .dockg/  exists) and saves a snapshot
#   3. Stages the snapshot files
#   4. Runs the pre-commit framework checks
#
# Usage:
#   bash scripts/install-hooks.sh
#
# Skip KG snapshots during a commit (e.g. for quick fixups):
#   CODEKG_SKIP_SNAPSHOT=1 git commit ...

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
HOOK="$REPO_ROOT/.git/hooks/pre-commit"
SOURCE="$REPO_ROOT/scripts/pre-commit-hook"

cp "$SOURCE" "$HOOK"
chmod +x "$HOOK"
echo "Installed KG-aware pre-commit hook → $HOOK"
