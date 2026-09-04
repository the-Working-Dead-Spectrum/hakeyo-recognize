# QWEN.md — Local Music Recognition Engine (LMRE)

Ce fichier est la **référence de contexte** pour toute session de QWEN Code sur ce projet.
Il doit être lu avant toute génération de code. Toute story implémentée doit rester cohérente avec ce document.

---

## 1. Mission du projet (à ne jamais perdre de vue)

Construire un moteur de reconnaissance musicale **local** (fingerprinting acoustique type Shazam), afin de mesurer objectivement s'il peut réduire la dépendance à **ARCCloud** (service de reconnaissance tiers actuellement utilisé en production).

**Ce projet n'est PAS un remplacement immédiat d'ARCCloud.** ARCCloud reste le fallback obligatoire tant que la précision du moteur local n'est pas validée par les métriques définies dans le plan de sprint.

### Non-objectifs explicites (ne pas implémenter sans validation du Product Owner)
- Pas de Kubernetes, pas de microservices multiples.
- Pas de Redis/Celery/Docker avant que l'algorithme de fingerprinting soit validé en local (voir phase du sprint courant, section 8).
- Pas de scaling à 1 million de morceaux dès le départ. Le dataset croît par paliers : 100 → 500 → 1000 → 10 000.
- Pas de suppression ou de contournement du fallback ARCCloud, jamais, à aucun sprint.

Si une tâche demandée semble sortir de ces limites, le code doit signaler l'écart plutôt que l'implémenter silencieusement.

---

## 2. Architecture cible (vue d'ensemble, ne pas tout construire dès le sprint 1)

```
APPLICATION
     │
     ▼
 FastAPI (V0.2+, pas V0.1)
     │
     ▼
 Redis Queue (V0.2+)
     │
     ▼
 Worker (V0.2+)
     │
     ▼
 Fingerprint Engine (coeur du projet, V0.1)
     │
     ├──► Fingerprint DB (table `fingerprints`, PostgreSQL)
     └──► PostgreSQL (table `tracks`)
     │
     ▼
 Matching (avec vérification d'alignement temporel — voir section 4)
     │
  ┌──┴──┐
  ▼     ▼
MATCH  NO MATCH
  │       │
  ▼       ▼
RESULT  ARCCloud (fallback)
```

**En V0.1 (sprint courant), seule la partie "Fingerprint Engine + DB + Matching" existe, en script Python exécutable en CLI, sans API.**

---

## 3. Stack technique

| Composant | Choix | Statut |
|---|---|---|
| Langage | Python 3.11+ | V0.1 |
| Traitement audio | librosa, numpy, scipy | V0.1 |
| Base de données | PostgreSQL (SQLite acceptable en dev local uniquement) | V0.1 |
| Tests | pytest | V0.1 |
| API | FastAPI | V0.2 |
| Queue | Redis + RQ (préféré à Celery pour la simplicité) | V0.2 |
| Conteneurisation | Docker / docker-compose | V0.2 |

**Ne pas introduire de dépendance hors de cette liste sans justification explicite dans le message de commit.**

---

## 4. Spécification de l'algorithme de fingerprinting (cœur critique du projet)

C'est la partie la plus sensible du projet. Toute implémentation doit suivre ces étapes précisément — c'est ce qui distingue un vrai algo de type Shazam d'un simple comparateur de hash naïf produisant des faux positifs.

### Étape 1 — Spectrogramme
- Charger l'audio en mono, resampler à une fréquence fixe (ex. 11025 Hz, configurable).
- Calculer un spectrogramme via STFT (`scipy.signal.stft` ou équivalent librosa).

### Étape 2 — Extraction des pics (peak-picking)
- Identifier les points d'énergie locale maximale dans le spectrogramme (fenêtre temps/fréquence configurable).
- Limiter la densité de pics par bin temporel pour éviter l'explosion combinatoire.

### Étape 3 — Génération des hash (empreintes)
Pour chaque pic "ancre", on l'associe à un ou plusieurs pics "cibles" dans une fenêtre temporelle suivante (zone cible), et on génère un hash à partir de :
```
hash = f(freq_ancre, freq_cible, delta_t)
```
- `delta_t` = différence de temps entre les deux pics (doit être borné, ex. 0 à ~5s).
- Le hash est stocké avec le timestamp absolu du pic ancre (`offset`).

### Étape 4 — Stockage
Table `fingerprints(hash, track_id, offset)`, indexée sur `hash` (voir section 5).

### Étape 5 — Matching (partie CRITIQUE — ne jamais l'omettre)
1. Générer les fingerprints de l'extrait capturé.
2. Chercher tous les `track_id` candidats par correspondance de `hash`.
3. **Obligatoire : pour chaque candidat, calculer `delta_offset = offset_track - offset_capture` pour chaque hash matché, puis construire un histogramme de ces `delta_offset`.**
4. Le vrai match est le track dont l'histogramme présente un pic net (beaucoup de hash partagent le même `delta_offset`) — pas simplement le track avec le plus de hash en commun.
5. Un simple comptage de hash matchés SANS cette vérification d'alignement temporel est un anti-pattern à corriger si détecté dans le code — il génère des faux positifs statistiques.

### Étape 6 — Score de confiance
- Normaliser le pic de l'histogramme (nombre de hash alignés au meilleur `delta_offset`) par rapport au nombre total de fingerprints générés depuis la capture.
- Retourner une valeur entre 0 et 1.
- Définir un seuil de décision (`CONFIDENCE_THRESHOLD`, configurable, valeur de départ suggérée : 0.15 à ajuster empiriquement) sous lequel le système déclare `no match` et bascule vers ARCCloud.

---

## 5. Schéma de données

```sql
CREATE TABLE tracks (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    artist TEXT,
    album TEXT,
    duration FLOAT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE fingerprints (
    id BIGSERIAL PRIMARY KEY,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    hash TEXT NOT NULL,
    offset FLOAT NOT NULL
);

CREATE INDEX idx_fingerprint_hash ON fingerprints(hash);
```

L'index sur `hash` est non négociable — sans lui, le matching devient inutilisable au-delà de quelques centaines de morceaux.

---

## 6. Contrat d'API (à respecter dès l'implémentation de la V0.2)

### `POST /recognize`
**Entrée** : fichier audio (5–15s)
**Sortie** :
```json
{
  "match": true,
  "track_id": 123,
  "title": "Titre",
  "artist": "Artiste",
  "confidence": 0.94,
  "processing_time_ms": 183,
  "source": "local"
}
```
- Si `confidence < CONFIDENCE_THRESHOLD` → `match: false` → appel automatique au fallback ARCCloud, et `source` devient `"arccloud"` dans la réponse finale si celui-ci trouve un résultat.

### `GET /tracks`, `POST /tracks`
Gestion basique du catalogue de référence (CRUD minimal, pas de pagination avancée en V0.2).

---

## 7. Conventions de code

- Style : PEP8, formaté avec `black`, imports triés avec `isort`.
- Typage : type hints obligatoires sur toutes les fonctions publiques.
- Tests : chaque fonction de la section 4 (peak-picking, hashing, matching, scoring) doit avoir un test unitaire dédié dans `tests/`.
- Pas de logique métier dans les endpoints FastAPI — déléguer à des modules `engine/`, `matching/`, `storage/`.
- Config via variables d'environnement (`.env`), jamais de valeurs sensibles en dur (clé ARCCloud, credentials DB).
- Structure de dossiers suggérée :
```
lmre/
├── engine/          # spectrogramme, peak-picking, hashing
├── matching/         # recherche candidats, alignement offset, scoring
├── storage/          # accès DB (tracks, fingerprints)
├── api/              # FastAPI (V0.2+)
├── fallback/          # intégration ARCCloud
├── scripts/           # ingestion dataset, génération d'extraits de test
├── tests/
└── QWEN.md
```

---

## 8. Sprint courant : ce que QWEN Code doit implémenter MAINTENANT

**Sprint 1 (V0.1)** — pipeline CLI de bout en bout, sans API, sans Redis, sans Docker :
- E1-01 : chargement audio + génération spectrogramme
- E1-02 : peak-picking
- E1-03 : génération de hash (freq1, freq2, delta_t)
- E2-01 : tables `tracks` / `fingerprints` en PostgreSQL (ou SQLite en dev)

**Ne pas anticiper le Sprint 2+** (matching avec vérification d'offset, score de confiance) tant que le Sprint 1 n'est pas validé par des tests — sauf si explicitement demandé.

---

## 9. Definition of Done (rappel, applicable à chaque story)

1. Tests unitaires passants (`pytest`).
2. Documentation minimale (docstrings + README à jour si nouvelle commande CLI).
3. Métrique mesurée si applicable (accuracy, latence) et rapportée dans le message de fin de tâche.
4. Aucune régression sur le fallback ARCCloud existant.
5. Aucun ajout de dépendance hors section 3 sans justification.

---

## 10. Comportement attendu de QWEN Code

- Si une demande implique de sauter une étape critique de la section 4 (en particulier l'alignement temporel des offsets), signaler le risque avant d'implémenter une version simplifiée.
- Si une demande introduit une techno hors stack (section 3) ou une story hors sprint courant (section 8), le signaler explicitement plutôt que de l'implémenter silencieusement.
- Toujours proposer un test mesurable (accuracy/latence) quand le composant livré s'y prête.
