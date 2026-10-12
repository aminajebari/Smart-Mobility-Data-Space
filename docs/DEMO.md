# Démonstration finale

## Préparation (5 min avant)

```bash
docker compose up --build -d                     # ou : python scripts/run_local.py (sans Docker)
docker compose --profile test run --rm smoke-test   # doit afficher SMOKE TEST PASSED
```

Ouvrir dans le navigateur :
- dashboard : http://localhost:8080 (sans Docker : `npm run dev` dans `feat/dashboard-devops/dashboard`
  avec `VITE_USE_MOCK_DATA=false`, puis http://localhost:5173) ;
- Swagger : http://localhost:8001/docs (API trafic), http://localhost:8010/docs (Data Space), http://localhost:8020/docs (Edge AI).

Clés de démonstration : `city-demo-key` (urbanisme, member), `startup-demo-key` (startup, guest),
`bus-demo-key` (opérateur de bus).

## Déroulé (≈ 10 min) : les 7 étapes du scénario

| # | Action | Ce qu'on montre |
|---|---|---|
| 0 | Dashboard | 4 fournisseurs connectés, 6 services en bonne santé, KPI en direct |
| 1 | `docker compose stop traffic-simulator` puis `docker compose --profile demo run --rm scenario` | le simulateur passe normal → densité croissante → incident → congestion (~70 s) |
| 2 | Courbe de trafic du dashboard | la densité monte, la zone « CONGESTION EVENT » apparaît |
| 3 | Carte « Congestion probability » | la probabilité monte **avant** l'incident (prédiction edge, ONNX) |
| 4 | Swagger trafic, `GET /data`, `dataset_id=traffic_sensor_1.congestion_forecast`, clé `city-demo-key` | le partenaire obtient la prédiction, pas les données brutes |
| 5 | Même requête avec `startup-demo-key` | 403 : « guest membership, member required » |
| 6 | Tableau « Recent data space exchanges » ou `GET :8010/audit` | autorisé et refusé tracés : qui, quoi, finalité, politique, décision |
| 7 | Dashboard | fournisseurs, indicateurs, prédiction et trace mis à jour en direct |

Puis `docker compose start traffic-simulator`.

Bonus souveraineté :
- `GET :8002/data?dataset_id=bus_line_12.passenger_counts` → 403 (politique `denied`) ;
- échange inter-fournisseurs : `GET :8002/partners/data?dataset_id=traffic_sensor_1.traffic_flow&purpose=route_optimization`
  avec `bus-demo-key` → 403, puis `POST :8002/partners/contracts` avec `traffic_management` → contrat → l'accès fonctionne ;
- `GET :8020/model-info` : métriques et benchmark ONNX.

## Plan de présentation (10 diapositives)

1. Problème : données de mobilité en silos, besoin de partage souverain.
2. Objectif et technologies imposées.
3. Acteurs et cas d'utilisation.
4. Architecture (diagramme des composants).
5. Gaia-X : politiques, contrats, audit (tableau de correspondance).
6. API distribuées : template, sécurité, échanges inter-fournisseurs.
7. Edge AI : tâche, caractéristiques, métriques vs référence, benchmark ONNX.
8. Déploiement : Docker Compose, Kubernetes (pods simulateur + API), CI.
9. Démonstration live (scénario ci-dessus).
10. Limites et perspectives.
