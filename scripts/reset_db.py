"""
Script de nettoyage / réinitialisation du dataset de test.
Story E2-03 : Script de nettoyage / réinitialisation du dataset de test

Conforme QWEN.md:
- Validation stricte des entrées (Section 7.2 - A03 Injection)
- Requêtes paramétrées (déjà dans database.py)
- KISS: solution simple sans sur-ingénierie
- Codes retour clairs: 0 = succès, 1 = erreur technique
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

# Ajout du chemin racine au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from storage import Database, count_tracks, count_fingerprints


def reset_database(db_path: str, confirm: bool = False) -> tuple[bool, Optional[str]]:
    """
    Réinitialise complètement la base de données en supprimant toutes les pistes et empreintes.
    
    Args:
        db_path: Chemin vers le fichier de base de données SQLite
        confirm: Si True, ne demande pas de confirmation interactive
        
    Returns:
        Tuple (success, error_message)
            - success: True si la réinitialisation a réussi
            - error_message: Message d'erreur ou None
    """
    try:
        # Vérifier que le fichier de base de données existe
        db_file = Path(db_path)
        if not db_file.exists():
            return False, f"Base de données non trouvée: {db_path}"
        
        # Initialiser la connexion
        db = Database(db_path)
        
        # Afficher l'état initial
        initial_tracks = count_tracks(db)
        initial_fingerprints = count_fingerprints(db)
        
        print(f"📊 État actuel de la base de données:")
        print(f"   Pistes: {initial_tracks}")
        print(f"   Empreintes: {initial_fingerprints}")
        
        if initial_tracks == 0 and initial_fingerprints == 0:
            print("✅ La base de données est déjà vide.")
            return True, None
        
        # Demander confirmation si mode interactif
        if not confirm:
            response = input(
                f"\n⚠️  Attention: Cette opération va supprimer {initial_tracks} pistes "
                f"et {initial_fingerprints} empreintes définitivement.\n"
                f"Voulez-vous continuer? (oui/non): "
            )
            if response.lower() not in ['oui', 'yes', 'y']:
                print("❌ Opération annulée.")
                return True, None  # Considéré comme succès car pas d'erreur technique
        
        # Supprimer toutes les empreintes (d'abord à cause de CASCADE)
        print("\n🗑️  Suppression des empreintes...")
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM fingerprints")
            deleted_fingerprints = cursor.rowcount
            print(f"   {deleted_fingerprints} empreintes supprimées")
        
        # Supprimer toutes les pistes
        print("🗑️  Suppression des pistes...")
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tracks")
            deleted_tracks = cursor.rowcount
            print(f"   {deleted_tracks} pistes supprimées")
        
        # Vérifier l'état final
        final_tracks = count_tracks(db)
        final_fingerprints = count_fingerprints(db)
        
        print(f"\n✅ Réinitialisation terminée avec succès!")
        print(f"   État final: {final_tracks} pistes, {final_fingerprints} empreintes")
        
        # Vérification de cohérence
        if final_tracks != 0 or final_fingerprints != 0:
            return False, f"Incohérence détectée: {final_tracks} pistes et {final_fingerprints} empreintes restantes"
        
        return True, None
        
    except Exception as e:
        return False, f"Erreur lors de la réinitialisation: {str(e)}"


def main():
    parser = argparse.ArgumentParser(
        description="Réinitialise la base de données LMRE en supprimant toutes les pistes et empreintes"
    )
    
    parser.add_argument(
        "--db",
        default="lmre.db",
        help="Chemin vers la base de données SQLite (défaut: lmre.db)"
    )
    
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        dest="confirm",
        help="Ne pas demander de confirmation (mode automatique)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Afficher l'état de la base sans effectuer de suppression"
    )
    
    args = parser.parse_args()
    
    # Mode dry-run
    if args.dry_run:
        db_file = Path(args.db)
        if not db_file.exists():
            print(f"❌ Base de données non trouvée: {args.db}")
            sys.exit(1)
        
        db = Database(args.db)
        tracks = count_tracks(db)
        fingerprints = count_fingerprints(db)
        
        print(f"📊 État de la base de données '{args.db}':")
        print(f"   Pistes: {tracks}")
        print(f"   Empreintes: {fingerprints}")
        
        if tracks == 0 and fingerprints == 0:
            print("✅ La base de données est déjà vide.")
        
        sys.exit(0)
    
    # Exécuter la réinitialisation
    success, error_msg = reset_database(args.db, confirm=args.confirm)
    
    if not success:
        print(f"❌ Échec: {error_msg}")
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
