"""
Couche de stockage pour les empreintes et les pistes.
Story E2-01 : Création des tables tracks et fingerprints en BDD

Conforme au schéma QWEN.md Section 5:
- hash en TEXT (pas INTEGER)
- offset au lieu de anchor_time
- Index obligatoire sur hash
"""

import sqlite3
from typing import List, Tuple, Optional
from contextlib import contextmanager


class DatabaseError(Exception):
    """Exception levée lors d'opérations sur la base de données."""
    pass


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
            raise DatabaseError(f"Erreur de transaction: {str(e)}") from e
        finally:
            conn.close()
    
    def _init_tables(self):
        """Crée les tables si elles n'existent pas déjà."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Table des pistes (tracks) - conforme QWEN.md Section 5
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tracks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    artist TEXT,
                    album TEXT,
                    duration REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Table des empreintes (fingerprints) - conforme QWEN.md Section 5
            # Utilise 'hash' (TEXT) et 'offset' (FLOAT) comme spécifié
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fingerprints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
                    hash TEXT NOT NULL,
                    offset REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Index sur hash - NON NÉGOCIABLE selon QWEN.md Section 5
            # Sans lui, le matching devient inutilisable au-delà de quelques centaines de morceaux
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_fingerprint_hash 
                ON fingerprints(hash)
            """)
            
            # Index composite pour les requêtes de matching
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_fingerprints_track 
                ON fingerprints(track_id, hash)
            """)


def add_track(
    db: Database,
    title: str,
    artist: str = None,
    album: str = None,
    duration: float = None
) -> int:
    """
    Ajoute une nouvelle piste dans la base de données.
    
    Args:
        db: Instance de Database
        title: Titre de la piste
        artist: Artiste (optionnel)
        album: Album (optionnel)
        duration: Durée en secondes (optionnel)
    
    Returns:
        L'ID de la piste créée
        
    Raises:
        DatabaseError: En cas d'erreur d'insertion
    """
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tracks (title, artist, album, duration)
            VALUES (?, ?, ?, ?)
        """, (title, artist, album, duration))
        
        return cursor.lastrowid


def add_fingerprint(
    db: Database,
    track_id: int,
    hash_value: str,
    offset: float
) -> int:
    """
    Ajoute une empreinte digitale pour une piste donnée.
    
    Args:
        db: Instance de Database
        track_id: ID de la piste
        hash_value: Hash de l'empreinte (TEXT, conforme spec)
        offset: Temps du pic ancre en secondes
    
    Returns:
        ID de l'empreinte créée
    """
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO fingerprints (track_id, hash, offset)
            VALUES (?, ?, ?)
        """, (track_id, hash_value, offset))
        
        return cursor.lastrowid


def add_fingerprints_batch(
    db: Database,
    track_id: int,
    fingerprints: List[Tuple[str, float]]
) -> int:
    """
    Ajoute des empreintes digitales pour une piste donnée (batch).
    
    Args:
        db: Instance de Database
        track_id: ID de la piste
        fingerprints: Liste de tuples (hash_value, offset)
                     hash_value doit être une chaîne de caractères (TEXT)
    
    Returns:
        Nombre d'empreintes ajoutées
    """
    if not fingerprints:
        return 0
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Insertion en batch pour la performance
        data = [
            (track_id, hash_value, offset)
            for hash_value, offset in fingerprints
        ]
        
        cursor.executemany("""
            INSERT INTO fingerprints (track_id, hash, offset)
            VALUES (?, ?, ?)
        """, data)
        
        return len(data)


def get_track_by_id(db: Database, track_id: int) -> Optional[dict]:
    """
    Récupère une piste par son ID.
    
    Args:
        db: Instance de Database
        track_id: ID de la piste
    
    Returns:
        Dictionnaire avec les infos de la piste ou None si non trouvé
    """
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, artist, album, duration, created_at
            FROM tracks
            WHERE id = ?
        """, (track_id,))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def get_fingerprints_by_hash(
    db: Database,
    hash_value: str
) -> List[dict]:
    """
    Récupère toutes les occurrences d'un hash donné.
    
    Args:
        db: Instance de Database
        hash_value: Valeur du hash à rechercher (TEXT)
    
    Returns:
        Liste de dictionnaires contenant hash, offset, track_id, title
    """
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.hash, f.offset, f.track_id, t.title
            FROM fingerprints f
            JOIN tracks t ON f.track_id = t.id
            WHERE f.hash = ?
        """, (hash_value,))
        
        return [dict(row) for row in cursor.fetchall()]


def get_candidate_tracks(
    db: Database,
    hashes: List[str],
    min_matches: int = 1
) -> List[dict]:
    """
    Récupère les pistes candidates ayant au moins min_matches hash communs.
    
    Utilisé pour le matching (Sprint 2+).
    
    Args:
        db: Instance de Database
        hashes: Liste des hashes de la requête
        min_matches: Nombre minimum de matches pour considérer un candidat
    
    Returns:
        Liste de dicts: {track_id, title, match_count, offsets}
    """
    if not hashes:
        return []
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Créer une table temporaire pour les hashes de la requête
        placeholders = ','.join('?' * len(hashes))
        query = f"""
            SELECT f.track_id, t.title, COUNT(*) as match_count,
                   GROUP_CONCAT(f.offset) as offsets
            FROM fingerprints f
            JOIN tracks t ON f.track_id = t.id
            WHERE f.hash IN ({placeholders})
            GROUP BY f.track_id, t.title
            HAVING match_count >= ?
            ORDER BY match_count DESC
        """
        
        cursor.execute(query, hashes + [min_matches])
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'track_id': row['track_id'],
                'title': row['title'],
                'match_count': row['match_count'],
                'offsets': [float(x) for x in row['offsets'].split(',')] if row['offsets'] else []
            })
        
        return results


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
