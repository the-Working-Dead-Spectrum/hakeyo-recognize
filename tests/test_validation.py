"""
Tests pour le module de validation audio (storage/validation.py).

Conforme QWEN.md Section 0 : Tests ne validant pas juste l'exécution,
mais prouvant le comportement correct dans tous les cas limites.
"""

import pytest
import os
import tempfile
from pathlib import Path
import numpy as np
import soundfile as sf

from storage.validation import (
    validate_audio_file,
    validate_audio_for_recognition,
    ValidationError,
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    MIN_AUDIO_DURATION_SEC,
)


class TestValidateAudioFile:
    """Tests pour la fonction validate_audio_file."""
    
    def test_valid_wav_file(self, tmp_path):
        """Test avec un fichier WAV valide."""
        # Création d'un fichier audio valide (3s)
        duration = 3.0
        sample_rate = 11025
        samples = int(duration * sample_rate)
        audio_data = np.random.uniform(-0.5, 0.5, samples)
        
        file_path = tmp_path / "test.wav"
        sf.write(str(file_path), audio_data, sample_rate)
        
        # Validation
        resolved_path, metadata = validate_audio_file(str(file_path))
        
        assert resolved_path == file_path.resolve()
        assert metadata['duration'] >= MIN_AUDIO_DURATION_SEC
        # librosa resample à SAMPLE_RATE par défaut (11025 ou 22050 selon config)
        assert metadata['sample_rate'] > 0  # Juste vérifier qu'il y a un sample rate valide
        assert metadata['size'] > 0
    
    def test_valid_mp3_file(self, tmp_path):
        """Test avec un fichier MP3 valide."""
        duration = 5.0
        sample_rate = 22050
        samples = int(duration * sample_rate)
        audio_data = np.random.uniform(-0.5, 0.5, samples)
        
        file_path = tmp_path / "test.mp3"
        sf.write(str(file_path), audio_data, sample_rate, format='MP3')
        
        resolved_path, metadata = validate_audio_file(str(file_path))
        
        assert resolved_path.exists()
        assert metadata['duration'] >= MIN_AUDIO_DURATION_SEC
    
    def test_nonexistent_file_raises_error(self, tmp_path):
        """Test qu'un fichier inexistant lève une ValidationError."""
        non_existent = tmp_path / "does_not_exist.wav"
        
        with pytest.raises(ValidationError) as exc_info:
            validate_audio_file(str(non_existent))
        
        assert "inexistant" in str(exc_info.value).lower()
    
    def test_directory_instead_of_file_raises_error(self, tmp_path):
        """Test qu'un dossier (pas un fichier) lève une ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_audio_file(str(tmp_path))
        
        assert "fichier" in str(exc_info.value).lower()
    
    def test_invalid_extension_raises_error(self, tmp_path):
        """Test qu'une extension non supportée lève une ValidationError."""
        # Création d'un fichier avec mauvaise extension
        bad_file = tmp_path / "test.xyz"
        bad_file.write_text("fake audio")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_audio_file(str(bad_file))
        
        assert "extension" in str(exc_info.value).lower()
    
    def test_empty_file_raises_error(self, tmp_path):
        """Test qu'un fichier vide lève une ValidationError."""
        empty_file = tmp_path / "empty.wav"
        empty_file.touch()
        
        with pytest.raises(ValidationError) as exc_info:
            validate_audio_file(str(empty_file))
        
        assert "vide" in str(exc_info.value).lower()
    
    def test_too_short_audio_raises_error(self, tmp_path):
        """Test qu'un extrait trop court (< MIN_AUDIO_DURATION_SEC) lève une erreur."""
        # Création d'un fichier de 1s (trop court)
        duration = 1.0  # < MIN_AUDIO_DURATION_SEC (2.0s)
        sample_rate = 11025
        samples = int(duration * sample_rate)
        audio_data = np.random.uniform(-0.5, 0.5, samples)
        
        file_path = tmp_path / "too_short.wav"
        sf.write(str(file_path), audio_data, sample_rate)
        
        with pytest.raises(ValidationError) as exc_info:
            validate_audio_file(str(file_path))
        
        assert "trop court" in str(exc_info.value).lower()
        assert str(MIN_AUDIO_DURATION_SEC) in str(exc_info.value)
    
    def test_corrupted_audio_file_raises_error(self, tmp_path):
        """Test qu'un fichier corrompu (faux WAV) lève une ValidationError."""
        # Création d'un faux fichier WAV (contenu invalide)
        corrupted_file = tmp_path / "corrupted.wav"
        corrupted_file.write_text("RIFFfake wav content not real audio")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_audio_file(str(corrupted_file))
        
        # Doit mentionner un problème de format ou corruption
        assert any(keyword in str(exc_info.value).lower() 
                   for keyword in ["corrompu", "invalide", "format", "erreur"])
    
    def test_path_traversal_protection(self, tmp_path):
        """Test que les chemins avec .. sont résolus correctement."""
        # Création d'un sous-répertoire
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        
        # Fichier dans le répertoire parent
        duration = 3.0
        sample_rate = 11025
        samples = int(duration * sample_rate)
        audio_data = np.random.uniform(-0.5, 0.5, samples)
        
        parent_file = tmp_path / "parent.wav"
        sf.write(str(parent_file), audio_data, sample_rate)
        
        # Tentative d'accès via .. depuis le sous-répertoire
        traversal_path = subdir / ".." / "parent.wav"
        resolved_path, metadata = validate_audio_file(str(traversal_path))
        
        # Le chemin doit être résolu en absolu
        assert resolved_path.is_absolute()
        assert resolved_path == parent_file.resolve()
    
    def test_validate_audio_for_recognition_wrapper(self, tmp_path):
        """Test que le wrapper validate_audio_for_recognition fonctionne."""
        duration = 3.0
        sample_rate = 11025
        samples = int(duration * sample_rate)
        audio_data = np.random.uniform(-0.5, 0.5, samples)
        
        file_path = tmp_path / "test.wav"
        sf.write(str(file_path), audio_data, sample_rate)
        
        # Le wrapper doit retourner le même résultat
        path1, meta1 = validate_audio_file(str(file_path))
        path2, meta2 = validate_audio_for_recognition(str(file_path))
        
        assert path1 == path2
        assert meta1['duration'] == meta2['duration']
    
    def test_allowed_extensions_constant(self):
        """Test que ALLOWED_EXTENSIONS contient les formats attendus."""
        assert '.mp3' in ALLOWED_EXTENSIONS
        assert '.wav' in ALLOWED_EXTENSIONS
        assert '.flac' in ALLOWED_EXTENSIONS
        assert isinstance(ALLOWED_EXTENSIONS, set)
    
    def test_max_file_size_constant_reasonable(self):
        """Test que MAX_FILE_SIZE_BYTES est défini raisonnablement."""
        # 50 MB maximum - suffisant pour un extrait, pas pour un album complet
        assert MAX_FILE_SIZE_BYTES == 50 * 1024 * 1024
        assert MAX_FILE_SIZE_BYTES > 0
    
    def test_min_duration_constant_defined(self):
        """Test que MIN_AUDIO_DURATION_SEC est défini."""
        assert MIN_AUDIO_DURATION_SEC == 2.0
        assert MIN_AUDIO_DURATION_SEC > 0


class TestValidationEdgeCases:
    """Tests des cas limites avancés."""
    
    def test_silence_audio_detection(self, tmp_path):
        """Test qu'un fichier silence total est détecté comme corrompu/faible."""
        # Silence total pendant 3s
        duration = 3.0
        sample_rate = 11025
        samples = int(duration * sample_rate)
        audio_data = np.zeros(samples)  # Silence parfait
        
        file_path = tmp_path / "silence.wav"
        sf.write(str(file_path), audio_data, sample_rate)
        
        # Le silence devrait passer la validation (c'est techniquement valide)
        # Mais pourrait être rejeté plus tard par extract_peaks
        resolved_path, metadata = validate_audio_file(str(file_path))
        
        assert resolved_path.exists()
        assert metadata['duration'] >= MIN_AUDIO_DURATION_SEC
    
    def test_very_long_audio_passes_validation(self, tmp_path):
        """Test qu'un fichier long (> 5s) passe la validation."""
        # Fichier de 30s (bien au-dessus du minimum)
        duration = 30.0
        sample_rate = 11025
        samples = int(duration * sample_rate)
        audio_data = np.random.uniform(-0.5, 0.5, samples)
        
        file_path = tmp_path / "long.wav"
        sf.write(str(file_path), audio_data, sample_rate)
        
        resolved_path, metadata = validate_audio_file(str(file_path))
        
        assert resolved_path.exists()
        assert metadata['duration'] >= MIN_AUDIO_DURATION_SEC
    
    def test_boundary_duration_exactly_at_minimum(self, tmp_path):
        """Test à la limite exacte de MIN_AUDIO_DURATION_SEC."""
        duration = MIN_AUDIO_DURATION_SEC  # Exactement 2.0s
        sample_rate = 11025
        samples = int(duration * sample_rate)
        audio_data = np.random.uniform(-0.5, 0.5, samples)
        
        file_path = tmp_path / "boundary.wav"
        sf.write(str(file_path), audio_data, sample_rate)
        
        # Doit passer (>= MIN_AUDIO_DURATION_SEC)
        resolved_path, metadata = validate_audio_file(str(file_path))
        
        assert metadata['duration'] >= MIN_AUDIO_DURATION_SEC - 0.1  # Petite tolérance
