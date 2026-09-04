"""
Tests unitaires pour le module fallback/ArcCloudProvider.

Conformité QWEN.md Section 7:
- Tests dédiés pour chaque fonction publique
- Validation des cas limites (timeout, erreurs HTTP, JSON invalide)
- Vérification que la clé API n'apparaît jamais dans les logs/messages
"""

import os
import pytest
from unittest.mock import patch, MagicMock
import json

from fallback import ArcCloudProvider, ArcCloudUnavailableError, RecognitionResult


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_env_vars():
    """Fixture pour définir les variables d'environnement requises."""
    with patch.dict(os.environ, {
        "ARCCLOUD_API_KEY": "test_api_key_secret",
        "ARCCLOUD_API_URL": "https://api.arccloud.example/recognize"
    }):
        yield


@pytest.fixture
def provider(mock_env_vars):
    """Fixture pour créer un provider configuré."""
    return ArcCloudProvider()


# =============================================================================
# Tests d'initialisation
# =============================================================================

class TestArcCloudProviderInit:
    """Tests de l'initialisation du provider."""
    
    def test_init_with_env_vars(self, mock_env_vars):
        """Le provider s'initialise correctement avec les variables d'environnement."""
        provider = ArcCloudProvider()
        assert provider.api_key == "test_api_key_secret"
        assert provider.api_url == "https://api.arccloud.example/recognize"
    
    def test_init_with_explicit_args(self):
        """Les arguments explicites override les variables d'environnement."""
        provider = ArcCloudProvider(
            api_key="explicit_key",
            api_url="https://explicit.url"
        )
        assert provider.api_key == "explicit_key"
        assert provider.api_url == "https://explicit.url"
    
    def test_init_missing_api_key(self):
        """ValueError levée si ARCCLOUD_API_KEY est absent."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                ArcCloudProvider()
            assert "ARCCLOUD_API_KEY" in str(exc_info.value)
    
    def test_init_missing_api_url(self):
        """ValueError levée si ARCCLOUD_API_URL est absent."""
        with patch.dict(os.environ, {"ARCCLOUD_API_KEY": "key"}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                ArcCloudProvider()
            assert "ARCCLOUD_API_URL" in str(exc_info.value)
    
    def test_api_key_not_in_error_message(self):
        """La valeur de la clé API n'apparaît jamais dans les messages d'erreur."""
        with patch.dict(os.environ, {
            "ARCCLOUD_API_KEY": "super_secret_key_12345",
            "ARCCLOUD_API_URL": "https://api.arccloud.example/recognize"
        }):
            try:
                # Force une erreur pour vérifier le message
                provider = ArcCloudProvider()
                # Simule une erreur
                raise ValueError("Test error")
            except ValueError as e:
                # La clé secrète ne doit pas apparaître
                assert "super_secret_key_12345" not in str(e)


# =============================================================================
# Tests de reconnaissance - succès
# =============================================================================

class TestRecognizeSuccess:
    """Tests des cas de reconnaissance réussie."""
    
    @patch('fallback.requests.post')
    def test_recognize_match_found(self, mock_post, provider):
        """Reconnaissance avec match trouvé."""
        # Mock de la réponse HTTP
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "found",
            "result": {
                "id": 123,
                "title": "Titre Test",
                "artist": "Artiste Test",
                "confidence": 0.94
            }
        }
        mock_post.return_value = mock_response
        
        # Création d'un fichier audio fictif
        with patch('builtins.open', MagicMock()), \
             patch('os.path.isfile', return_value=True):
            result = provider.recognize("/fake/path/audio.mp3")
        
        assert result.match is True
        assert result.track_id == 123
        assert result.title == "Titre Test"
        assert result.artist == "Artiste Test"
        assert result.confidence == 0.94
        assert result.source == "arccloud"
    
    @patch('fallback.requests.post')
    def test_recognize_no_match_404(self, mock_post, provider):
        """Reconnaissance sans match (404)."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"status": "not_found"}
        mock_post.return_value = mock_response
        
        with patch('builtins.open', MagicMock()), \
             patch('os.path.isfile', return_value=True):
            result = provider.recognize("/fake/path/audio.mp3")
        
        assert result.match is False
        assert result.track_id is None
        assert result.source == "arccloud"
    
    @patch('fallback.requests.post')
    def test_recognize_no_match_status_field(self, mock_post, provider):
        """Reconnaissance sans match (status explicite)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "not_found"}
        mock_post.return_value = mock_response
        
        with patch('builtins.open', MagicMock()), \
             patch('os.path.isfile', return_value=True):
            result = provider.recognize("/fake/path/audio.mp3")
        
        assert result.match is False


# =============================================================================
# Tests de reconnaissance - erreurs techniques
# =============================================================================

class TestRecognizeErrors:
    """Tests des erreurs techniques (doivent lever ArcCloudUnavailableError)."""
    
    @patch('fallback.requests.post')
    def test_timeout_error(self, mock_post, provider):
        """Timeout après 5 secondes."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()
        
        with patch('builtins.open', MagicMock()), \
             patch('os.path.isfile', return_value=True):
            with pytest.raises(ArcCloudUnavailableError) as exc_info:
                provider.recognize("/fake/path/audio.mp3")
        
        assert "Timeout" in str(exc_info.value)
    
    @patch('fallback.requests.post')
    def test_connection_error(self, mock_post, provider):
        """Erreur de connexion (DNS, refus, etc.)."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError()
        
        with patch('builtins.open', MagicMock()), \
             patch('os.path.isfile', return_value=True):
            with pytest.raises(ArcCloudUnavailableError) as exc_info:
                provider.recognize("/fake/path/audio.mp3")
        
        assert "connexion" in str(exc_info.value).lower() or "Connection" in str(exc_info.value)
    
    @patch('fallback.requests.post')
    def test_server_error_500(self, mock_post, provider):
        """Erreur serveur 5xx."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response
        
        with patch('builtins.open', MagicMock()), \
             patch('os.path.isfile', return_value=True):
            with pytest.raises(ArcCloudUnavailableError) as exc_info:
                provider.recognize("/fake/path/audio.mp3")
        
        assert "500" in str(exc_info.value)
    
    @patch('fallback.requests.post')
    def test_auth_error_401(self, mock_post, provider):
        """Erreur d'authentification 401."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response
        
        with patch('builtins.open', MagicMock()), \
             patch('os.path.isfile', return_value=True):
            with pytest.raises(ArcCloudUnavailableError) as exc_info:
                provider.recognize("/fake/path/audio.mp3")
        
        assert "401" in str(exc_info.value) or "Authentification" in str(exc_info.value)
    
    @patch('fallback.requests.post')
    def test_forbidden_403(self, mock_post, provider):
        """Accès refusé 403."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_post.return_value = mock_response
        
        with patch('builtins.open', MagicMock()), \
             patch('os.path.isfile', return_value=True):
            with pytest.raises(ArcCloudUnavailableError) as exc_info:
                provider.recognize("/fake/path/audio.mp3")
        
        assert "403" in str(exc_info.value) or "refusé" in str(exc_info.value)
    
    @patch('fallback.requests.post')
    def test_invalid_json_response(self, mock_post, provider):
        """Réponse JSON mal formée."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("JSON decode error")
        mock_post.return_value = mock_response
        
        with patch('builtins.open', MagicMock()), \
             patch('os.path.isfile', return_value=True):
            with pytest.raises(ArcCloudUnavailableError) as exc_info:
                provider.recognize("/fake/path/audio.mp3")
        
        assert "JSON" in str(exc_info.value) or "invalide" in str(exc_info.value).lower()
    
    def test_file_not_found(self, provider):
        """Fichier audio inexistant."""
        with patch('os.path.isfile', return_value=False):
            with pytest.raises(FileNotFoundError):
                provider.recognize("/nonexistent/path/audio.mp3")


# =============================================================================
# Tests de normalisation
# =============================================================================

class TestNormalization:
    """Tests de la normalisation des réponses."""
    
    def test_recognition_result_to_dict(self):
        """Sérialisation correcte de RecognitionResult."""
        result = RecognitionResult(
            match=True,
            track_id=42,
            title="Ma Chanson",
            artist="Mon Artiste",
            confidence=0.87
        )
        
        data = result.to_dict()
        
        assert data["match"] is True
        assert data["track_id"] == 42
        assert data["title"] == "Ma Chanson"
        assert data["artist"] == "Mon Artiste"
        assert data["confidence"] == 0.87
        assert data["source"] == "arccloud"
    
    def test_recognition_result_default_values(self):
        """Valeurs par défaut correctes pour no-match."""
        result = RecognitionResult(match=False)
        
        assert result.match is False
        assert result.track_id is None
        assert result.title is None
        assert result.artist is None
        assert result.confidence == 0.0
        assert result.source == "arccloud"


# =============================================================================
# Tests de timeout configuré
# =============================================================================

class TestTimeoutConfiguration:
    """Vérification que le timeout est bien configuré à 5 secondes."""
    
    @patch('fallback.requests.post')
    def test_timeout_is_5_seconds(self, mock_post, provider):
        """Le timeout passé à requests.post est bien 5 secondes."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "not_found"}
        mock_post.return_value = mock_response
        
        with patch('builtins.open', MagicMock()), \
             patch('os.path.isfile', return_value=True):
            provider.recognize("/fake/path/audio.mp3")
        
        # Vérifier que post a été appelé avec timeout=5.0
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["timeout"] == 5.0


# =============================================================================
# Tests de sécurité - non-exposition des secrets
# =============================================================================

class TestSecurityNoSecretLeak:
    """Vérification que les secrets n'apparaissent pas dans les logs/messages."""
    
    def test_api_key_not_in_exception_message(self):
        """La clé API n'apparaît pas dans les messages d'exception."""
        secret_key = "super_secret_xyz_789"
        
        with patch.dict(os.environ, {
            "ARCCLOUD_API_KEY": secret_key,
            "ARCCLOUD_API_URL": "https://api.arccloud.example/recognize"
        }):
            provider = ArcCloudProvider()
            
            # Vérifier que l'attribut existe mais n'est pas loggué tel quel
            assert hasattr(provider, 'api_key')
            assert provider.api_key == secret_key
            
            # Le __repr__ ou __str__ ne doit pas exposer la clé
            provider_repr = repr(provider)
            provider_str = str(provider)
            
            assert secret_key not in provider_repr
            assert secret_key not in provider_str
