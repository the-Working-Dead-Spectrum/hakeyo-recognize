"""
Génération des empreintes digitales (fingerprinting).
Story E1-03 : Génération de hash à partir des pics
"""

import numpy as np
from typing import List, Tuple, Dict


def generate_fingerprint(
    peaks: List[Tuple[float, float]],
    target_zone_radius: float = 0.5,
    max_freq_diff: float = 500.0,
    hash_bits: int = 32
) -> List[Tuple[int, float]]:
    """
    Génère des hashes à partir des pics spectraux en utilisant la méthode
    des "target zones" (inspirée de Shazam).
    
    Pour chaque pic "ancre", on forme des paires avec les pics voisins dans
    une fenêtre temporelle future. Chaque paire génère un hash basé sur:
    - La fréquence du pic ancre
    - La fréquence du pic cible
    - Le delta temps entre les deux pics
    
    Args:
        peaks: Liste de tuples (time, frequency) représentant les pics
        target_zone_radius: Rayon de la zone cible en secondes
        max_freq_diff: Différence maximale de fréquence pour former une paire
        hash_bits: Nombre de bits du hash (défaut: 32)
    
    Returns:
        Liste de tuples (hash_value, anchor_time) où:
            - hash_value: Entier représentant l'empreinte
            - anchor_time: Temps du pic ancre (pour alignement temporel)
    """
    if len(peaks) < 2:
        return []
    
    # Trier les pics par temps croissant
    sorted_peaks = sorted(peaks, key=lambda x: x[0])
    
    fingerprints = []
    
    for i, anchor in enumerate(sorted_peaks):
        anchor_time, anchor_freq = anchor
        
        # Parcourir les pics suivants dans la zone cible
        for j in range(i + 1, len(sorted_peaks)):
            target = sorted_peaks[j]
            target_time, target_freq = target
            
            # Vérifier si le pic cible est dans la zone temporelle
            time_diff = target_time - anchor_time
            if time_diff > target_zone_radius:
                break  # Hors de la zone cible
            
            if time_diff <= 0:
                continue  # Doit être dans le futur
            
            # Vérifier la différence de fréquence
            freq_diff = abs(target_freq - anchor_freq)
            if freq_diff > max_freq_diff:
                continue
            
            # Créer le hash à partir des caractéristiques de la paire
            # On encode: anchor_freq, target_freq, time_diff
            hash_value = _create_hash(
                anchor_freq,
                target_freq,
                time_diff,
                hash_bits
            )
            
            fingerprints.append((hash_value, anchor_time))
    
    return fingerprints


def _create_hash(
    anchor_freq: float,
    target_freq: float,
    time_diff: float,
    hash_bits: int = 32
) -> int:
    """
    Crée un hash entier à partir des caractéristiques d'une paire de pics.
    
    Args:
        anchor_freq: Fréquence du pic ancre (Hz)
        target_freq: Fréquence du pic cible (Hz)
        time_diff: Différence de temps entre les pics (secondes)
        hash_bits: Nombre de bits du hash
    
    Returns:
        Hash entier sur hash_bits bits
    """
    # Quantification des valeurs pour créer un hash stable
    # On utilise des bins pour rendre le hash robuste aux petites variations
    
    # Bin de fréquence: 100 Hz
    freq_bin = 100.0
    anchor_bin = int(anchor_freq / freq_bin)
    target_bin = int(target_freq / freq_bin)
    
    # Bin de temps: 0.01 seconde (10 ms)
    time_bin = 0.01
    time_delta_bin = int(time_diff / time_bin)
    
    # Combinaison des valeurs en un entier unique
    # Format: [anchor_freq (10 bits)][target_freq (10 bits)][time_diff (12 bits)]
    mask_10bits = (1 << 10) - 1  # 0x3FF
    mask_12bits = (1 << 12) - 1  # 0xFFF
    
    hash_value = (
        (anchor_bin & mask_10bits) << 22 |
        (target_bin & mask_10bits) << 12 |
        (time_delta_bin & mask_12bits)
    )
    
    # Masquer pour avoir exactement hash_bits bits
    full_mask = (1 << hash_bits) - 1
    hash_value = hash_value & full_mask
    
    return hash_value
