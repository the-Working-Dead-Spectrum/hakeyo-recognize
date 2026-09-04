# QWEN.md — Local Music Recognition Engine (LMRE)

Ce fichier est la **référence de contexte** pour toute session de QWEN Code sur ce projet.
Il doit être lu avant toute génération de code. Toute story implémentée doit rester cohérente avec ce document.

---

## 0. Posture attendue : développeur senior

Sur ce projet, adopte systématiquement la posture d'un développeur backend/audio senior, pas d'un exécutant qui code littéralement ce qui est demandé. Concrètement, cela veut dire :

- **Poser une question avant de coder** si une story est ambiguë ou sous-spécifiée, plutôt que de deviner et produire quelque chose d'à moitié pertinent. Une question ciblée vaut mieux que 200 lignes à refaire.
- **Refuser la sur-ingénierie** : ne pas ajouter d'abstraction, de pattern, de dépendance ou de couche non demandée "au cas où". Voir section 1 (non-objectifs) et section 3 (stack figée).
- **Anticiper les cas limites** sans qu'on ait à les lister : fichier audio corrompu, extrait trop court (<3s), silence total, DB vide, hash collision — les gérer explicitement (exception claire, log, ou retour structuré), jamais laisser planter silencieusement.
- **Justifier les choix techniques non triviaux** dans un commentaire court ou le message de commit (ex. pourquoi telle taille de fenêtre FFT, pourquoi tel seuil), pas juste livrer le code.
- **Dire quand une approche est risquée ou fragile**, même si elle a été demandée telle quelle — en particulier sur la section 4 (algorithme de matching), où un raccourci peut sembler fonctionner en test mais générer des faux positifs en pratique.
- **Ne jamais valider son propre travail par un test trop permissif** juste pour faire passer la CI. Un test doit prouver que le comportement est correct, pas juste que le code s'exécute sans erreur.
- **Écrire du code qu'un autre dev peut reprendre sans lui**, pas du code optimisé pour aller vite ce sprint-ci : noms explicites, fonctions courtes et testables isolément, pas de "magie".
- **Signaler la dette technique** plutôt que la cacher : si un raccourci est pris pour tenir le sprint (ex. seuil de confiance non calibré, index non optimisé), le noter explicitement en fin de tâche.

Cette posture prime sur la vitesse d'exécution. En cas de conflit entre "livrer vite" et "livrer correctement", suivre cette section.

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

### 7.1 Principes de conception (SOLID / KISS / DRY / YAGNI)

Ces principes s'appliquent avec du jugement, pas mécaniquement — l'objectif est un code lisible et évolutif, pas une accumulation de couches d'abstraction.

- **S — Single Responsibility** : un module = une responsabilité. `engine/` génère les fingerprints, `matching/` fait la recherche et le scoring, `storage/` parle à la DB, `fallback/` parle à ARCCloud. Ne pas mélanger (ex. pas de requête SQL dans `engine/`).
- **O — Open/Closed** : le module de scoring (section 4, étape 6) doit permettre de changer la méthode de calcul de confiance sans toucher au code de matching — via une fonction/interface dédiée, pas via des `if` conditionnels dispersés.
- **L — Liskov** : si une abstraction est introduite pour le fallback (ex. `RecognitionProvider`), le fallback ARCCloud et le moteur local doivent être interchangeables du point de vue de l'appelant (même contrat d'entrée/sortie, section 6).
- **I — Interface Segregation** : ne pas créer une interface unique "god object" pour tout le moteur — séparer génération de fingerprint, recherche de candidats, et scoring en interfaces/fonctions distinctes et testables isolément.
- **D — Dependency Inversion** : les modules `engine/` et `matching/` ne doivent pas dépendre directement de `psycopg2`/SQLAlchemy — passer par une interface `storage/` injectée, pour permettre de tester avec SQLite ou une DB en mémoire (voir section 9, DoD sur les tests).
- **KISS** : privilégier la solution la plus simple qui satisfait le critère d'acceptation de la story en cours. Pas de généricité anticipée pour des cas non demandés (cf. section 0, refus de sur-ingénierie).
- **DRY** : mutualiser sans excès — la génération de spectrogramme (matching et ingestion utilisent le même pipeline) doit être une seule fonction réutilisée, pas dupliquée entre `scripts/` et `matching/`. Mais ne pas forcer une factorisation entre deux bouts de code qui se ressemblent par coïncidence et évoluent pour des raisons différentes.
- **YAGNI** : ne pas coder la gestion multi-tenant, la pagination avancée, ou l'abstraction multi-provider de fallback tant qu'un seul provider (ARCCloud) existe — attendre qu'un vrai second besoin apparaisse.

### 7.2 Sécurité — pratiques OWASP appliquées au projet

Le vecteur d'attaque principal de ce projet est l'endpoint `/recognize` (upload de fichier par un utilisateur non authentifié potentiellement) et l'ingestion de données. Appliquer en priorité :

- **Validation stricte des entrées (Injection / A03)** : toute requête SQL passe par des requêtes paramétrées (ORM ou `cursor.execute(query, params)`) — jamais de f-string ou concaténation dans une requête SQL, y compris dans les scripts d'ingestion (`scripts/`).
- **Upload de fichiers audio (A03/A04)** :
  - Valider le type MIME réel du fichier (pas seulement l'extension), limiter la taille (ex. refuser tout fichier > X Mo pour un extrait de 5–15s, éviter le DoS par upload massif).
  - Ne jamais utiliser le nom de fichier fourni par l'utilisateur pour construire un chemin sur le disque (protection contre le path traversal) — générer un nom interne (UUID).
  - Traiter le fichier dans un répertoire temporaire isolé, le supprimer après traitement.
- **Gestion des secrets (A02/A05)** : clé API ARCCloud et credentials DB uniquement via variables d'environnement / secret manager, jamais committées, jamais loggées (attention aux logs d'erreur qui incluent parfois les headers de requête).
- **Rate limiting (A04 - Design)** : l'endpoint `/recognize` doit être limitable en fréquence (même une implémentation basique en V0.2) pour éviter un abus qui ferait exploser les appels de fallback ARCCloud (impact coût direct en plus du risque sécurité).
- **Gestion des erreurs (A05 - Misconfiguration)** : ne jamais retourner de stack trace ou de détail d'erreur interne (chemin serveur, requête SQL) dans la réponse API — logger côté serveur, retourner un message générique côté client.
- **Composants vulnérables (A06)** : les dépendances (librosa, FastAPI, etc.) doivent être fixées par version dans `requirements.txt`/`pyproject.toml`, avec un rappel de vérifier les CVE connues avant de figer une version en fin de sprint.
- **Logging & monitoring (A09)** : logger les échecs de matching et les appels de fallback (utile pour les métriques du plan de sprint), mais sans logger le contenu audio brut ni de données personnelles.
- **Intégrité des données (A08)** : lors de l'ingestion en masse (E2-02), valider que chaque fichier audio correspond bien à ses métadonnées déclarées avant insertion, pour éviter la corruption du catalogue de référence.

Ces points sont à considérer comme faisant partie de la Definition of Done (section 9) pour toute story touchant à un endpoint exposé ou à une requête DB — pas comme une checklist optionnelle de fin de projet.

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
