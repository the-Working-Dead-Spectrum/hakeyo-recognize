"""
Couche de stockage pour les empreintes et les pistes.
Story E2-01 : Création des tables tracks et fingerprints en BDD
"""

from .database import (
    Database,
    add_track,
    add_fingerprints,
    get_track_by_path,
    get_fingerprints_by_hash,
    count_tracks,
    count_fingerprints,
)

__all__ = [
    "Database",
    "add_track",
    "add_fingerprints",
    "get_track_by_path",
    "get_fingerprints_by_hash",
    "count_tracks",
    "count_fingerprints",
]