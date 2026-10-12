# Rapport final : Smart Mobility Data Space

*Data Spaces Engineering and Distributed AI Systems, projet 3*

## 1. Contexte et objectif

Les données de mobilité d'une ville (bus, capteurs routiers, parkings, vélos) sont dispersées entre
organismes qui ne veulent pas en perdre le contrôle. Le projet réalise un prototype de **Data Space**
inspiré de Gaia-X. Chaque fournisseur garde ses données localement, les expose par une API contrôlée,
les partage selon des politiques d'usage tracées, et un nœud **Edge AI** prédit les embouteillages
localement en ne partageant que ses résultats.

## 2. Architecture

Voir [ARCHITECTURE.md](ARCHITECTURE.md) (acteurs, cas d'utilisation, diagramme des composants, séquence).
Cinq modules indépendants, un par membre et par branche, communiquent uniquement par des API REST
documentées ([shared/API_CONTRACTS.md](../shared/API_CONTRACTS.md)).

| Module | Branche | Réalisation |
|---|---|---|
| 1. Simulation | `feat/data-simulation` | 4 simulateurs à états (trafic, bus, parking, vélos), seeds déterministes, scénario de congestion, schéma JSON, API d'accès locale |
| 2. API distribuées | `feat/distributed-api` | template FastAPI instancié par fournisseur : `/data` (filtres temps, incident, position), `/datasets`, `/publish`, `/search`, `/logs`, échanges inter-fournisseurs, clés API, journal des requêtes |
| 3. Data Space | `feat/data-space` | registre de 8 participants, catalogue de 6 jeux (métadonnées), 5 types de politiques, contrats, service de décision `/authorize`, journal d'audit SQLite |
| 4. Edge AI | `feat/edge-ai` | prédiction de congestion (random forest → ONNX), service `/predict` `/model-info`, boucle edge pull → prédiction → publication |
| 5. Dashboard & DevOps | `feat/dashboard-devops` | dashboard React branché sur une API d'agrégation, 6 images Docker, docker-compose, manifestes Kubernetes, smoke test, CI |

## 3. Fonctionnalités par exigence du sujet

| Exigence | Réalisation |
|---|---|
| Fournisseurs simulés, données locales | 4 fournisseurs, un dossier (ou volume / pod) chacun |
| Vitesse, densité, occupation, horaires, incidents, géolocalisation | champs du schéma commun selon le type de fournisseur |
| Publier des données | `POST /publish` (jeux dérivés) + auto-publication de l'offre au catalogue |
| Consulter des données autorisées | `GET /data`, décision du Data Space avant chaque réponse |
| Rechercher des jeux de données | `GET /search` (local ou fédéré), `GET /catalogue?q=` |
| Contrôler les accès | clés API → participant ; politiques public / partner_only / role_based / purpose_limited / denied ; contrats |
| Journaliser les requêtes | journal de requêtes par API + journal d'audit central |
| OpenAPI / Swagger | `/docs` sur chaque service |
| Principes Gaia-X | voir ARCHITECTURE.md §7 |
| Edge AI | modèle ONNX exécuté sur le nœud, seuls les résultats sont publiés |
| Tableau de bord | fournisseurs, santé des API, données simulées (KPI, courbe), prédictions, indicateurs, échanges |
| Docker, Kubernetes | Dockerfiles, compose, manifestes Minikube/Kind avec sondes et ConfigMap/Secret |

## 4. Edge AI : évaluation

Tâche : prédire qu'une congestion (incident signalé par le capteur) surviendra dans les 6 prochaines
mesures, à partir d'une fenêtre de 6 mesures (12 caractéristiques). Données : 3 jours simulés
(51 840 mesures), découpage chronologique 80/20.

| Modèle | Exactitude | Précision | Rappel | F1 | ROC-AUC |
|---|---|---|---|---|---|
| Random forest (ONNX) | 0,843 | 0,554 | 0,825 | **0,663** | **0,863** |
| Régression logistique | 0,834 | 0,537 | 0,827 | 0,651 | 0,854 |
| Persistance (« incident maintenant ») | 0,866 | 0,792 | 0,387 | 0,520 | n/a |

Le modèle détecte 83 % des congestions à venir contre 39 % pour la référence naïve. Il anticipe donc le
début de la congestion. La précision limitée vient du caractère aléatoire des transitions d'état du simulateur.

| Benchmark (CPU) | scikit-learn | ONNX Runtime |
|---|---|---|
| Taille du modèle | 2,9 Mo | 1,2 Mo |
| Une prédiction (moyenne) | 17,2 ms | 0,085 ms |
| Lot de 1000 (moyenne) | 28,9 ms | 33,8 ms |

Écart maximal de probabilité entre les deux formats : 3,5·10⁻⁷. Le nœud edge fait une prédiction
toutes les quelques secondes : c'est la latence unitaire qui compte.

## 5. Validation

| Niveau | Contenu | Résultat |
|---|---|---|
| Tests unitaires / API | Module 1 : 12 · Module 2 : 16 · Module 3 : 17 · Module 4 : 7 · API dashboard : 4 | tous réussis |
| Intégration en processus | `tests/integration/test_end_to_end.py` : les 7 étapes du scénario avec les vraies applications | réussi |
| Smoke test système | `scripts/smoke_test.py` sur les 7 services lancés (`scripts/run_local.py`) : 28 vérifications | réussi |
| Tests frontend | `npm test` (rendu mock, plages de congestion) | exécutés par la CI |
| Docker / Kubernetes | `docker compose --profile test run --rm smoke-test`, Job `smoke-test` | exécutés par la CI (compose) ; Kubernetes à valider sur Minikube |

Scénario forcé (`scenario_generator.py`) observé sur le système en fonctionnement, relevé toutes les ~6 s :

| Phase | Vitesse | Densité | Incident | Probabilité prédite | Niveau |
|---|---|---|---|---|---|
| normal | 52,6 | 0,26 | non | 0,27 | moderate |
| densité croissante | 36,7 | 0,44 | non | **0,78** | heavy |
| incident | 12,0 | 0,75 | oui | 0,98 | severe |
| congestion | 1,6 | 0,85 | oui | 0,94 | severe |
| retour (simulateur réactif) | 31,0 | 0,16 | non | 0,05 | free_flow |

La probabilité dépasse 0,5 pendant la phase de densité croissante, **avant** que le capteur ne signale l'incident.

## 6. Sécurité et souveraineté : scénarios vérifiés

- Une startup *guest* peut lire les jeux publics (parking, bus), mais n'obtient ni la prévision
  (partner_only) ni les données brutes de trafic à des fins commerciales (403, tracé).
- Les comptages de passagers (`denied`) ne sortent jamais du fournisseur.
- Le nœud edge est refusé tant qu'il n'a pas de contrat, puis autorisé après négociation.
- Le bus ne peut pas obtenir de contrat pour la finalité `route_optimization` (non prévue par la politique du
  trafic). Il l'obtient pour `traffic_management` et récupère alors les données via découverte catalogue.
- Si le service de gouvernance tombe, les API refusent de servir (fail-closed).
- Révoquer un contrat coupe immédiatement l'accès.

## 7. Limites et perspectives

- **Identité simplifiée** : clés API partagées au lieu de credentials vérifiables Gaia-X (DID/VC) et
  d'un connecteur type Eclipse Dataspace Components.
- **Gouvernance centralisée** : un seul service de décision ; un vrai Data Space fédère plusieurs catalogues.
- **Politiques non exécutoires après livraison** : rétention et non-redistribution sont inscrites au
  contrat mais pas techniquement imposées chez le consommateur.
- **Données simulées** : le modèle est entraîné sur le simulateur ; il faudrait le réentraîner sur des
  données réelles (PeMS, METR-LA) et évaluer d'autres horizons.
- **Stockage** : JSONL et SQLite suffisent pour la démonstration ; PostgreSQL/MongoDB pour la montée en charge.
- **Temps de trajet** : estimation heuristique (corridor / vitesse moyenne), pas apprise.
