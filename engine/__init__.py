"""
Moteur de traitement audio pour LMRE.
Fournit les fonctions de chargement, spectrogramme, peak-picking et hachage.
"""

from .audio_loader import load_audio_file
from .spectrogram import compute_spectrogram
from .peak_picking import extract_peaks
from .fingerprint import generate_fingerprint

__all__ = [
    "load_audio_file",
    "compute_spectrogram",
    "extract_peaks",
    "generate_fingerprint",
]