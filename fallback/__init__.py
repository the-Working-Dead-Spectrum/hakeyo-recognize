"""
Fallback - Intégration du service de reconnaissance ARCCloud.

Ce module implémente le fallback obligatoire vers ARCCloud lorsque
le moteur local ne trouve pas de match avec un score de confiance suffisant.

Conformité QWEN.md Section 6.2 (E2-05):
- Contrat API mock réaliste piloté par ARCCLOUD_API_URL
- Timeout: 5 secondes, sans retry automatique (KISS/YAGNI)
- Exception dédiée ArcCloudUnavailableError pour les erreurs techniques
- Normalisation vers RecognitionResult interne standard
- Secrets via variables d'environnement (ARCCLOUD_API_KEY, ARCCLOUD_API_URL)
- Client HTTP: requests
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

import requests


logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions dédiées
# =============================================================================

class ArcCloudUnavailableError(Exception):
    """
    Exception levée en cas d'erreur technique lors de l'appel à ARCCloud.
    
    Cas couverts:
    - Timeout (>5s)
    - Erreur réseau (DNS, connexion refusée, etc.)
    - Erreur HTTP (5xx, 4xx non attendus)
    
    À attraper explicitement par l'appelant (recognize.py) pour loguer
    distinctement d'un simple 'match: false' métier.
    """
    pass


# =============================================================================
# Structure de résultat normalisée
# =============================================================================

@dataclass
class RecognitionResult:
    """
    Résultat standardisé d'une reconnaissance (local ou ARCCloud).
    
    Conforme au contrat d'API Section 6 de QWEN.md.
    """
    match: bool
    track_id: Optional[int] = None
    title: Optional[str] = None
    artist: Optional[str] = None
    confidence: float = 0.0
    source: str = "arccloud"  # Toujours "arccloud" pour ce provider
    
    def to_dict(self) -> Dict[str, Any]:
        """Sérialisation pour API ou CLI."""
        return {
            "match": self.match,
            "track_id": self.track_id,
            "title": self.title,
            "artist": self.artist,
            "confidence": self.confidence,
            "source": self.source,
        }


# =============================================================================
# Provider ARCCloud
# =============================================================================

class ArcCloudProvider:
    """
    Client HTTP pour le service de reconnaissance ARCCloud.
    
    Responsabilités (Single Responsibility, Section 7.1):
    - Appeler l'API ARCCloud avec timeout 5s
    - Gérer les erreurs réseau/HTTP et lever ArcCloudUnavailableError
    - Normaliser la réponse brute vers RecognitionResult
    
    Aucune logique conditionnelle liée à ARCCloud ne doit fuiter hors de ce module
    (Dependency Inversion, Section 7.1).
    
    DETTE TECHNIQUE (Section 0):
    Le contrat JSON utilisé ici est une hypothèse basée sur les conventions courantes.
    Il doit être vérifié et ajusté dès que la documentation réelle d'ARCCloud sera disponible.
    """
    
    DEFAULT_TIMEOUT = 5.0  # secondes, sans retry (KISS/YAGNI)
    
    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        """
        Initialise le provider ARCCloud.
        
        Args:
            api_key: Clé API ARCCloud. Si None, récupérée depuis ARCCLOUD_API_KEY.
            api_url: URL de l'API ARCCloud. Si None, récupérée depuis ARCCLOUD_API_URL.
        
        Raises:
            ValueError: Si ARCCLOUD_API_KEY ou ARCCLOUD_API_URL est absent(e) des variables
                        d'environnement et non fourni(e) en argument.
        """
        self.api_key = api_key or os.getenv("ARCCLOUD_API_KEY")
        self.api_url = api_url or os.getenv("ARCCLOUD_API_URL")
        
        if not self.api_key:
            raise ValueError(
                "ARCCLOUD_API_KEY est requis. Définissez la variable d'environnement "
                "ou passez api_key en argument."
            )
        if not self.api_url:
            raise ValueError(
                "ARCCLOUD_API_URL est requis. Définissez la variable d'environnement "
                "ou passez api_url en argument."
            )
        
        # Note: La valeur de la clé n'apparaît jamais dans les logs/messages d'erreur
        
        logger.info(f"ArcCloudProvider initialisé avec URL: {self.api_url}")
    
    def recognize(self, audio_file_path: str) -> RecognitionResult:
        """
        Reconnaît un fichier audio via l'API ARCCloud.
        
        Args:
            audio_file_path: Chemin absolu du fichier audio à analyser.
        
        Returns:
            RecognitionResult normalisé.
        
        Raises:
            ArcCloudUnavailableError: En cas d'erreur technique (timeout, réseau, HTTP).
            FileNotFoundError: Si le fichier audio n'existe pas.
        
        Side effects:
            - Lit le fichier audio en mémoire pour l'envoi multipart
            - Loggue les erreurs techniques (pas les succès/échecs métier)
        """
        if not os.path.isfile(audio_file_path):
            raise FileNotFoundError(f"Le fichier audio n'existe pas: {audio_file_path}")
        
        try:
            with open(audio_file_path, "rb") as f:
                files = {"audio": (os.path.basename(audio_file_path), f, "audio/mpeg")}
                headers = {"Authorization": f"Bearer {self.api_key}"}
                
                logger.debug(f"Appel ARCCloud: POST {self.api_url}")
                
                response = requests.post(
                    self.api_url,
                    files=files,
                    headers=headers,
                    timeout=self.DEFAULT_TIMEOUT,
                )
                
                # Gestion des erreurs HTTP
                if response.status_code >= 500:
                    raise ArcCloudUnavailableError(
                        f"Erreur serveur ARCCloud (status {response.status_code})"
                    )
                
                if response.status_code == 401:
                    raise ArcCloudUnavailableError(
                        "Authentification ARCCloud invalide (status 401)"
                    )
                
                if response.status_code == 403:
                    raise ArcCloudUnavailableError(
                        "Accès ARCCloud refusé (status 403)"
                    )
                
                if response.status_code not in (200, 404):
                    # Autres codes 4xx considérés comme erreur client, pas erreur technique
                    # Mais on logge pour diagnostic
                    logger.warning(f"ARCCloud retourne status {response.status_code}")
                
                # Parsing de la réponse JSON
                try:
                    data = response.json()
                except ValueError as e:
                    raise ArcCloudUnavailableError(
                        f"Réponse ARCCloud invalide (JSON mal formé): {e}"
                    ) from e
                
                return self._normalize_response(data, response.status_code)
                
        except requests.exceptions.Timeout as e:
            raise ArcCloudUnavailableError(
                f"Timeout ARCCloud après {self.DEFAULT_TIMEOUT}s"
            ) from e
        
        except requests.exceptions.ConnectionError as e:
            raise ArcCloudUnavailableError(
                f"Erreur de connexion à ARCCloud: {e}"
            ) from e
        
        except requests.exceptions.RequestException as e:
            # Catch-all pour autres erreurs requests (DNS, SSL, etc.)
            raise ArcCloudUnavailableError(
                f"Erreur réseau lors de l'appel ARCCloud: {e}"
            ) from e
    
    def _normalize_response(self, data: Dict[str, Any], status_code: int) -> RecognitionResult:
        """
        Normalise la réponse brute d'ARCCloud vers RecognitionResult.
        
        Hypothèse de contrat JSON (à vérifier avec la doc réelle):
        {
            "status": "found" | "not_found",
            "result": {
                "id": 123,
                "title": "Titre",
                "artist": "Artiste",
                "confidence": 0.94
            }
        }
        
        Ou en cas de non-match (404):
        {
            "status": "not_found"
        }
        
        Args:
            data: Réponse JSON brute d'ARCCloud
            status_code: Code HTTP de la réponse
        
        Returns:
            RecognitionResult normalisé
        
        DETTE TECHNIQUE (Section 0):
        Ce parsing repose sur une hypothèse de contrat. À valider avec la doc ARCCloud.
        """
        # Cas: pas de match (404 ou status explicite)
        if status_code == 404:
            return RecognitionResult(match=False)
        
        status = data.get("status", "")
        
        if status == "not_found" or "result" not in data:
            return RecognitionResult(match=False)
        
        # Cas: match trouvé
        result = data.get("result", {})
        
        return RecognitionResult(
            match=True,
            track_id=result.get("id"),
            title=result.get("title"),
            artist=result.get("artist"),
            confidence=float(result.get("confidence", 0.0)),
        )
