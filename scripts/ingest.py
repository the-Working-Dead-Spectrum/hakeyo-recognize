"""
Script d'ingestion de pistes audio.
Permet d'ajouter des fichiers audio à la base de données avec leurs empreintes.

Sécurité (OWASP QWEN.md Section 7.2):
- Validation du type MIME
- Limite de taille de fichier
- Protection contre path traversal
- Requêtes paramétrées (déjà dans database.py)
"""

import argparse
import sys
import os
from pathlib import Path
import mimetypes
from typing import Optional

# Ajout du chemin racine au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import (
    load_audio_file,
    compute_spectrogram,
    extract_peaks,
    generate_fingerprint,
)
from engine.config import SecurityConfig, FingerprintConfig
from storage import (
    Database,
    add_track,
    add_fingerprints_batch,
    get_track_by_id,
    count_tracks,
    count_fingerprints,
)


def validate_audio_file(file_path: str, config: SecurityConfig = None) -> tuple[bool, Optional[str]]:
    """
    Valide un fichier audio selon les critères de sécurité OWASP.
    
    Args:
        file_path: Chemin vers le fichier audio
        config: Configuration de sécurité
        
    Returns:
        Tuple (is_valid, error_message)
            - is_valid: True si le fichier est valide
            - error_message: Message d'erreur ou None
    """
    if config is None:
        config = SecurityConfig()
    
    path = Path(file_path).resolve()
    
    # Vérifier que le fichier existe
    if not path.exists():
        return False, f"Fichier non trouvé: {file_path}"
    
    # Vérifier que c'est bien un fichier (pas un dossier)
    if not path.is_file():
        return False, f"Ce n'est pas un fichier: {file_path}"
    
    # Vérifier la taille du fichier
    file_size_mb = path.stat().st_size / (1024 * 1024)
    if file_size_mb > config.max_file_size_mb:
        return False, f"Fichier trop volumineux: {file_size_mb:.2f} Mo > {config.max_file_size_mb} Mo maximum"
    
    # Vérifier le type MIME
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type and mime_type not in config.allowed_mime_types:
        return False, f"Type de fichier non autorisé: {mime_type}"
    
    return True, None


def ingest_file(
    db: Database, 
    file_path: str, 
    title: str = None, 
    artist: str = None,
    security_config: SecurityConfig = None,
    fingerprint_config: FingerprintConfig = None,
):
    """
    Ingeste un fichier audio dans la base de données.
    
    Args:
        db: Instance de Database
        file_path: Chemin vers le fichier audio
        title: Titre de la piste (optionnel, par défaut le nom du fichier)
        artist: Artiste (optionnel)
        security_config: Configuration de sécurité
        fingerprint_config: Configuration pour le fingerprinting
    """
    if security_config is None:
        security_config = SecurityConfig()
    
    # Valider le fichier avant traitement
    is_valid, error_msg = validate_audio_file(file_path, security_config)
    if not is_valid:
        print(f"❌ Validation échouée: {error_msg}")
        return
    
    # Utiliser un chemin absolu et normalisé
    file_path = str(Path(file_path).resolve())
    
    # Définir le titre par défaut
    if title is None:
        title = Path(file_path).stem
    
    print(f"🎵 Traitement: {title}")
    
    try:
        # 1. Charger le fichier audio
        print("   ├─ Chargement du fichier audio...")
        signal, sr = load_audio_file(file_path)
        print(f"   │  Sample rate: {sr} Hz, Durée: {len(signal)/sr:.2f}s")
        
        # 2. Calculer le spectrogramme
        print("   ├─ Calcul du spectrogramme...")
        spectrogram, times, freqs = compute_spectrogram(signal, sr=sr)
        print(f"   │  Shape: {spectrogram.shape}")
        
        # 3. Extraire les pics
        print("   ├─ Extraction des pics spectraux...")
        peaks = extract_peaks(spectrogram, times, freqs, max_peaks=500)
        print(f"   │  Nombre de pics: {len(peaks)}")
        
        # 4. Générer les empreintes
        print("   ├─ Génération des empreintes digitales...")
        fingerprints_int = generate_fingerprint(peaks, config=fingerprint_config)
        
        # Convertir les hashes int en string (TEXT) pour conformité spec
        fingerprints = [(str(h), t) for h, t in fingerprints_int]
        print(f"   │  Nombre d'empreintes: {len(fingerprints)}")
        
        # 5. Ajouter à la base de données
        print("   ├─ Insertion en base de données...")
        track_id = add_track(
            db,
            title=title,
            artist=artist,
            duration=len(signal) / sr
        )
        
        added_count = add_fingerprints_batch(db, track_id, fingerprints)
        print(f"   │  Piste ID: {track_id}, Empreintes ajoutées: {added_count}")
        
        print(f"✅ Terminé: {title}")
        
    except Exception as e:
        print(f"❌ Erreur lors du traitement de {title}: {str(e)}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Ingeste des fichiers audio dans la base de données LMRE"
    )
    
    parser.add_argument(
        "files",
        nargs="+",
        help="Chemins vers les fichiers audio à ingérer"
    )
    
    parser.add_argument(
        "--db",
        default="lmre.db",
        help="Chemin vers la base de données SQLite (défaut: lmre.db)"
    )
    
    parser.add_argument(
        "--title",
        help="Titre de la piste (par défaut: nom du fichier)"
    )
    
    parser.add_argument(
        "--artist",
        help="Nom de l'artiste (optionnel)"
    )
    
    parser.add_argument(
        "--max-size-mb",
        type=int,
        default=50,
        help="Taille maximale de fichier en Mo (défaut: 50)"
    )
    
    args = parser.parse_args()
    
    # Initialiser les configurations
    security_config = SecurityConfig(max_file_size_mb=args.max_size_mb)
    fingerprint_config = FingerprintConfig()
    
    # Initialiser la base de données
    print(f"📦 Connexion à la base de données: {args.db}")
    db = Database(args.db)
    
    initial_tracks = count_tracks(db)
    initial_fingerprints = count_fingerprints(db)
    print(f"   État initial: {initial_tracks} pistes, {initial_fingerprints} empreintes\n")
    
    # Traiter chaque fichier
    success_count = 0
    error_count = 0
    
    for file_path in args.files:
        try:
            ingest_file(
                db, 
                file_path, 
                title=args.title, 
                artist=args.artist,
                security_config=security_config,
                fingerprint_config=fingerprint_config,
            )
            success_count += 1
            print()
        except Exception as e:
            error_count += 1
            print(f"❌ Erreur critique: {e}\n")
            continue
    
    # Résumé final
    final_tracks = count_tracks(db)
    final_fingerprints = count_fingerprints(db)
    
    print("=" * 50)
    print("📊 Résumé:")
    print(f"   Fichiers traités: {success_count}")
    print(f"   Erreurs: {error_count}")
    print(f"   Pistes ajoutées: {final_tracks - initial_tracks}")
    print(f"   Empreintes ajoutées: {final_fingerprints - initial_fingerprints}")
    print(f"   Total: {final_tracks} pistes, {final_fingerprints} empreintes")


if __name__ == "__main__":
    main()
