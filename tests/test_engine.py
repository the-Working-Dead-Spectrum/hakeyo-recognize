"""
Tests pour le moteur audio (E1-01, E1-02, E1-03).
Conforme à la posture senior : tests qui prouvent le comportement correct.
"""

import pytest
import numpy as np
import os
import tempfile
from pathlib import Path

# Import des modules à tester
from engine.audio_loader import load_audio_file, AudioTooShortError, CorruptedAudioFileError
from engine.spectrogram import compute_spectrogram
from engine.peak_picking import extract_peaks
from engine.fingerprint import generate_fingerprint
from engine.config import AudioConfig


class TestAudioLoader:
    """Tests pour le chargement audio (Story E1-01)."""
    
    def test_load_audio_file_returns_tuple(self):
        """Vérifie que la fonction retourne un tuple (signal, sr)."""
        # On crée un signal synthétique de durée suffisante (>3s)
        sample_rate = 44100
        duration = 4.0  # secondes (> min_duration de 3s)
        t = np.linspace(0, duration, int(sample_rate * duration))
        signal = np.sin(2 * np.pi * 440 * t)  # La à 440 Hz
        
        # Sauvegarder dans un fichier temporaire
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            import soundfile as sf
            sf.write(f.name, signal, sample_rate)
            temp_path = f.name
        
        try:
            loaded_signal, sr = load_audio_file(temp_path)
            
            assert isinstance(loaded_signal, np.ndarray), "Le signal doit être un numpy array"
            assert isinstance(sr, int), "Le sample rate doit être un entier"
            assert sr == 11025, f"Sample rate attendu: 11025 (config par défaut), obtenu: {sr}"
            assert len(loaded_signal) > 0, "Le signal ne doit pas être vide"
        finally:
            os.unlink(temp_path)
    
    def test_load_audio_file_mono(self):
        """Vérifie que le signal est converti en mono."""
        sample_rate = 44100
        duration = 4.0  # > 3s requis
        t = np.linspace(0, duration, int(sample_rate * duration))
        signal = np.sin(2 * np.pi * 440 * t)
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            import soundfile as sf
            sf.write(f.name, signal, sample_rate)
            temp_path = f.name
        
        try:
            loaded_signal, _ = load_audio_file(temp_path)
            assert loaded_signal.ndim == 1, "Le signal doit être mono (1D)"
        finally:
            os.unlink(temp_path)
    
    def test_load_audio_file_too_short_raises_error(self):
        """Vérifie qu'un fichier < 3s lève une exception (cas limite)."""
        sample_rate = 44100
        duration = 1.0  # < 3s requis
        t = np.linspace(0, duration, int(sample_rate * duration))
        signal = np.sin(2 * np.pi * 440 * t)
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            import soundfile as sf
            sf.write(f.name, signal, sample_rate)
            temp_path = f.name
        
        try:
            with pytest.raises(AudioTooShortError):
                load_audio_file(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_load_audio_file_custom_config(self):
        """Vérifie l'utilisation d'une configuration personnalisée."""
        sample_rate = 44100
        duration = 2.0  # 2s
        t = np.linspace(0, duration, int(sample_rate * duration))
        signal = np.sin(2 * np.pi * 440 * t)
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            import soundfile as sf
            sf.write(f.name, signal, sample_rate)
            temp_path = f.name
        
        try:
            # Config avec min_duration=1s (accepte 2s)
            config = AudioConfig(sample_rate=sample_rate)
            loaded_signal, sr = load_audio_file(temp_path, config=config, min_duration=1.0)
            
            assert len(loaded_signal) > 0
            assert sr == sample_rate
        finally:
            os.unlink(temp_path)


class TestSpectrogram:
    """Tests pour le calcul du spectrogramme (Story E1-01)."""
    
    def test_compute_spectrogram_returns_tuple(self):
        """Vérifie que la fonction retourne un tuple (S, times, freqs)."""
        # Créer un signal de test
        sample_rate = 44100
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        signal = np.sin(2 * np.pi * 440 * t)
        
        S, times, freqs = compute_spectrogram(signal, sr=sample_rate)
        
        assert isinstance(S, np.ndarray), "Le spectrogramme doit être un numpy array"
        assert isinstance(times, np.ndarray), "Les temps doivent être un numpy array"
        assert isinstance(freqs, np.ndarray), "Les fréquences doivent être un numpy array"
        assert S.ndim == 2, "Le spectrogramme doit être 2D (freq x temps)"
        assert len(times) > 0, "L'axe des temps ne doit pas être vide"
        assert len(freqs) > 0, "L'axe des fréquences ne doit pas être vide"
    
    def test_spectrogram_shape(self):
        """Vérifie les dimensions du spectrogramme."""
        sample_rate = 44100
        n_mels = 128
        signal = np.random.randn(sample_rate)  # 1 seconde
        
        S, times, freqs = compute_spectrogram(signal, sr=sample_rate, n_mels=n_mels)
        
        assert S.shape[0] == n_mels, f"Nombre de bandes Mel attendu: {n_mels}"
        assert len(freqs) == n_mels, "Nombre de fréquences doit correspondre à n_mels"


class TestPeakPicking:
    """Tests pour l'extraction des pics (Story E1-02)."""
    
    def test_extract_peaks_returns_list(self):
        """Vérifie que la fonction retourne une liste de tuples."""
        # Créer un spectrogramme simple avec un pic évident
        n_mels = 128
        n_frames = 100
        spectrogram = np.random.randn(n_mels, n_frames) * 10 - 50
        
        # Ajouter un pic artificiel
        spectrogram[64, 50] = 0  # Pic au centre
        
        times = np.linspace(0, 1, n_frames)
        freqs = np.linspace(200, 8000, n_mels)
        
        peaks = extract_peaks(spectrogram, times, freqs)
        
        assert isinstance(peaks, list), "Les pics doivent être une liste"
        if len(peaks) > 0:
            assert isinstance(peaks[0], tuple), "Chaque pic doit être un tuple"
            assert len(peaks[0]) == 2, "Chaque pic doit avoir (time, frequency)"
    
    def test_extract_peaks_max_peaks(self):
        """Vérifie que max_peaks limite le nombre de résultats."""
        n_mels = 128
        n_frames = 100
        spectrogram = np.random.randn(n_mels, n_frames) * 10 - 30
        
        times = np.linspace(0, 1, n_frames)
        freqs = np.linspace(200, 8000, n_mels)
        
        max_peaks = 10
        peaks = extract_peaks(spectrogram, times, freqs, max_peaks=max_peaks)
        
        assert len(peaks) <= max_peaks, f"Le nombre de pics ne doit pas dépasser {max_peaks}"


class TestFingerprint:
    """Tests pour la génération d'empreintes (Story E1-03)."""
    
    def test_generate_fingerprint_returns_list(self):
        """Vérifie que la fonction retourne une liste de tuples."""
        # Créer des pics artificiels
        peaks = [
            (0.1, 440.0),
            (0.2, 880.0),
            (0.3, 1320.0),
            (0.4, 1760.0),
        ]
        
        fingerprints = generate_fingerprint(peaks)
        
        assert isinstance(fingerprints, list), "Les empreintes doivent être une liste"
        if len(fingerprints) > 0:
            assert isinstance(fingerprints[0], tuple), "Chaque empreinte doit être un tuple"
            assert len(fingerprints[0]) == 2, "Chaque empreinte doit avoir (hash, anchor_time)"
            assert isinstance(fingerprints[0][0], int), "Le hash doit être un entier"
            assert isinstance(fingerprints[0][1], float), "Le temps d'ancre doit être un float"
    
    def test_generate_fingerprint_empty(self):
        """Vérifie le comportement avec moins de 2 pics."""
        assert generate_fingerprint([]) == [], "Aucun pic => aucune empreinte"
        assert generate_fingerprint([(0.1, 440.0)]) == [], "Un seul pic => aucune empreinte"
    
    def test_generate_fingerprint_hash_stability(self):
        """Vérifie que le même pic produit le même hash."""
        peaks = [
            (0.1, 440.0),
            (0.2, 880.0),
        ]
        
        fp1 = generate_fingerprint(peaks)
        fp2 = generate_fingerprint(peaks)
        
        assert fp1 == fp2, "Les mêmes pics doivent produire les mêmes empreintes"
    
    def test_generate_fingerprint_none_raises_error(self):
        """Vérifie que peaks=None lève une ValueError (cas limite)."""
        with pytest.raises(ValueError, match="peaks ne peut pas être None"):
            generate_fingerprint(None)
    
    def test_generate_fingerprint_target_zone_duration(self):
        """Vérifie que la zone cible respecte la config (5s par défaut)."""
        # Pics espacés de plus de 5s
        peaks = [
            (0.0, 440.0),
            (6.0, 880.0),  # > 5s, hors zone cible
        ]
        
        fingerprints = generate_fingerprint(peaks)
        assert len(fingerprints) == 0, "Doit ignorer les pics hors zone cible (5s)"
        
        # Pics dans la zone cible
        peaks_in_zone = [
            (0.0, 440.0),
            (4.0, 880.0),  # < 5s, dans zone cible
        ]
        
        fingerprints_in_zone = generate_fingerprint(peaks_in_zone)
        assert len(fingerprints_in_zone) > 0, "Doit inclure les pics dans la zone cible"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
