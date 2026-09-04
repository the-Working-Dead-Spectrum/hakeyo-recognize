# Plan de Développement — Local Music Recognition Engine (LMRE)

**Rôle du document** : plan directeur agile (Scrum) pour piloter le projet du POC jusqu'à une décision Go/No-Go de remplacement ou complément d'ARCCloud.

**Sponsor produit** : toi (Product Owner)
**Scrum Master** : ce document + moi en tant qu'assistant de pilotage
**Équipe de développement** : à définir (1 à 3 devs backend/audio selon capacité)

---

## 1. Charte de projet

### 1.1 Énoncé de vision

> Construire, mesurer et faire évoluer un moteur de reconnaissance musicale local (fingerprinting acoustique), afin de disposer de données objectives permettant de décider s'il peut réduire la dépendance à ARCCloud (coût, latence, souveraineté des données), sans jamais dégrader l'expérience utilisateur actuelle.

### 1.2 Ce que ce projet N'EST PAS
- Ce n'est **pas** un projet de remplacement immédiat d'ARCCloud.
- Ce n'est **pas** un projet d'infrastructure massive (pas de Kubernetes, pas de millions de morceaux dès le départ).
- Ce n'est **pas** un chantier "recherche pure" sans livrable mesurable : chaque sprint doit produire un incrément testable.

### 1.3 Critères de succès du projet (pas d'un sprint)
| Critère | Seuil de décision |
|---|---|
| Accuracy sur dataset ≥ 1000 morceaux | ≥ 85 % pour envisager V2, ≥ 93 % pour envisager un remplacement partiel |
| Latence moyenne | < 300 ms pour usage interactif |
| Coût par requête | Significativement < coût ARCCloud |
| Robustesse conditions dégradées | Comportement documenté et acceptable sur au moins 6 des 8 scénarios de bruit |

### 1.4 Contraintes connues
- ARCCloud reste actif en fallback à chaque étape (aucune coupure de service).
- Le projet doit rester découplé de l'application principale (pas de dépendance dure tant que la précision n'est pas validée).
- Budget d'infrastructure V0.1 : minimal (pas de Redis/Docker avant validation de l'algo).

---

## 2. Structure Agile retenue

- **Framework** : Scrum, sprints de **2 semaines**
- **Cérémonies** :
  - Sprint Planning (début de sprint, 1h)
  - Daily standup (15 min, async accepté si équipe réduite)
  - Sprint Review / démo (fin de sprint, avec mesure des métriques d'accuracy à chaque fois qu'un incrément le permet)
  - Rétrospective (fin de sprint, 30 min)
- **Definition of Ready (DoR)** : une story est prête si elle a un critère d'acceptation testable et ne dépend pas d'une story non terminée.
- **Definition of Done (DoD)** :
  1. Code revu (ou auto-revu si solo) et testé (pytest passant)
  2. Documentation minimale à jour (README ou docstring)
  3. Métrique mesurée si applicable (accuracy, latence)
  4. Aucune régression sur le fallback ARCCloud

---

## 3. Roadmap par Releases (vue macro)

```
Release V0.1 ─────────► Release V0.2 ─────────► Release V1.0 ─────────► Décision Go/No-Go
(Algo core,             (API + Queue +           (Dataset étendu +
 dataset 100)            Dashboard mesure)         tests conditions
                                                    dégradées)
   Sprint 1-2              Sprint 3-4                Sprint 5-7            Sprint 8
```

| Release | Objectif métier | Durée estimée |
|---|---|---|
| **V0.1 — Preuve de concept algorithmique** | Prouver que le fingerprinting maison fonctionne sur un petit catalogue, en local, sans API | 2 sprints (~4 sem.) |
| **V0.2 — Service exploitable + mesure** | Exposer le moteur via API, avec queue asynchrone, et un dashboard comparatif Local vs ARCCloud | 2 sprints (~4 sem.) |
| **V1.0 — Robustesse & montée en charge** | Étendre à 10 000 morceaux, tester les scénarios dégradés, fiabiliser | 3 sprints (~6 sem.) |
| **Décision** | Revue de gouvernance avec les KPIs consolidés | 1 sprint (analyse + rapport) |

---

## 4. Backlog structuré par Epics

### EPIC 1 — Moteur de Fingerprinting (cœur algorithmique)
Objectif : générer et matcher des empreintes audio fiables.

| ID | User Story | Story Points | Priorité |
|---|---|---|---|
| E1-01 | En tant que dev, je peux charger un fichier audio et générer son spectrogramme | 3 | Haute |
| E1-02 | En tant que dev, je peux extraire les pics d'énergie (peak-picking) du spectrogramme | 5 | Haute |
| E1-03 | En tant que dev, je peux générer des hash à partir de paires de pics (freq1, freq2, delta_t) | 5 | Haute |
| E1-04 | En tant que dev, je peux stocker les fingerprints en base avec index sur `hash` | 3 | Haute |
| E1-05 | En tant que dev, je peux matcher un extrait capturé contre la base et obtenir des candidats par comptage de hash | 5 | Haute |
| E1-06 | En tant que dev, je dois vérifier la cohérence temporelle des offsets (alignement constant) pour éliminer les faux positifs statistiques | 8 | **Critique** |
| E1-07 | En tant que dev, je peux calculer un score de confiance normalisé (0 à 1) | 3 | Haute |

**Total Epic 1** : ~32 points

### EPIC 2 — Persistance & Données de référence
| ID | User Story | SP | Priorité |
|---|---|---|---|
| E2-01 | Modéliser et créer les tables `tracks` et `fingerprints` (PostgreSQL) | 2 | Haute |
| E2-02 | Script d'ingestion en masse d'un dossier `music/` vers la base | 3 | Haute |
| E2-03 | Script de nettoyage / réinitialisation du dataset de test | 2 | Moyenne |

**Total Epic 2** : ~7 points

### EPIC 3 — API & Service exploitable (V0.2)
| ID | User Story | SP | Priorité |
|---|---|---|---|
| E3-01 | Endpoint `POST /recognize` (upload extrait audio → résultat JSON) | 5 | Haute |
| E3-02 | Endpoint `GET /tracks` et `POST /tracks` (gestion catalogue) | 3 | Moyenne |
| E3-03 | Intégration Redis + Worker (RQ ou Celery) pour traitement asynchrone | 5 | Moyenne |
| E3-04 | Fallback automatique vers ARCCloud si `no match` ou confiance < seuil | 5 | **Critique** |
| E3-05 | Dockerisation du service (API + worker + DB) | 3 | Moyenne |

**Total Epic 3** : ~21 points

### EPIC 4 — Mesure, Qualité & Dashboard
| ID | User Story | SP | Priorité |
|---|---|---|---|
| E4-01 | Générer automatiquement des extraits de test (3s, 5s, 10s) à partir du catalogue | 3 | Haute |
| E4-02 | Suite de tests automatisés mesurant accuracy / faux positifs / non-reconnus | 5 | **Critique** |
| E4-03 | Mesure de latence (P50, P95) et de coût par requête | 3 | Haute |
| E4-04 | Dashboard comparatif Local vs ARCCloud (accuracy, latence, coût, disponibilité offline) | 5 | Haute |
| E4-05 | Tests en conditions dégradées (bruit, voix, volume, compression, capture via haut-parleur) | 8 | Haute |

**Total Epic 4** : ~24 points

### EPIC 5 — Montée en charge du dataset (V1.0)
| ID | User Story | SP | Priorité |
|---|---|---|---|
| E5-01 | Étendre le catalogue 100 → 500 → 1000 morceaux avec mesure à chaque palier | 5 | Haute |
| E5-02 | Étendre à 10 000 morceaux, optimiser l'index de recherche si dégradation de perf | 8 | Moyenne |
| E5-03 | Rapport de synthèse final avec recommandation Go/No-Go | 3 | **Critique** |

**Total Epic 5** : ~16 points

**Total backlog estimé : ~100 points** (à ajuster après le premier sprint, une fois la vélocité réelle connue)

---

## 5. Découpage en Sprints (proposition)

> Hypothèse de vélocité initiale : ~15-18 points / sprint (2 semaines, 1-2 devs). À recalibrer après Sprint 1.

| Sprint | Objectif | Stories incluses | SP visés |
|---|---|---|---|
| **Sprint 1** | Premier pipeline fingerprint fonctionnel de bout en bout, sur ~10 morceaux, en CLI | E1-01, E1-02, E1-03, E2-01 | 13 |
| **Sprint 2** | Matching fiable + score de confiance, dataset à 100 morceaux | E1-04, E1-05, E1-06, E1-07, E2-02 | 21 → *probablement à splitter sur 2 sprints selon vélocité réelle* |
| **Sprint 3** | Exposition API minimale + fallback ARCCloud | E3-01, E3-04, E2-03 | 13 |
| **Sprint 4** | Async (Redis/Worker) + Dockerisation + début dashboard | E3-02, E3-03, E3-05, E4-01 | 17 |
| **Sprint 5** | Suite de mesure automatisée + dashboard comparatif | E4-02, E4-03, E4-04 | 13 |
| **Sprint 6** | Tests conditions dégradées + montée à 1000 morceaux | E4-05, E5-01 | 13 |
| **Sprint 7** | Montée à 10 000 morceaux + optimisation perf | E5-02 | 8 |
| **Sprint 8** | Rapport final, revue de gouvernance, recommandation | E5-03 | 3 + analyse |

*Note* : le Sprint 2 est volontairement chargé — c'est le cœur algorithmique risqué (E1-06 en particulier). Je recommande de le splitter en 2 sprints réels si l'équipe est petite, plutôt que de forcer le respect du planning.

---

## 6. Registre des risques

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| L'algo de matching génère trop de faux positifs sans vérification d'offset | Élevée | Élevé | Prioriser E1-06 dès le Sprint 2, ne pas le repousser |
| Accuracy insuffisante même à petit catalogue | Moyenne | Élevé | Tester tôt (dès 100 morceaux) plutôt qu'attendre 10 000 |
| Dérive de scope (ajout Kubernetes/microservices trop tôt) | Moyenne | Moyen | Le Scrum Master (ce plan) refuse toute story hors backlog validé |
| Dépendance cachée à ARCCloud dans le code applicatif | Faible | Élevé | E3-04 doit garder le fallback explicite et testé à chaque sprint |
| Sous-estimation du temps de labellisation du dataset de test | Élevée | Moyen | Prévoir E4-01 (génération automatique d'extraits) tôt, dès Sprint 4 |

---

## 7. Rôles proposés (si équipe > 1 personne)

| Rôle | Responsabilité |
|---|---|
| Product Owner | Toi — priorise le backlog, valide les critères Go/No-Go |
| Scrum Master | Facilite les cérémonies, protège le scope, suit la vélocité |
| Dev Audio/Algo | E1-*, E5-* (cœur fingerprinting) |
| Dev Backend/API | E2-*, E3-* (service, infra légère) |
| QA / Mesure | E4-* (peut être partagé si équipe réduite) |

Si tu es seul ou en très petite équipe : garde les epics dans cet ordre de priorité strict, ne parallélise pas E3 (API) avant que E1-06 et E1-07 soient validés — sinon tu industrialises un algo pas encore fiable.

---

## 8. KPIs suivis à chaque Sprint Review

- Accuracy cumulative sur le dataset de test courant
- Latence moyenne et P95
- Nombre de faux positifs / faux négatifs
- Vélocité réelle vs vélocité planifiée
- Taille du catalogue testé

---

## 9. Prochaine étape immédiate

Le **Sprint 1** est prêt à démarrer : pipeline fingerprint CLI sur un petit dataset (E1-01, E1-02, E1-03, E2-01), sans API, sans Redis, sans Docker.

Dis-moi si tu valides ce découpage tel quel, ou si tu veux que j'ajuste (taille des sprints, ajout/retrait de stories, équipe solo vs équipe) avant qu'on lance le Sprint 1.
