#!/usr/bin/env python3
"""
Script CLI de reconnaissance musicale (Story E2-04).

Utilisation :
    python scripts/recognize.py <fichier_audio> [--db <chemin_bdd>] [--json] [--verbose]

Exemples :
    python scripts/recognize.py extrait.mp3
    python scripts/recognize.py test.wav --db lmre.db --json
    python scripts/recognize.py sample.ogg --verbose

Ce script :
1. Valide le fichier audio (existence, format, durée minimale)
2. Génère les fingerprints de l'extrait
3. Interroge la base de données pour trouver des candidats
4. Construit l'histogramme des deltas et calcule le score de confiance
5. Retourne le meilleur match si confidence >= CONFIDENCE_THRESHOLD
6. Simule le fallback ARCCloud si aucun match local n'est trouvé

Conforme QWEN.md :
- Section 4 : Algorithme de matching avec alignement temporel
- Section 6 : Contrat de sortie JSON
- Section 7.2 : Validation OWASP des entrées (réutilisable en API)
- Section 0 : Gestion explicite des cas limites
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

# Imports du projet
from storage import (
    Database,
    find_matches_by_hashes,
    get_track_by_id,
    ValidationError,
    validate_audio_for_recognition,
)
from engine import (
    load_audio_file,
    extract_peaks,
    generate_fingerprint,
)
from matching import (
    build_offset_histogram,
    find_best_match,
    MatchResult,
)

# Configuration - seuil de confiance pour le matching
# Valeur par défaut: 0.15 (à calibrer empiriquement selon QWEN.md Section 4.1)
CONFIDENCE_THRESHOLD = 0.05  # 5% comme décidé dans les paramètres de matching


def recognize_audio(
    db: Database,
    audio_path: str,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Reconnaît un extrait audio en le comparant à la base de données.
    
    Args:
        db: Instance de Database
        audio_path: Chemin vers le fichier audio à reconnaître
        verbose: Si True, affiche des logs détaillés
        
    Returns:
        Dictionnaire conforme au contrat d'API (QWEN.md Section 6):
        {
            "match": bool,
            "track_id": int ou None,
            "title": str ou None,
            "artist": str ou None,
            "confidence": float (0-1),
            "processing_time_ms": int,
            "source": "local" ou "arccloud",
            "top_candidates": list (pour diagnostic, top-3)
        }
    """
    start_time = time.time()
    
    # 1. Validation du fichier audio
    if verbose:
        print(f"[VALIDATION] Vérification du fichier: {audio_path}")
    
    try:
        validated_path, metadata = validate_audio_for_recognition(audio_path)
    except ValidationError as e:
        return {
            "match": False,
            "error": str(e),
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "source": "none"
        }
    
    if verbose:
        print(f"[INFO] Fichier valide: {metadata['duration']:.2f}s, {metadata['sample_rate']}Hz")
    
    # 2. Chargement et traitement audio
    if verbose:
        print("[AUDIO] Chargement du fichier...")
    
    try:
        y, sr = load_audio_file(str(validated_path))
    except Exception as e:
        return {
            "match": False,
            "error": f"Erreur de chargement audio: {str(e)}",
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "source": "none"
        }
    
    # 3. Extraction des pics
    if verbose:
        print("[PEAKS] Extraction des pics spectraux...")
    
    try:
        peaks = extract_peaks(y, sr)
        if len(peaks) == 0:
            return {
                "match": False,
                "error": "Aucun pic spectral détecté (silence ou signal trop faible)",
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "source": "none"
            }
    except Exception as e:
        return {
            "match": False,
            "error": f"Erreur d'extraction des pics: {str(e)}",
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "source": "none"
        }
    
    if verbose:
        print(f"[PEAKS] {len(peaks)} pics extraits")
    
    # 4. Génération des fingerprints
    if verbose:
        print("[FINGERPRINT] Génération des empreintes...")
    
    try:
        fingerprints = generate_fingerprint(peaks, sr)
        if len(fingerprints) == 0:
            return {
                "match": False,
                "error": "Aucune empreinte générée (pics insuffisants)",
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "source": "none"
            }
    except Exception as e:
        return {
            "match": False,
            "error": f"Erreur de génération des fingerprints: {str(e)}",
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "source": "none"
        }
    
    if verbose:
        print(f"[FINGERPRINT] {len(fingerprints)} empreintes générées")
    
    # 5. Recherche des matches en BDD
    if verbose:
        print("[MATCHING] Recherche dans la base de données...")
    
    query_hashes = [fp[0] for fp in fingerprints]  # Liste des hash strings
    matches_raw = find_matches_by_hashes(db, query_hashes)
    
    if verbose:
        print(f"[MATCHING] {len(matches_raw)} correspondances brutes trouvées")
    
    if not matches_raw:
        # Aucun candidat en BDD
        result = {
            "match": False,
            "confidence": 0.0,
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "source": "local",
            "top_candidates": [],
            "message": "Aucun candidat trouvé dans la base de données"
        }
        
        # Simulation du fallback ARCCloud
        print("\n[FALLBACK] Aucun match local trouvé. Appel simulé à ARCCloud...")
        print("[FALLBACK] Dans une implémentation réelle, l'API ARCCloud serait invoquée ici.")
        result["source"] = "arccloud_simulated"
        result["arccloud_status"] = "no_call_made_simulation_only"
        
        return result
    
    # 6. Construction de l'histogramme et recherche du meilleur match
    if verbose:
        print("[HISTOGRAM] Construction de l'histogramme des offsets...")
    
    # Convertir les fingerprints de la requête en dict {hash: offset_frame}
    # Note: generate_fingerprints retourne (hash_str, offset_sec), on doit convertir en frames
    from engine.config import SAMPLE_RATE, HOP_LENGTH
    query_fingerprints_dict = {
        fp[0]: int(fp[1] * SAMPLE_RATE / HOP_LENGTH)  # offset_sec -> offset_frame
        for fp in fingerprints
    }
    
    histogram_result = build_offset_histogram(
        matches_raw=matches_raw,
        query_fingerprints=query_fingerprints_dict
    )
    
    if verbose:
        print(f"[HISTOGRAM] {len(histogram_result['candidates'])} candidats analysés")
    
    # 7. Sélection du meilleur match avec seuil de confiance
    best_match = find_best_match(
        histogram_result=histogram_result,
        total_query_hashes=len(fingerprints),
        min_absolute_matches=5,  # Plancher absolu (QWEN.md Section 4.1)
        min_relative_ratio=CONFIDENCE_THRESHOLD  # Seuil relatif (5% par défaut)
    )
    
    processing_time_ms = int((time.time() - start_time) * 1000)
    
    # 8. Formatage du résultat
    if best_match is None or not best_match.is_match:
        # Aucun match ne dépasse les seuils
        result = {
            "match": False,
            "confidence": best_match.confidence if best_match else 0.0,
            "processing_time_ms": processing_time_ms,
            "source": "local",
            "top_candidates": [],
            "message": f"Confidence insuffisante: {best_match.confidence:.3f} < {CONFIDENCE_THRESHOLD}" if best_match else "Aucun candidat"
        }
        
        # Simulation du fallback ARCCloud
        print(f"\n[FALLBACK] Confidence trop faible ({result['confidence']:.3f}). Appel simulé à ARCCloud...")
        print("[FALLBACK] Dans une implémentation réelle, l'API ARCCloud serait invoquée ici.")
        result["source"] = "arccloud_simulated"
        result["arccloud_status"] = "no_call_made_simulation_only"
        
        # Inclure le top-3 pour diagnostic même en cas d'échec
        if best_match and hasattr(best_match, 'top_candidates'):
            result["top_candidates"] = [
                {"track_id": c.track_id, "confidence": c.confidence, "aligned_hashes": c.aligned_hash_count}
                for c in best_match.top_candidates[:3]
            ]
        
        return result
    
    # Match trouvé !
    track_info = get_track_by_id(db, best_match.track_id)
    
    result = {
        "match": True,
        "track_id": best_match.track_id,
        "title": track_info["title"] if track_info else "Inconnu",
        "artist": track_info.get("artist", "Inconnu"),
        "confidence": round(best_match.confidence, 4),
        "processing_time_ms": processing_time_ms,
        "source": "local",
        "aligned_hashes": best_match.aligned_hash_count,
        "delta_offset_frames": best_match.best_delta_offset,
        "top_candidates": [
            {"track_id": c.track_id, "confidence": c.confidence, "aligned_hashes": c.aligned_hash_count}
            for c in best_match.top_candidates[:3]
        ] if hasattr(best_match, 'top_candidates') and best_match.top_candidates else []
    }
    
    if verbose:
        print(f"\n[MATCH] {result['title']} - {result['artist']}")
        print(f"[MATCH] Confiance: {result['confidence']:.2%}")
        print(f"[MATCH] Hashes alignés: {result['aligned_hashes']}")
        print(f"[MATCH] Temps de traitement: {result['processing_time_ms']}ms")
    
    return result


def format_output(result: Dict[str, Any], as_json: bool = False) -> str:
    """
    Formate le résultat pour affichage.
    
    Args:
        result: Dictionnaire de résultat
        as_json: Si True, retourne un JSON brut
        
    Returns:
        Chaîne formatée pour affichage
    """
    if as_json:
        return json.dumps(result, indent=2, ensure_ascii=False)
    
    # Format texte lisible
    lines = []
    
    if result.get("match"):
        lines.append("=" * 60)
        lines.append("✅ MATCH TROUVÉ")
        lines.append("=" * 60)
        lines.append(f"Titre:       {result.get('title', 'N/A')}")
        lines.append(f"Artiste:     {result.get('artist', 'N/A')}")
        lines.append(f"ID Piste:    {result.get('track_id', 'N/A')}")
        lines.append(f"Confiance:   {result.get('confidence', 0):.2%}")
        lines.append(f"Hashes alignés: {result.get('aligned_hashes', 0)}")
        lines.append(f"Source:      {result.get('source', 'N/A')}")
        lines.append(f"Temps:       {result.get('processing_time_ms', 0)}ms")
        
        if result.get("top_candidates"):
            lines.append("\nTop candidats (diagnostic):")
            for i, cand in enumerate(result["top_candidates"], 1):
                lines.append(f"  {i}. Track #{cand['track_id']} - {cand['confidence']:.2%} ({cand['aligned_hashes']} hashes)")
    else:
        lines.append("=" * 60)
        lines.append("❌ AUCUN MATCH")
        lines.append("=" * 60)
        
        if result.get("error"):
            lines.append(f"Erreur:      {result['error']}")
        elif result.get("message"):
            lines.append(f"Raison:      {result['message']}")
        
        lines.append(f"Confiance:   {result.get('confidence', 0):.2%}")
        lines.append(f"Source:      {result.get('source', 'N/A')}")
        lines.append(f"Temps:       {result.get('processing_time_ms', 0)}ms")
        
        if result.get("arccloud_status"):
            lines.append(f"\n[FALLBACK] {result['arccloud_status']}")
    
    return "\n".join(lines)


def main():
    """Point d'entrée principal du script CLI."""
    parser = argparse.ArgumentParser(
        description="Reconnaissance musicale locale (LMRE V0.2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  %(prog)s extrait.mp3
  %(prog)s test.wav --db lmre.db --json
  %(prog)s sample.ogg --verbose
        """
    )
    
    parser.add_argument(
        "audio_file",
        help="Chemin vers le fichier audio à reconnaître (5-15s recommandé)"
    )
    
    parser.add_argument(
        "--db",
        default="lmre.db",
        help="Chemin vers la base de données SQLite (défaut: lmre.db)"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Afficher le résultat au format JSON (pour intégration)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Mode verbeux avec logs détaillés"
    )
    
    args = parser.parse_args()
    
    # Initialisation de la base de données
    db = Database(args.db)
    
    # Vérification rapide que la BDD n'est pas vide
    from storage import count_tracks, count_fingerprints
    track_count = count_tracks(db)
    fingerprint_count = count_fingerprints(db)
    
    if args.verbose:
        print(f"[INFO] Base de données: {args.db}")
        print(f"[INFO] {track_count} pistes, {fingerprint_count} empreintes")
    
    if track_count == 0:
        result = {
            "match": False,
            "error": "Base de données vide. Ingérez d'abord des pistes avec: python scripts/ingest.py <fichiers>",
            "processing_time_ms": 0,
            "source": "none"
        }
        print(format_output(result, args.json))
        sys.exit(1)
    
    # Lancement de la reconnaissance
    result = recognize_audio(db, args.audio_file, args.verbose)
    
    # Affichage du résultat
    print(format_output(result, args.json))
    
    # Code de sortie :
    # 0 = succès (même sans match, c'est un résultat métier valide)
    # 1 = erreur technique (fichier inexistant, DB vide, etc.)
    if result.get("error") and "Base de données vide" in result.get("error", ""):
        sys.exit(1)
    elif result.get("error") and "Validation" in result.get("error", ""):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
