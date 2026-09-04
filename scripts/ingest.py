"""
Script d'ingestion de pistes audio.
Permet d'ajouter des fichiers audio à la base de données avec leurs empreintes.
"""

import argparse
import sys
from pathlib import Path

# Ajout du chemin racine au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import (
    load_audio_file,
    compute_spectrogram,
    extract_peaks,
    generate_fingerprint,
)
from storage import (
    Database,
    add_track,
    add_fingerprints,
    get_track_by_path,
    count_tracks,
    count_fingerprints,
)


def ingest_file(db: Database, file_path: str, title: str = None, artist: str = None):
    """
    Ingeste un fichier audio dans la base de données.
    
    Args:
        db: Instance de Database
        file_path: Chemin vers le fichier audio
        title: Titre de la piste (optionnel, par défaut le nom du fichier)
        artist: Artiste (optionnel)
    """
    file_path = str(Path(file_path).resolve())
    
    # Vérifier si le fichier existe déjà
    existing = get_track_by_path(db, file_path)
    if existing:
        print(f"⚠️  Le fichier existe déjà dans la BDD (ID: {existing['id']})")
        return
    
    # Définir le titre par défaut
    if title is None:
        title = Path(file_path).stem
    
    print(f"🎵 Traitement: {title}")
    
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
    fingerprints = generate_fingerprint(peaks)
    print(f"   │  Nombre d'empreintes: {len(fingerprints)}")
    
    # 5. Ajouter à la base de données
    print("   ├─ Insertion en base de données...")
    track_id = add_track(
        db,
        title=title,
        file_path=file_path,
        artist=artist,
        duration=len(signal) / sr
    )
    
    added_count = add_fingerprints(db, track_id, fingerprints)
    print(f"   │  Piste ID: {track_id}, Empreintes ajoutées: {added_count}")
    
    print(f"✅ Terminé: {title}")


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
    
    args = parser.parse_args()
    
    # Initialiser la base de données
    print(f"📦 Connexion à la base de données: {args.db}")
    db = Database(args.db)
    
    initial_tracks = count_tracks(db)
    initial_fingerprints = count_fingerprints(db)
    print(f"   État initial: {initial_tracks} pistes, {initial_fingerprints} empreintes\n")
    
    # Traiter chaque fichier
    for file_path in args.files:
        if not Path(file_path).exists():
            print(f"❌ Fichier non trouvé: {file_path}")
            continue
        
        try:
            ingest_file(db, file_path, title=args.title, artist=args.artist)
            print()
        except Exception as e:
            print(f"❌ Erreur lors du traitement de {file_path}: {e}\n")
            continue
    
    # Résumé final
    final_tracks = count_tracks(db)
    final_fingerprints = count_fingerprints(db)
    
    print("=" * 50)
    print("📊 Résumé:")
    print(f"   Pistes ajoutées: {final_tracks - initial_tracks}")
    print(f"   Empreintes ajoutées: {final_fingerprints - initial_fingerprints}")
    print(f"   Total: {final_tracks} pistes, {final_fingerprints} empreintes")


if __name__ == "__main__":
    main()
