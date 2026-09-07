"""
Tests du module de matching (Story E2-02).
Vérifie l'alignement temporel et la détection des faux positifs.
"""

import pytest
from matching.histogram import build_offset_histogram, find_best_match
from matching.matcher import Matcher, MatchResult


class TestBuildOffsetHistogram:
    """Tests de la construction d'histogramme des delta_offsets."""
    
    def test_histogram_simple_match(self):
        """Un seul hash matché entre capture et DB."""
        # (hash, track_id, offset_db, offset_capture)
        matches = [("abc123", 1, 2.5, 1.0)]
        
        histogram = build_offset_histogram(
            matches,
            hop_length=512,
            sr=11025,
            tolerance_frames=1,
        )
        
        assert 1 in histogram  # track_id présent
        # delta_frame ≈ (2.5 - 1.0) * 11025 / 512 ≈ 32 frames
        assert len(histogram[1]) > 0  # Au moins un delta enregistré
    
    def test_histogram_multiple_hashes_same_track(self):
        """Plusieurs hashes alignés sur le même track → pic net."""
        # Simule 10 hashes tous alignés avec le même delta
        matches = [
            (f"hash{i}", 1, 2.0 + i * 0.1, 1.0 + i * 0.1)
            for i in range(10)
        ]
        
        histogram = build_offset_histogram(matches, hop_length=512, sr=11025)
        
        # Tous les hashes devraient avoir le même delta_frame ≈ 1.0 * 11025/512 ≈ 21
        assert 1 in histogram
        # Le pic devrait être à ~21 (avec tolérance ±1)
        deltas = histogram[1]
        max_count = max(deltas.values())
        assert max_count >= 10  # Tous les hashes contribuent au pic
    
    def test_histogram_different_tracks(self):
        """Hashes répartis sur plusieurs tracks → pas de pic clair."""
        # Track 1: 3 hashes alignés
        # Track 2: 2 hashes alignés (moins que track 1)
        matches = [
            ("h1", 1, 2.0, 1.0),
            ("h2", 1, 2.1, 1.1),
            ("h3", 1, 2.2, 1.2),
            ("h4", 2, 3.0, 1.0),  # Delta différent
            ("h5", 2, 3.5, 1.5),  # Delta différent
        ]
        
        histogram = build_offset_histogram(matches, hop_length=512, sr=11025)
        
        assert 1 in histogram
        assert 2 in histogram
        # Track 1 devrait avoir un meilleur score (plus de matches alignés)
    
    def test_histogram_empty_input(self):
        """Aucun match → histogramme vide."""
        histogram = build_offset_histogram([], hop_length=512, sr=11025)
        assert histogram == {}
    
    def test_histogram_tolerance_applied(self):
        """La tolérance ±1 frame est bien appliquée."""
        matches = [("abc", 1, 2.0, 1.0)]
        
        histogram = build_offset_histogram(
            matches,
            hop_length=512,
            sr=11025,
            tolerance_frames=1,
        )
        
        # Avec tolérance=1, on incrémente delta et delta±1 → 3 bins consécutifs
        # delta_frame = round((2.0 - 1.0) * 11025 / 512) = round(21.48) = 21
        # Les bins devraient être 20, 21, 22
        assert len(histogram[1]) == 3  # Exactement 3 bins
        # Vérifie que les valeurs sont consécutives
        bins = sorted(histogram[1].keys())
        assert bins[1] - bins[0] == 1
        assert bins[2] - bins[1] == 1
        # Chaque bin a un count de 1
        for count in histogram[1].values():
            assert count == 1


class TestFindBestMatch:
    """Tests de la détection du meilleur match."""
    
    def test_clear_winner(self):
        """Un track domine nettement → match confirmé."""
        histogram = {
            123: {45: 50},  # 50 hashes alignés
            456: {102: 3},  # Seulement 3
        }
        
        track_id, _, confidence, candidates = find_best_match(
            histogram,
            total_capture_hashes=100,
            min_absolute_matches=5,
            min_relative_ratio=0.05,
        )
        
        assert track_id == 123
        assert confidence == 0.50  # 50/100
        assert 123 in candidates
        assert 456 in candidates
    
    def test_no_match_below_threshold(self):
        """Aucun track ne passe les seuils → NO MATCH."""
        histogram = {
            123: {45: 2},  # Seulement 2 hashes (< 5 absolu)
            456: {102: 1},
        }
        
        track_id, _, confidence, candidates = find_best_match(
            histogram,
            total_capture_hashes=100,
            min_absolute_matches=5,
            min_relative_ratio=0.05,
        )
        
        assert track_id is None  # Pas de match
        assert confidence == 0.0
    
    def test_relative_threshold_blocks_weak_match(self):
        """Seuil relatif bloque un match statistiquement faible."""
        histogram = {
            123: {45: 4},  # 4 hashes = 4% de 100 (< 5% relatif)
        }
        
        track_id, _, confidence, candidates = find_best_match(
            histogram,
            total_capture_hashes=100,
            min_absolute_matches=5,
            min_relative_ratio=0.05,
        )
        
        assert track_id is None  # Bloqué par le seuil relatif
    
    def test_top3_candidates_returned(self):
        """Le top-3 est retourné pour diagnostic."""
        histogram = {
            1: {10: 50},
            2: {20: 30},
            3: {30: 20},
            4: {40: 10},  # 4ème track, ne sera pas dans top-3
        }
        
        _, _, _, candidates = find_best_match(histogram, total_capture_hashes=100)
        
        assert len(candidates) <= 3
        assert 1 in candidates  # Meilleur
        assert 2 in candidates
        assert 3 in candidates
        assert 4 not in candidates  # Exclu du top-3
    
    def test_empty_histogram(self):
        """Histogramme vide → pas de match."""
        track_id, _, confidence, candidates = find_best_match({}, total_capture_hashes=100)
        
        assert track_id is None
        assert confidence == 0.0
        assert candidates == {}


class TestMatcherIntegration:
    """Tests d'intégration du Matcher complet."""
    
    def test_matcher_no_fingerprints(self):
        """Matcher avec fingerprints vides → retour rapide."""
        # Mock DB
        class MockDB:
            def find_matches_by_hashes(self, hashes): return []
            def get_track_by_id(self, track_id): return None
        
        matcher = Matcher(MockDB())
        result = matcher.recognize([])
        
        assert result.match is False
        assert result.confidence == 0.0
        assert result.processing_time_ms >= 0
    
    def test_matcher_no_db_matches(self):
        """Aucun match en BDD → NO MATCH."""
        class MockDB:
            def find_matches_by_hashes(self, hashes): return []
            def get_track_by_id(self, track_id): return None
        
        matcher = Matcher(MockDB())
        fingerprints = [("abc123", 0.5), ("def456", 1.0)]
        result = matcher.recognize(fingerprints)
        
        assert result.match is False
        assert result.confidence == 0.0
    
    def test_matcher_successful_recognition(self):
        """Reconnaissance réussie avec bon alignement."""
        # Mock DB qui retourne des matches bien alignés
        class MockDB:
            def find_matches_by_hashes(self, hashes):
                # Simule 10 hashes tous alignés sur le track 1
                return [(h, 1, 2.0) for h in hashes]
            
            def get_track_by_id(self, track_id):
                return {"id": 1, "title": "Test Song", "artist": "Test Artist"}
        
        matcher = Matcher(MockDB(), min_absolute_matches=5, min_relative_ratio=0.05)
        # Fingerprints tous alignés avec offset_db=2.0
        fingerprints = [(f"hash{i}", 1.0) for i in range(10)]
        
        result = matcher.recognize(fingerprints)
        
        assert result.match is True
        assert result.track_id == 1
        assert result.title == "Test Song"
        assert result.artist == "Test Artist"
        assert result.confidence > 0.0
        assert result.source == "local"
    
    def test_matcher_to_dict(self):
        """Sérialisation du résultat."""
        result = MatchResult(
            match=True,
            track_id=123,
            title="Song Title",
            artist="Artist Name",
            confidence=0.85,
            processing_time_ms=42.5,
            source="local",
        )
        
        data = result.to_dict()
        
        assert data["match"] is True
        assert data["track_id"] == 123
        assert data["title"] == "Song Title"
        assert data["artist"] == "Artist Name"
        assert data["confidence"] == 0.85
        assert data["processing_time_ms"] == 42.5
        assert data["source"] == "local"
