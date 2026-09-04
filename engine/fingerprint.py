"""
Génération des empreintes digitales (fingerprinting).
Story E1-03 : Génération de hash à partir des pics

Conforme à la spécification QWEN.md Section 4, Étapes 3-4.
"""

import numpy as np
from typing import List, Tuple, Dict
from .config import FingerprintConfig


def generate_fingerprint(
    peaks: List[Tuple[float, float]],
    config: FingerprintConfig = None,
) -> List[Tuple[int, float]]:
    """
    Génère des hashes à partir des pics spectraux en utilisant la méthode
    des "target zones" (inspirée de Shazam).
    
    Pour chaque pic "ancre", on forme des paires avec les pics voisins dans
    une fenêtre temporelle future (zone cible). Chaque paire génère un hash 
    basé sur:
    - La fréquence du pic ancre
    - La fréquence du pic cible
    - Le delta temps entre les deux pics
    
    Args:
        peaks: Liste de tuples (time, frequency) représentant les pics
        config: Configuration pour les paramètres de fingerprinting
        
    Returns:
        Liste de tuples (hash_value, anchor_time) où:
            - hash_value: Entier représentant l'empreinte (64 bits)
            - anchor_time: Temps du pic ancre (pour alignement temporel)
    
    Raises:
        ValueError: Si peaks est None
    """
    if peaks is None:
        raise ValueError("peaks ne peut pas être None")
    
    if len(peaks) < 2:
        return []
    
    # Utiliser la configuration par défaut si non fournie
    if config is None:
        config = FingerprintConfig()
    
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
            if time_diff > config.target_zone_duration:
                break  # Hors de la zone cible (~5s selon spec)
            
            if time_diff <= 0:
                continue  # Doit être dans le futur
            
            # Vérifier la différence de fréquence
            freq_diff = abs(target_freq - anchor_freq)
            if freq_diff > config.max_freq_diff:
                continue
            
            # Créer le hash à partir des caractéristiques de la paire
            hash_value = _create_hash(
                anchor_freq,
                target_freq,
                time_diff,
                config
            )
            
            fingerprints.append((hash_value, anchor_time))
    
    return fingerprints


def _create_hash(
    anchor_freq: float,
    target_freq: float,
    time_diff: float,
    config: FingerprintConfig
) -> int:
    """
    Crée un hash entier à partir des caractéristiques d'une paire de pics.
    
    Algorithme conforme à QWEN.md Section 4, Étape 3:
    hash = f(freq_ancre, freq_cible, delta_t)
    
    Args:
        anchor_freq: Fréquence du pic ancre (Hz)
        target_freq: Fréquence du pic cible (Hz)
        time_diff: Différence de temps entre les pics (secondes)
        config: Configuration pour les paramètres de quantification
        
    Returns:
        Hash entier sur config.hash_bits bits (défaut: 64 bits)
        
    Justification technique:
        - Quantification par bins pour robustesse aux petites variations
        - 64 bits pour réduire les collisions statistiques
        - Format: [anchor_freq (20 bits)][target_freq (20 bits)][time_diff (24 bits)]
    """
    # Quantification des valeurs pour créer un hash stable
    # Les bins rendent le hash robuste aux petites variations de timing/fréquence
    
    anchor_bin = int(anchor_freq / config.freq_bin)
    target_bin = int(target_freq / config.freq_bin)
    
    # Bin de temps selon config (défaut: 10ms)
    time_delta_bin = int(time_diff / config.time_bin)
    
    # Combinaison des valeurs en un entier unique sur 64 bits
    # Format: [anchor_freq (20 bits)][target_freq (20 bits)][time_diff (24 bits)]
    # Cela permet:
    #   - Fréquences jusqu'à ~100 kHz avec résolution 100 Hz
    #   - Delta temps jusqu'à ~167 secondes avec résolution 10ms
    
    mask_20bits = (1 << 20) - 1  # 0xFFFFF
    mask_24bits = (1 << 24) - 1  # 0xFFFFFF
    
    hash_value = (
        (anchor_bin & mask_20bits) << 44 |
        (target_bin & mask_20bits) << 24 |
        (time_delta_bin & mask_24bits)
    )
    
    # Masquer pour avoir exactement hash_bits bits
    if config.hash_bits < 64:
        full_mask = (1 << config.hash_bits) - 1
        hash_value = hash_value & full_mask
    
    return hash_value
