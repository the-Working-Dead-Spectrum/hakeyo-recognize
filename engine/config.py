"""
Configuration du moteur LMRE.
Centralise tous les paramètres ajustables pour éviter les valeurs en dur.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AudioConfig:
    """Configuration du traitement audio."""
    sample_rate: int = 11025  # Fréquence d'échantillonnage cible (Hz)
    n_fft: int = 2048  # Taille de la fenêtre FFT
    hop_length: int = 512  # Pas entre les fenêtres
    n_mels: int = 128  # Nombre de bandes Mel
    fmin: float = 300.0  # Fréquence minimale (Hz) - voix humaine
    fmax: float = 8000.0  # Fréquence maximale (Hz)
    
    
@dataclass
class PeakPickingConfig:
    """Configuration de l'extraction des pics."""
    neighborhood_size: int = 5  # Taille de la fenêtre pour maxima locaux
    threshold_db: float = -60.0  # Seuil minimal en dB
    max_peaks_per_second: int = 50  # Densité maximale de pics par seconde
    

@dataclass
class FingerprintConfig:
    """
    Configuration de la génération de fingerprints.
    
    Justification des choix techniques :
    - target_zone_duration: ~5s selon spécification Shazam (Section 4 QWEN.md)
      Permet de capturer des relations temporelles significatives sans explosion combinatoire
    - freq_bin: 100 Hz pour quantifier les fréquences
      Suffisamment fin pour distinguer les notes, assez grossier pour être robuste
    - time_bin: 0.01s (10ms) pour quantifier le temps
      Correspond à la résolution temporelle humaine pour la perception rythmique
    - hash_bits: 64 bits pour réduire les collisions
      32 bits génère trop de collisions au-delà de 1000 morceaux
    """
    target_zone_duration: float = 5.0  # Fenêtre temporelle cible (secondes)
    max_freq_diff: float = 3000.0  # Différence maximale de fréquence (Hz)
    freq_bin: float = 100.0  # Bin de fréquence pour quantification (Hz)
    time_bin: float = 0.01  # Bin de temps pour quantification (secondes)
    hash_bits: int = 64  # Nombre de bits du hash
    min_fingerprint_pairs: int = 3  # Minimum de paires pour valider un match
    

@dataclass
class MatchingConfig:
    """
    Configuration du matching (Sprint 2+).
    
    CONFIDENCE_THRESHOLD: 0.15 est une valeur de départ suggérée
    À ajuster empiriquement selon le dataset et le taux de faux positifs acceptable
    """
    confidence_threshold: float = 0.15  # Seuil de confiance minimum
    min_hash_matches: int = 5  # Nombre minimum de hash matches pour considérer un candidat
    histogram_bin_width: float = 0.1  # Largeur des bins pour l'histogramme d'offsets (secondes)
    

@dataclass
class DatabaseConfig:
    """Configuration de la base de données."""
    sqlite_path: str = "lmre.db"  # Chemin SQLite pour dev local
    postgres_uri: Optional[str] = None  # URI PostgreSQL pour production
    # Format: postgresql://user:password@host:port/dbname
    # Doit être défini via variable d'environnement LMRE_DATABASE_URL
    

@dataclass
class SecurityConfig:
    """
    Configuration de sécurité (OWASP).
    
    Références :
    - A03: Injection prevention
    - A04: Upload de fichiers sécurisé
    - A02: Gestion des secrets
    """
    max_file_size_mb: int = 50  # Taille maximale d'un fichier audio (Mo)
    allowed_mime_types: list = None  # Types MIME autorisés
    
    def __post_init__(self):
        if self.allowed_mime_types is None:
            self.allowed_mime_types = [
                "audio/mpeg",
                "audio/wav",
                "audio/ogg",
                "audio/flac",
                "audio/mp4",
                "audio/x-m4a",
            ]


# Instance de configuration globale
# Peut être overriding via variables d'environnement ou fichier .env
DEFAULT_CONFIG = {
    "audio": AudioConfig(),
    "peak_picking": PeakPickingConfig(),
    "fingerprint": FingerprintConfig(),
    "matching": MatchingConfig(),
    "database": DatabaseConfig(),
    "security": SecurityConfig(),
}


def get_config(section: str = None):
    """
    Récupère la configuration globale ou une section spécifique.
    
    Args:
        section: Nom de la section ('audio', 'fingerprint', etc.) ou None pour tout
        
    Returns:
        Dataclass de configuration ou dict de toutes les configurations
    """
    if section is None:
        return DEFAULT_CONFIG
    return DEFAULT_CONFIG.get(section)
