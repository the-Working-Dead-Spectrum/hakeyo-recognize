"""
Extraction des pics spectraux (peak-picking).
Story E1-02 : Extraction des pics
"""

import numpy as np
from scipy.ndimage import maximum_filter
from typing import List, Tuple


def extract_peaks(
    spectrogram: np.ndarray,
    times: np.ndarray,
    freqs: np.ndarray,
    neighborhood_size: int = 5,
    threshold: float = -60.0,
    max_peaks: int = None
) -> List[Tuple[float, float]]:
    """
    Extrait les pics locaux du spectrogramme.
    
    Un pic est un point dont l'amplitude est supérieure à tous ses voisins
    dans une fenêtre définie, et qui dépasse un seuil minimal.
    
    Args:
        spectrogram: Spectrogramme Mel en dB (n_mels x temps)
        times: Axe des temps (secondes)
        freqs: Axe des fréquences (Hz)
        neighborhood_size: Taille de la fenêtre pour la détection de maxima locaux
        threshold: Seuil minimal en dB pour considérer un pic
        max_peaks: Nombre maximum de pics à retourner (None = tous)
    
    Returns:
        Liste de tuples (time, frequency) représentant les pics détectés
    """
    # Appliquer un filtre de maximum local
    neighborhood = (neighborhood_size, neighborhood_size)
    local_max = maximum_filter(spectrogram, size=neighborhood)
    
    # Trouver les positions où le spectrogramme égale le maximum local
    # (ce sont les maxima locaux)
    peaks_mask = (spectrogram == local_max) & (spectrogram > threshold)
    
    # Extraire les indices des pics
    peak_freq_indices, peak_time_indices = np.where(peaks_mask)
    
    # Convertir en coordonnées réelles (temps, fréquence)
    peaks = []
    for freq_idx, time_idx in zip(peak_freq_indices, peak_time_indices):
        time_val = times[time_idx]
        freq_val = freqs[freq_idx]
        peaks.append((time_val, freq_val))
    
    # Trier par amplitude décroissante et limiter le nombre de pics
    if max_peaks is not None and len(peaks) > max_peaks:
        # Récupérer les amplitudes pour trier
        peak_amplitudes = [
            spectrogram[freq_idx, time_idx]
            for freq_idx, time_idx in zip(peak_freq_indices, peak_time_indices)
        ]
        
        # Trier par amplitude décroissante
        sorted_indices = np.argsort(peak_amplitudes)[::-1][:max_peaks]
        peaks = [peaks[i] for i in sorted_indices]
    
    return peaks
