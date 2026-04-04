"""
kg_snapshot — Shared Snapshot Infrastructure for KG Modules

Zero-dependency (stdlib-only) package providing:
  - :class:`Snapshot` — point-in-time KG metrics dataclass
  - :class:`SnapshotManifest` — manifest index dataclass
  - :class:`SnapshotManager` — capture, persist, compare snapshots

Domain KG packages (code-kg, doc-kg, etc.) import from here and subclass
:class:`SnapshotManager` to add domain-specific delta fields.
"""

from kg_snapshot.snapshots import PruneResult, Snapshot, SnapshotManager, SnapshotManifest

__version__ = "0.3.0"

__all__ = ["PruneResult", "Snapshot", "SnapshotManifest", "SnapshotManager"]
