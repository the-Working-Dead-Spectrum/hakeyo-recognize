"""
Couche de stockage pour les empreintes et les pistes.
Story E2-01 : Création des tables tracks et fingerprints en BDD
"""

from .database import (
    Database,
    DatabaseError,
    add_track,
    add_fingerprint,
    add_fingerprints_batch,
    get_track_by_id,
    get_fingerprints_by_hash,
    get_candidate_tracks,
    count_tracks,
    count_fingerprints,
)

__all__ = [
    "Database",
    "DatabaseError",
    "add_track",
    "add_fingerprint",
    "add_fingerprints_batch",
    "get_track_by_id",
    "get_fingerprints_by_hash",
    "get_candidate_tracks",
    "count_tracks",
    "count_fingerprints",
]