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
    find_matches_by_hashes,
)

from .validation import (
    ValidationError,
    validate_audio_file,
    validate_audio_for_recognition,
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    MIN_AUDIO_DURATION_SEC,
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
    "find_matches_by_hashes",
    "ValidationError",
    "validate_audio_file",
    "validate_audio_for_recognition",
    "ALLOWED_EXTENSIONS",
    "MAX_FILE_SIZE_BYTES",
    "MIN_AUDIO_DURATION_SEC",
]