# LMRE - Local Music Recognition Engine

## 🎯 Objectif
Développer un moteur de reconnaissance musicale local (similaire à Shazam) capable d'identifier des morceaux à partir d'un extrait audio.

## 📁 Structure du projet

```
lmre/
├── engine/              # Moteur de traitement audio
│   ├── __init__.py
│   ├── audio_loader.py  # Chargement des fichiers audio
│   ├── spectrogram.py   # Calcul du spectrogramme Mel
│   ├── peak_picking.py  # Extraction des pics spectraux
│   └── fingerprint.py   # Génération des empreintes digitales
├── storage/             # Couche de stockage
│   ├── __init__.py
│   └── database.py      # Gestion de la base de données SQLite
├── scripts/             # Scripts utilitaires CLI
│   ├── __init__.py
│   └── ingest.py        # Script d'ingestion de pistes
├── tests/               # Tests unitaires
│   ├── __init__.py
│   ├── test_engine.py   # Tests du moteur audio
│   └── test_storage.py  # Tests de la couche de stockage
├── QWEN.md              # Documentation principale
└── hakeyo-scrum.md      # Méthodologie Scrum
```

## 🚀 Installation

### Prérequis
- Python 3.11+
- pip

### Installation des dépendances

```bash
pip install librosa numpy scipy pytest soundfile
```

## 📖 Utilisation

### Ingestion de pistes audio

Pour ajouter des fichiers audio à la base de données :

```bash
cd scripts
python ingest.py /chemin/vers/morceau1.mp3 /chemin/vers/morceau2.wav --artist "Nom Artiste"
```

Options :
- `--db` : Chemin vers la base de données (défaut: `lmre.db`)
- `--title` : Titre de la piste (défaut: nom du fichier)
- `--artist` : Nom de l'artiste

### Exemple complet

```bash
# Créer la base de données et ingérer des pistes
python scripts/ingest.py music/*.mp3 --db lmre.db

# Vérifier le contenu
sqlite3 lmre.db "SELECT COUNT(*) FROM tracks;"
sqlite3 lmre.db "SELECT COUNT(*) FROM fingerprints;"
```

## 🧪 Tests

Lancer tous les tests :

```bash
pytest tests/ -v
```

Lancer les tests du moteur audio :

```bash
pytest tests/test_engine.py -v
```

Lancer les tests de la base de données :

```bash
pytest tests/test_storage.py -v
```

## 📊 Sprint 1 (V0.1) - Stories implémentées

| Story | Description | Statut |
|-------|-------------|--------|
| E1-01 | Chargement audio + spectrogramme | ✅ |
| E1-02 | Extraction des pics (peak-picking) | ✅ |
| E1-03 | Génération de hash à partir des pics | ✅ |
| E2-01 | Création des tables tracks et fingerprints | ✅ |

## 🔧 Architecture technique

### Pipeline de fingerprinting

1. **Chargement** : Lecture du fichier audio et conversion en mono (44.1 kHz)
2. **Spectrogramme** : Calcul du spectrogramme Mel (128 bandes, échelle logarithmique)
3. **Peak-picking** : Détection des maxima locaux dans le spectrogramme
4. **Fingerprinting** : Génération de hashes à partir des paires de pics (méthode "target zones")
5. **Stockage** : Insertion des empreintes dans SQLite avec indexation

### Base de données

**Table `tracks`** :
- `id` : Identifiant unique
- `title` : Titre de la piste
- `artist` : Artiste
- `album` : Album
- `file_path` : Chemin unique vers le fichier
- `duration` : Durée en secondes

**Table `fingerprints`** :
- `id` : Identifiant unique
- `hash_value` : Empreinte digitale (entier 32 bits)
- `anchor_time` : Temps du pic ancre (secondes)
- `track_id` : Clé étrangère vers `tracks`

## 📝 Prochaines étapes (Sprint 2)

- [ ] Implémenter l'algorithme de matching (recherche par hash)
- [ ] Créer un script CLI de reconnaissance (`recognize.py`)
- [ ] Ajouter des tests d'intégration end-to-end
- [ ] Documenter les paramètres algorithmiques (taille des target zones, etc.)

## 📄 Références

- [QWEN.md](QWEN.md) - Documentation détaillée du projet
- [hakeyo-scrum.md](hakeyo-scrum.md) - Plan de développement Scrum
