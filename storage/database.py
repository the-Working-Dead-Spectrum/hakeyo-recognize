"""
Couche de stockage pour les empreintes et les pistes.
Story E2-01 : Création des tables tracks et fingerprints en BDD
"""

import sqlite3
from typing import List, Tuple, Optional
from contextlib import contextmanager


class Database:
    """Gère la connexion et les opérations sur la base de données SQLite."""
    
    def __init__(self, db_path: str = "lmre.db"):
        """
        Initialise la base de données.
        
        Args:
            db_path: Chemin vers le fichier de base de données SQLite
        """
        self.db_path = db_path
        self._init_tables()
    
    @contextmanager
    def get_connection(self):
        """Context manager pour gérer les connexions à la BDD."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_tables(self):
        """Crée les tables si elles n'existent pas déjà."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Table des pistes (tracks)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tracks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    artist TEXT,
                    album TEXT,
                    file_path TEXT UNIQUE NOT NULL,
                    duration REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Table des empreintes (fingerprints)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fingerprints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash_value INTEGER NOT NULL,
                    anchor_time REAL NOT NULL,
                    track_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
                )
            """)
            
            # Index pour accélérer les recherches par hash
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_fingerprints_hash 
                ON fingerprints(hash_value)
            """)
            
            # Index composite pour les requêtes de matching
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_fingerprints_track 
                ON fingerprints(track_id, hash_value)
            """)


def add_track(
    db: Database,
    title: str,
    file_path: str,
    artist: str = None,
    album: str = None,
    duration: float = None
) -> int:
    """
    Ajoute une nouvelle piste dans la base de données.
    
    Args:
        db: Instance de Database
        title: Titre de la piste
        file_path: Chemin vers le fichier audio
        artist: Artiste (optionnel)
        album: Album (optionnel)
        duration: Durée en secondes (optionnel)
    
    Returns:
        L'ID de la piste créée
    
    Raises:
        sqlite3.IntegrityError: Si le file_path existe déjà
    """
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tracks (title, artist, album, file_path, duration)
            VALUES (?, ?, ?, ?, ?)
        """, (title, artist, album, file_path, duration))
        
        return cursor.lastrowid


def add_fingerprints(
    db: Database,
    track_id: int,
    fingerprints: List[Tuple[int, float]]
) -> int:
    """
    Ajoute des empreintes digitales pour une piste donnée.
    
    Args:
        db: Instance de Database
        track_id: ID de la piste
        fingerprints: Liste de tuples (hash_value, anchor_time)
    
    Returns:
        Nombre d'empreintes ajoutées
    """
    if not fingerprints:
        return 0
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Insertion en batch pour la performance
        data = [
            (hash_value, anchor_time, track_id)
            for hash_value, anchor_time in fingerprints
        ]
        
        cursor.executemany("""
            INSERT INTO fingerprints (hash_value, anchor_time, track_id)
            VALUES (?, ?, ?)
        """, data)
        
        return len(data)


def get_track_by_path(db: Database, file_path: str) -> Optional[dict]:
    """
    Récupère une piste par son chemin de fichier.
    
    Args:
        db: Instance de Database
        file_path: Chemin du fichier audio
    
    Returns:
        Dictionnaire avec les infos de la piste ou None si non trouvé
    """
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, artist, album, file_path, duration, created_at
            FROM tracks
            WHERE file_path = ?
        """, (file_path,))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def get_fingerprints_by_hash(
    db: Database,
    hash_value: int
) -> List[dict]:
    """
    Récupère toutes les occurrences d'un hash donné.
    
    Args:
        db: Instance de Database
        hash_value: Valeur du hash à rechercher
    
    Returns:
        Liste de dictionnaires contenant hash_value, anchor_time, track_id
    """
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.hash_value, f.anchor_time, f.track_id, t.title
            FROM fingerprints f
            JOIN tracks t ON f.track_id = t.id
            WHERE f.hash_value = ?
        """, (hash_value,))
        
        return [dict(row) for row in cursor.fetchall()]


def count_tracks(db: Database) -> int:
    """Retourne le nombre total de pistes dans la base."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM tracks")
        return cursor.fetchone()["count"]


def count_fingerprints(db: Database) -> int:
    """Retourne le nombre total d'empreintes dans la base."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM fingerprints")
        return cursor.fetchone()["count"]
