"""
Calcul du spectrogramme.
Story E1-01 : Chargement audio + spectrogramme
"""

import numpy as np
import librosa
from typing import Tuple


def compute_spectrogram(
    signal: np.ndarray,
    sr: int = 44100,
    n_fft: int = 2048,
    hop_length: int = 512,
    n_mels: int = 128
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calcule le spectrogramme Mel d'un signal audio.
    
    Args:
        signal: Signal audio mono (tableau numpy)
        sr: Fréquence d'échantillonnage (Hz)
        n_fft: Taille de la fenêtre FFT
        hop_length: Pas entre les fenêtres (en échantillons)
        n_mels: Nombre de bandes Mel
    
    Returns:
        Tuple contenant:
            - S: Spectrogramme Mel (n_mels x temps) en échelle logarithmique
            - times: Tableau des temps (en secondes)
            - freqs: Tableau des fréquences (en Hz) pour chaque bande Mel
    """
    # Calcul du spectrogramme Mel
    S = librosa.feature.melspectrogram(
        y=signal,
        sr=sr,
        n_fft=n_fft,
        hop_length=hop_length,
        n_mels=n_mels
    )
    
    # Conversion en échelle logarithmique (dB)
    S_db = librosa.power_to_db(S, ref=np.max)
    
    # Calcul des axes temps et fréquence
    times = librosa.frames_to_time(
        np.arange(S_db.shape[1]),
        sr=sr,
        hop_length=hop_length
    )
    
    # Fréquences centrales des bandes Mel
    freqs = librosa.core.mel_frequencies(
        n_mels=n_mels,
        fmin=librosa.note_to_hz('C2'),
        fmax=librosa.note_to_hz('C7')
    )
    
    return S_db, times, freqs
