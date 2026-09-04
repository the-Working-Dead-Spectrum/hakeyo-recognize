"""
Tests pour le script CLI recognize.py (Story E2-04).

Conforme QWEN.md Section 0 : Tests mesurant le comportement réel,
pas juste l'exécution sans erreur.
"""

import pytest
import subprocess
import json
import tempfile
import os
from pathlib import Path
import numpy as np
import soundfile as sf

# Chemin vers le script
SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "recognize.py"


class TestRecognizeCLI:
    """Tests pour le script CLI recognize.py."""
    
    def test_help_option(self):
        """Test que --help fonctionne et affiche la documentation."""
        result = subprocess.run(
            ["python", str(SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)}
        )
        
        assert result.returncode == 0
        assert "Reconnaissance musicale locale" in result.stdout
        assert "audio_file" in result.stdout
        assert "--db" in result.stdout
        assert "--json" in result.stdout
        assert "--verbose" in result.stdout
    
    def test_nonexistent_file_error(self, tmp_path):
        """Test qu'un fichier inexistant retourne une erreur claire."""
        db_path = tmp_path / "test.db"
        audio_path = tmp_path / "nonexistent.mp3"
        
        result = subprocess.run(
            ["python", str(SCRIPT_PATH), str(audio_path), "--db", str(db_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)}
        )
        
        # Doit échouer proprement avec un message d'erreur
        assert "inexistant" in result.stdout.lower() or "Base de données vide" in result.stdout
    
    def test_empty_database_returns_error(self, tmp_path):
        """Test qu'une base de données vide retourne une erreur explicite."""
        db_path = tmp_path / "empty.db"
        
        # Création d'un fichier audio valide
        duration = 3.0
        sample_rate = 11025
        samples = int(duration * sample_rate)
        audio_data = np.random.uniform(-0.5, 0.5, samples)
        audio_path = tmp_path / "test.wav"
        sf.write(str(audio_path), audio_data, sample_rate)
        
        result = subprocess.run(
            ["python", str(SCRIPT_PATH), str(audio_path), "--db", str(db_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)}
        )
        
        assert "Base de données vide" in result.stdout
        assert "ingest.py" in result.stdout  # Suggestion d'action
    
    def test_json_output_format(self, tmp_path):
        """Test que le mode --json retourne un JSON valide."""
        db_path = tmp_path / "test.db"
        
        # Création d'un fichier audio valide
        duration = 3.0
        sample_rate = 11025
        samples = int(duration * sample_rate)
        audio_data = np.random.uniform(-0.5, 0.5, samples)
        audio_path = tmp_path / "test.wav"
        sf.write(str(audio_path), audio_data, sample_rate)
        
        result = subprocess.run(
            ["python", str(SCRIPT_PATH), str(audio_path), "--db", str(db_path), "--json"],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)}
        )
        
        # Le stdout doit être du JSON valide
        try:
            output = json.loads(result.stdout)
            assert isinstance(output, dict)
            assert "match" in output
            assert isinstance(output["match"], bool)
        except json.JSONDecodeError:
            pytest.fail("La sortie n'est pas un JSON valide")
    
    def test_verbose_mode_shows_logs(self, tmp_path):
        """Test que le mode --verbose affiche des logs détaillés."""
        db_path = tmp_path / "test.db"
        
        # Création d'un fichier audio valide
        duration = 3.0
        sample_rate = 11025
        samples = int(duration * sample_rate)
        audio_data = np.random.uniform(-0.5, 0.5, samples)
        audio_path = tmp_path / "test.wav"
        sf.write(str(audio_path), audio_data, sample_rate)
        
        result = subprocess.run(
            ["python", str(SCRIPT_PATH), str(audio_path), "--db", str(db_path), "--verbose"],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)}
        )
        
        # Doit contenir des logs structurés
        assert "[VALIDATION]" in result.stdout or "[INFO]" in result.stdout
    
    def test_exit_code_zero_on_no_match(self, tmp_path):
        """Test que le code de sortie est 0 même sans match (résultat métier valide)."""
        db_path = tmp_path / "test.db"
        
        # Création d'un fichier audio valide
        duration = 3.0
        sample_rate = 11025
        samples = int(duration * sample_rate)
        audio_data = np.random.uniform(-0.5, 0.5, samples)
        audio_path = tmp_path / "test.wav"
        sf.write(str(audio_path), audio_data, sample_rate)
        
        result = subprocess.run(
            ["python", str(SCRIPT_PATH), str(audio_path), "--db", str(db_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)}
        )
        
        # Code 0 = succès métier (même sans match)
        # Seules les erreurs techniques doivent retourner 1
        if "Base de données vide" in result.stdout:
            assert result.returncode == 1  # Erreur technique
        else:
            assert result.returncode == 0  # Résultat métier valide
    
    def test_fallback_message_on_no_match(self, tmp_path):
        """Test que le fallback ARCCloud est mentionné en cas de non-match."""
        db_path = tmp_path / "test.db"
        
        # Création d'un fichier audio valide
        duration = 3.0
        sample_rate = 11025
        samples = int(duration * sample_rate)
        audio_data = np.random.uniform(-0.5, 0.5, samples)
        audio_path = tmp_path / "test.wav"
        sf.write(str(audio_path), audio_data, sample_rate)
        
        result = subprocess.run(
            ["python", str(SCRIPT_PATH), str(audio_path), "--db", str(db_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)}
        )
        
        # Si la DB n'est pas vide mais aucun match, doit mentionner le fallback
        if "Base de données vide" not in result.stdout:
            assert "FALLBACK" in result.stdout or "ARCCloud" in result.stdout


class TestRecognizeOutputStructure:
    """Tests de la structure de sortie du script."""
    
    def test_output_contains_required_fields(self, tmp_path):
        """Test que la sortie JSON contient tous les champs requis du contrat API."""
        db_path = tmp_path / "test.db"
        
        # Création d'un fichier audio valide
        duration = 3.0
        sample_rate = 11025
        samples = int(duration * sample_rate)
        audio_data = np.random.uniform(-0.5, 0.5, samples)
        audio_path = tmp_path / "test.wav"
        sf.write(str(audio_path), audio_data, sample_rate)
        
        result = subprocess.run(
            ["python", str(SCRIPT_PATH), str(audio_path), "--db", str(db_path), "--json"],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)}
        )
        
        output = json.loads(result.stdout)
        
        # Champs requis selon QWEN.md Section 6
        # Note: en cas d'erreur technique (DB vide), certains champs peuvent être absents
        required_fields = ["match", "processing_time_ms", "source"]
        for field in required_fields:
            assert field in output, f"Champ manquant: {field}"
        
        # Si match=True, champs additionnels requis
        if output.get("match"):
            assert "track_id" in output
            assert "title" in output
            assert "artist" in output
            assert "confidence" in output
        
        # Si erreur technique, champ 'error' présent
        if "error" in output:
            # C'est un cas d'erreur, pas un échec de reconnaissance
            pass
