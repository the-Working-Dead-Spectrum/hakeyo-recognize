"""
Matcher - Orchestrateur de la reconnaissance musicale.
Implémente le pipeline complet de matching (QWEN.md Section 4, Étape 5).
"""

from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
import time

from storage.database import Database
from matching.histogram import build_offset_histogram, find_best_match


@dataclass
class MatchResult:
    """Résultat d'une tentative de reconnaissance."""
    match: bool
    track_id: Optional[int] = None
    title: Optional[str] = None
    artist: Optional[str] = None
    confidence: float = 0.0
    processing_time_ms: float = 0.0
    source: str = "local"
    top_candidates: Optional[Dict[int, int]] = None  # {track_id: alignments}
    aligned_hash_count: Optional[int] = None
    best_delta_offset: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Sérialisation pour API ou CLI."""
        return {
            "match": self.match,
            "track_id": self.track_id,
            "title": self.title,
            "artist": self.artist,
            "confidence": self.confidence,
            "processing_time_ms": self.processing_time_ms,
            "source": self.source,
            "top_candidates": self.top_candidates,
            "aligned_hash_count": self.aligned_hash_count,
            "best_delta_offset": self.best_delta_offset,
        }


class Matcher:
    """
    Moteur de matching avec vérification d'alignement temporel.
    
    Pipeline:
    1. Générer les fingerprints de l'extrait (capture)
    2. Rechercher tous les matches en BDD par hash (WHERE hash = ANY(...))
    3. Construire l'histogramme des delta_offsets par track
    4. Identifier le pic et calculer le score de confiance
    5. Appliquer les seuils et retourner le résultat
    
    Conformité QWEN.md Section 4:
    - Utilise l'index de frame (pas de binning en secondes)
    - Tolérance ±1 frame pour le bruit de quantification
    - Seuil absolu (min 5 hashes) + relatif (5% du total)
    - Top-3 candidats pour diagnostic interne
    """
    
    def __init__(
        self,
        db: Database,
        hop_length: int = 512,
        sr: int = 11025,
        tolerance_frames: int = 1,
        min_absolute_matches: int = 5,
        min_relative_ratio: float = 0.05,
        verbose: bool = False,
    ):
        """
        Initialise le matcher.
        
        Args:
            db: Instance de Database pour les requêtes SQL
            hop_length: Hop length du STFT utilisé pour la génération des fingerprints
            sr: Sample rate utilisé (défaut: 11025 Hz)
            tolerance_frames: Tolérance de ±N frames pour l'histogramme
            min_absolute_matches: Seuil absolu minimum de hashes alignés
            min_relative_ratio: Seuil relatif minimum (fraction du total)
        """
        self.db = db
        self.hop_length = hop_length
        self.sr = sr
        self.tolerance_frames = tolerance_frames
        self.min_absolute_matches = min_absolute_matches
        self.min_relative_ratio = min_relative_ratio
        self.verbose = verbose
    
    def recognize(
        self,
        capture_fingerprints: List[Tuple[str, float]],  # (hash, offset)
    ) -> MatchResult:
        """
        Reconnaît un extrait à partir de ses fingerprints.
        
        Args:
            capture_fingerprints: Liste des (hash, offset) générés depuis l'extrait audio
        
        Returns:
            MatchResult avec les détails du match ou NO MATCH
        
        Note technique:
            - Requête SQL unique batchée: SELECT ... WHERE hash = ANY(%s)
            - Traitement de l'histogramme en mémoire (numpy)
            - Conforme YAGNI: pas d'optimisation prématurée
        """
        start_time = time.perf_counter()
        
        if not capture_fingerprints:
            return MatchResult(
                match=False,
                confidence=0.0,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )
        
        # Étape 1: Extraire la liste des hashes pour la requête SQL
        capture_hashes = [h for h, _ in capture_fingerprints]
        capture_offsets = {h: off for h, off in capture_fingerprints}  # Lookup rapide
        
        # Étape 2: Requête SQL batchée (WHERE hash = ANY(...))
        # Retourne: [(hash, track_id, offset_db), ...]
        db_matches = self.db.find_matches_by_hashes(capture_hashes)
        
        if self.verbose:
            print(f"[MATCHING] {len(db_matches)} correspondances brutes trouvées")
        
        if not db_matches:
            return MatchResult(
                match=False,
                confidence=0.0,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )
        
        # Étape 3: Préparer les données pour l'histogramme
        # Format: [(hash, track_id, offset_db, offset_capture), ...]
        hash_matches: List[Tuple[str, int, float, float]] = []
        for hash_val, track_id, offset_db in db_matches:
            offset_capture = capture_offsets.get(hash_val)
            if offset_capture is not None:
                hash_matches.append((hash_val, track_id, offset_db, offset_capture))
        
        # Étape 4: Construire l'histogramme des delta_offsets
        histogram = build_offset_histogram(
            hash_matches,
            hop_length=self.hop_length,
            sr=self.sr,
            tolerance_frames=self.tolerance_frames,
        )
        
        # Étape 5: Trouver le meilleur match avec vérification des seuils
        total_hashes = len(capture_fingerprints)
        best_track_id, best_delta, confidence, top_candidates = find_best_match(
            histogram,
            total_hashes,
            min_absolute_matches=self.min_absolute_matches,
            min_relative_ratio=self.min_relative_ratio,
        )
        
        # Étape 6: Récupérer les métadonnées si match trouvé
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        
        if best_track_id is None:
            # Aucun match ne passe les seuils
            return MatchResult(
                match=False,
                confidence=confidence,
                processing_time_ms=processing_time_ms,
                top_candidates=top_candidates,
                aligned_hash_count=None,
                best_delta_offset=None,
            )
        
        # Récupérer les infos du track
        track_info = self.db.get_track_by_id(best_track_id)
        
        return MatchResult(
            match=True,
            track_id=best_track_id,
            title=track_info.get("title") if track_info else None,
            artist=track_info.get("artist") if track_info else None,
            confidence=confidence,
            processing_time_ms=processing_time_ms,
            top_candidates=top_candidates,
            aligned_hash_count=best_delta if best_delta is not None else 0,
            best_delta_offset=best_delta,
        )
