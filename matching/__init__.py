"""
Matching Engine - Local Music Recognition
Module de matching acoustique avec vérification d'alignement temporel.
Implémente l'étape 5 de la spécification (QWEN.md Section 4).
"""

from .histogram import build_offset_histogram, find_best_match
from .matcher import Matcher, MatchResult

__all__ = ['Matcher', 'MatchResult', 'build_offset_histogram', 'find_best_match']
