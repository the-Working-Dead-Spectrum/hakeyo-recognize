"""
Tests pour la couche de stockage (Story E2-01).
Conforme au schéma QWEN.md Section 5.
"""

import pytest
import os
import tempfile
from pathlib import Path

# Import des modules à tester
from storage.database import (
    Database,
    add_track,
    add_fingerprint,
    add_fingerprints_batch,
    get_track_by_id,
    get_fingerprints_by_hash,
    count_tracks,
    count_fingerprints,
)


class TestDatabase:
    """Tests pour la base de données (Story E2-01)."""
    
    @pytest.fixture
    def db(self):
        """Crée une base de données temporaire pour chaque test."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name
        
        db = Database(temp_path)
        yield db
        
        # Nettoyage après le test
        os.unlink(temp_path)
    
    def test_database_initialization(self, db):
        """Vérifie que la base de données est initialisée correctement."""
        assert os.path.exists(db.db_path), "Le fichier de BDD doit exister"
        assert count_tracks(db) == 0, "La base doit être vide au départ"
        assert count_fingerprints(db) == 0, "La base doit être vide au départ"
    
    def test_add_track(self, db):
        """Vérifie l'ajout d'une piste."""
        track_id = add_track(
            db,
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            duration=180.5
        )
        
        assert track_id is not None, "L'ID de la piste ne doit pas être None"
        assert track_id > 0, "L'ID doit être positif"
        assert count_tracks(db) == 1, "Il doit y avoir 1 piste dans la BDD"
    
    def test_get_track_by_id(self, db):
        """Vérifie la récupération d'une piste par son ID."""
        track_id = add_track(
            db,
            title="Test Song",
            artist="Test Artist"
        )
        
        track = get_track_by_id(db, track_id)
        
        assert track is not None, "La piste doit être trouvée"
        assert track["title"] == "Test Song"
        assert track["artist"] == "Test Artist"
    
    def test_get_track_by_id_not_found(self, db):
        """Vérifie le comportement quand la piste n'existe pas."""
        track = get_track_by_id(db, 999)
        assert track is None, "Doit retourner None si la piste n'existe pas"
    
    def test_add_fingerprint(self, db):
        """Vérifie l'ajout d'une empreinte digitale (hash en TEXT)."""
        track_id = add_track(db, title="Test", artist="Test")
        
        # hash_value doit être une chaîne (TEXT conforme spec)
        fingerprint_id = add_fingerprint(db, track_id, "12345", 0.1)
        
        assert fingerprint_id is not None
        assert count_fingerprints(db) == 1
    
    def test_add_fingerprints_batch(self, db):
        """Vérifie l'ajout batch d'empreintes digitales."""
        track_id = add_track(db, title="Test", artist="Test")
        
        # hashes doivent être des strings (TEXT conforme spec)
        fingerprints = [
            ("12345", 0.1),
            ("67890", 0.2),
            ("11111", 0.3),
        ]
        
        count = add_fingerprints_batch(db, track_id, fingerprints)
        
        assert count == 3, "3 empreintes doivent être ajoutées"
        assert count_fingerprints(db) == 3, "Il doit y avoir 3 empreintes dans la BDD"
    
    def test_add_fingerprints_batch_empty(self, db):
        """Vérifie le comportement avec une liste vide d'empreintes."""
        track_id = add_track(db, title="Test", artist="Test")
        
        count = add_fingerprints_batch(db, track_id, [])
        
        assert count == 0, "Aucune empreinte ne doit être ajoutée"
        assert count_fingerprints(db) == 0
    
    def test_get_fingerprints_by_hash(self, db):
        """Vérifie la récupération d'empreintes par hash (TEXT)."""
        track_id = add_track(db, title="Test Song", artist="Test")
        
        # hash en TEXT
        fingerprints = [("12345", 0.1), ("12345", 0.5)]
        add_fingerprints_batch(db, track_id, fingerprints)
        
        results = get_fingerprints_by_hash(db, "12345")
        
        assert len(results) == 2, "Doit trouver 2 occurrences du hash"
        assert all(r["hash"] == "12345" for r in results)
    
    def test_get_fingerprints_by_hash_not_found(self, db):
        """Vérifie le comportement quand le hash n'existe pas."""
        results = get_fingerprints_by_hash(db, "99999")
        assert results == [], "Doit retourner une liste vide"
    
    def test_track_fingerprint_relationship(self, db):
        """Vérifie la relation entre pistes et empreintes."""
        # Ajouter deux pistes
        track1_id = add_track(db, title="Song 1", artist="Artist 1")
        track2_id = add_track(db, title="Song 2", artist="Artist 2")
        
        # Ajouter des empreintes différentes (hash en TEXT)
        add_fingerprints_batch(db, track1_id, [("111", 0.1), ("222", 0.2)])
        add_fingerprints_batch(db, track2_id, [("333", 0.3), ("444", 0.4)])
        
        assert count_tracks(db) == 2
        assert count_fingerprints(db) == 4
        
        # Vérifier que les empreintes sont associées aux bonnes pistes
        results1 = get_fingerprints_by_hash(db, "111")
        assert len(results1) == 1
        assert results1[0]["track_id"] == track1_id
        assert results1[0]["title"] == "Song 1"
    
    def test_schema_conformity_hash_is_text(self, db):
        """Vérifie que le champ hash est bien de type TEXT (QWEN.md Section 5)."""
        import sqlite3
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(fingerprints)")
            columns = {row['name']: row['type'] for row in cursor.fetchall()}
            
            assert 'hash' in columns, "La colonne 'hash' doit exister"
            assert columns['hash'].upper() == 'TEXT', "Le champ hash doit être TEXT"
            assert 'offset' in columns, "La colonne 'offset' doit exister"
    
    def test_index_on_hash_exists(self, db):
        """Vérifie que l'index sur hash existe (QWEN.md Section 5)."""
        import sqlite3
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = [row['name'] for row in cursor.fetchall()]
            
            assert 'idx_fingerprint_hash' in indexes, "L'index idx_fingerprint_hash doit exister"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
