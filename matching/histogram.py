"""
Histogramme des offsets et recherche du meilleur match.
Implémente la vérification d'alignement temporel (QWEN.md Section 4, Étape 5).
"""

from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import numpy as np


def build_offset_histogram(
    hash_matches: List[Tuple[str, int, float, float]],  # (hash, track_id, offset_db, offset_capture)
    hop_length: int = 512,
    sr: int = 11025,
    tolerance_frames: int = 1,
) -> Dict[int, Dict[int, int]]:
    """
    Construit un histogramme des delta_offsets pour chaque track candidat.
    
    Au lieu de binner en secondes, on utilise l'index de frame entier pour une précision maximale.
    Tolérance de ±`tolerance_frames` pour absorber le bruit de quantification.
    
    Args:
        hash_matches: Liste des correspondances (hash, track_id, offset_db, offset_capture)
            Chaque hash de la capture qui trouve un match en BDD génère une entrée.
        hop_length: Hop length utilisé pour le STFT (défaut: 512)
        sr: Sample rate utilisé (défaut: 11025 Hz)
        tolerance_frames: Tolérance de ±N frames pour le comptage (défaut: 1)
    
    Returns:
        Dict {track_id: {delta_frame_index: count}}
        Ex: {123: {45: 12, 46: 8}, 456: {102: 5}}
    
    Note technique:
        - offset est stocké en secondes dans la BDD
        - On le convertit en index de frame: frame_idx = round(offset * sr / hop_length)
        - delta_frame = frame_idx_db - frame_idx_capture
        - Tolérance ±1 frame appliquée lors du comptage (on incrémente delta et delta±1)
    """
    if not hash_matches:
        return {}
    
    histogram: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    
    for _, track_id, offset_db, offset_capture in hash_matches:
        # Conversion en indices de frame (arrondi pour éviter les erreurs de flottant)
        frame_idx_db = round(offset_db * sr / hop_length)
        frame_idx_capture = round(offset_capture * sr / hop_length)
        
        delta_frame = frame_idx_db - frame_idx_capture
        
        # Appliquer la tolérance: incrémenter delta et ses voisins immédiats
        for delta in range(delta_frame - tolerance_frames, delta_frame + tolerance_frames + 1):
            histogram[track_id][delta] += 1
    
    # Convertir les defaultdict en dict normaux pour la sérialisation
    return {tid: dict(deltas) for tid, deltas in histogram.items()}


def find_best_match(
    histogram: Dict[int, Dict[int, int]],
    total_capture_hashes: int,
    min_absolute_matches: int = 5,
    min_relative_ratio: float = 0.05,
) -> Tuple[Optional[int], Optional[int], float, Dict[int, int]]:
    """
    Trouve le meilleur match à partir de l'histogramme des deltas.
    
    Critères de décision (QWEN.md Section 4, Étape 6):
    1. Plancher absolu: minimum `min_absolute_matches` hashes alignés
    2. Seuil relatif: le pic doit représenter au moins `min_relative_ratio` 
       du total des hashes de la capture
    3. Retourne le top-1, mais calcule le top-3 pour diagnostic
    
    Args:
        histogram: Dict {track_id: {delta_frame: count}}
        total_capture_hashes: Nombre total de fingerprints générés depuis la capture
        min_absolute_matches: Seuil absolu minimum (défaut: 5)
        min_relative_ratio: Seuil relatif minimum (défaut: 0.05 = 5%)
    
    Returns:
        Tuple (best_track_id, best_delta_offset, confidence_score, top_candidates)
        - best_track_id: None si aucun match ne passe les seuils
        - best_delta_offset: Delta en frames du pic dominant (None si pas de match)
        - confidence_score: Entre 0 et 1 (pic_max / total_capture_hashes)
        - top_candidates: Dict {track_id: max_alignments} trié par score
    
    Example:
        >>> histogram = {123: {45: 50, 46: 10}, 456: {102: 3}}
        >>> find_best_match(histogram, total_capture_hashes=100)
        (123, 45, 0.50, {123: 50, 456: 3})
    """
    if not histogram:
        return None, None, 0.0, {}
    
    # Calculer le score maximum pour chaque track (meilleur delta)
    track_scores: Dict[int, int] = {}
    track_best_deltas: Dict[int, int] = {}
    for track_id, deltas in histogram.items():
        if deltas:
            best_delta = max(deltas, key=deltas.get)
            track_scores[track_id] = deltas[best_delta]
            track_best_deltas[track_id] = best_delta
    
    if not track_scores:
        return None, None, 0.0, {}
    
    # Trier par score décroissant (top-3 pour diagnostic)
    sorted_tracks = sorted(track_scores.items(), key=lambda x: x[1], reverse=True)
    top_candidates = dict(sorted_tracks[:3])
    
    best_track_id = sorted_tracks[0][0]
    best_score = sorted_tracks[0][1]
    best_delta = track_best_deltas.get(best_track_id)
    
    # Vérifier les seuils
    absolute_threshold = min_absolute_matches
    relative_threshold = int(total_capture_hashes * min_relative_ratio)
    effective_threshold = max(absolute_threshold, relative_threshold)
    
    if best_score < effective_threshold:
        # Aucun match ne passe les seuils
        return None, None, 0.0, top_candidates
    
    # Calculer la confiance normalisée
    confidence = best_score / total_capture_hashes if total_capture_hashes > 0 else 0.0
    
    return best_track_id, best_delta, confidence, top_candidates
