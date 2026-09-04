"""
Chargement de fichiers audio.
Story E1-01 : Chargement audio + spectrogramme
"""

import librosa
import numpy as np
from typing import Tuple


def load_audio_file(
    file_path: str,
    sample_rate: int = 44100,
    duration: float = None
) -> Tuple[np.ndarray, int]:
    """
    Charge un fichier audio et le convertit en mono.
    
    Args:
        file_path: Chemin vers le fichier audio
        sample_rate: Fréquence d'échantillonnage cible (défaut: 44100 Hz)
        duration: Durée maximale à charger en secondes (None = complet)
    
    Returns:
        Tuple contenant:
            - signal: Tableau numpy du signal audio (mono, normalisé)
            - sr: Fréquence d'échantillonnage effective
    """
    signal, sr = librosa.load(
        file_path,
        sr=sample_rate,
        mono=True,
        duration=duration
    )
    
    return signal, sr
