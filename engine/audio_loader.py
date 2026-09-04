"""
Chargement de fichiers audio.
Story E1-01 : Chargement audio + spectrogramme

Gère les cas limites : fichiers corrompus, extraits trop courts, silence total.
"""

import librosa
import numpy as np
from typing import Tuple, Optional
from .config import AudioConfig


class AudioLoadingError(Exception):
    """Exception levée lors du chargement d'un fichier audio."""
    pass


class AudioTooShortError(AudioLoadingError):
    """Exception levée lorsque l'audio est trop court (< 3s)."""
    pass


class CorruptedAudioFileError(AudioLoadingError):
    """Exception levée lorsque le fichier audio est corrompu."""
    pass


def load_audio_file(
    file_path: str,
    config: AudioConfig = None,
    duration: Optional[float] = None,
    min_duration: float = 3.0,
) -> Tuple[np.ndarray, int]:
    """
    Charge un fichier audio et le convertit en mono.
    
    Args:
        file_path: Chemin vers le fichier audio
        config: Configuration pour les paramètres audio
        duration: Durée maximale à charger en secondes (None = complet)
        min_duration: Durée minimale requise en secondes (défaut: 3s)
        
    Returns:
        Tuple contenant:
            - signal: Tableau numpy du signal audio (mono, normalisé)
            - sr: Fréquence d'échantillonnage effective
            
    Raises:
        FileNotFoundError: Si le fichier n'existe pas
        CorruptedAudioFileError: Si le fichier est corrompu ou illisible
        AudioTooShortError: Si l'audio est plus court que min_duration
        AudioLoadingError: Pour toute autre erreur de chargement
    """
    if config is None:
        config = AudioConfig()
    
    try:
        signal, sr = librosa.load(
            file_path,
            sr=config.sample_rate,
            mono=True,
            duration=duration
        )
    except FileNotFoundError:
        raise FileNotFoundError(f"Fichier audio non trouvé: {file_path}")
    except Exception as e:
        # Libriosa peut lever différentes exceptions pour fichiers corrompus
        raise CorruptedAudioFileError(
            f"Fichier audio corrompu ou illisible: {file_path}.Erreur: {str(e)}"
        )
    
    # Vérifier si le signal est vide
    if len(signal) == 0:
        raise CorruptedAudioFileError(
            f"Fichier audio vide: {file_path}"
        )
    
    # Vérifier la durée minimale
    actual_duration = len(signal) / config.sample_rate
    if actual_duration < min_duration:
        raise AudioTooShortError(
            f"Audio trop court: {actual_duration:.2f}s < {min_duration}s requis "
            f"(fichier: {file_path})"
        )
    
    # Vérifier si c'est un silence total (toutes les valeurs ~0)
    if np.all(np.abs(signal) < 1e-6):
        raise CorruptedAudioFileError(
            f"Fichier audio contient uniquement du silence: {file_path}"
        )
    
    return signal, config.sample_rate
