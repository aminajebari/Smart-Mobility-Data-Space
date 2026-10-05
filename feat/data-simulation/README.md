# Mobility Data & Simulation Engineer — feat/data-simulation

Simulateurs de fournisseurs de mobilité pour le Smart Mobility Data Space. Chaque provider génère localement des données réalistes conformes à un schéma JSON partagé.

## Installation
```powershell
pip install -r requirements.txt
```

## Démarrer un provider (mode continu)
```powershell
python cli.py start --provider traffic_sensor_1
python cli.py start --provider parking_lot_5
python cli.py start --provider bus_line_12
python cli.py start --provider bikes_zone_a
```
Arrêt avec `Ctrl+C`. Les données sont écrites dans `data/<provider_id>/YYYY-MM-DD.jsonl`.

## Démarrer un provider (mode batch, instantané)
```powershell
python cli.py start --provider traffic_sensor_1 --count 1000
```
Génère N lignes d'un coup (temps simulé, sans attente réelle) — utile pour les tests et le développement.

## Providers disponibles

| provider_id | Type | Intervalle |
|---|---|---|
| traffic_sensor_1 | Capteur de trafic | 5s |
| bus_line_12 | Transport public | 10s |
| parking_lot_5 | Parking intelligent | 15s |
| bikes_zone_a | Vélos/scooters partagés | 10s |

## Schéma commun
Voir `schemas/mobility_record.schema.json`. Champs de base : `provider_id`, `timestamp`, `latitude`, `longitude`, `speed`, `traffic_density`, `incident`. Champs additionnels selon le type de provider (`occupancy`, `route_id`, `delay_min`, `battery_level`, `status`).

## Comportement réactif (machine à états)
Chaque simulateur possède un état interne qui évolue tout seul, de façon probabiliste, à chaque enregistrement généré (voir `TRANSITIONS` dans chaque fichier `simulators/*.py`). Le système ne rejoue pas un script figé : il « décide » lui-même, de manière imprévisible mais réaliste, de dégrader ou d'améliorer sa situation (ex : trafic qui se dégrade progressivement vers un incident, bus qui accumule du retard, parking en affluence, flotte de vélos en faible disponibilité).

États par provider :
- `traffic_sensor.py` : `normal → buildup → incident → congestion → recovery`
- `public_transport.py` : `a_l_heure → leger_retard → retard_important → panne`
- `smart_parking.py` : `normal → affluence → presque_plein → retour_calme`
- `shared_mobility.py` : `normal → forte_demande → faible_disponibilite`

Validé automatiquement par `tests/test_reactive_behavior.py` :
- tous les états définis sont atteints sur une longue exécution
- le système ne reste jamais bloqué indéfiniment dans un état dégradé
- la distribution du temps passé dans chaque état reste réaliste (majoritairement normal)
- chaque record généré, quel que soit l'état, respecte toujours le schéma JSON commun

## Scénario de démonstration (congestion, forcé)
```powershell
python scenario/scenario_generator.py
```
Rejoue la séquence scriptée : normal → densité croissante → incident → congestion sur `traffic_sensor_1`, en ~70 secondes. Complémentaire du mode réactif : utile pour garantir un moment précis pendant la démonstration finale.

## Reproductibilité
Chaque provider a un seed fixe défini dans `config/seeds.yaml` : deux exécutions avec le même seed produisent exactement les mêmes valeurs (voir `tests/test_reproducibility.py`).

## Accès pour le Membre 2 (API distribuée)
Ne jamais lire les fichiers `data/` directement. Utiliser l'interface :
```python
from access.local_data_api import get_latest_records, get_records_since, list_available_providers
```

## Tests
```powershell
pytest tests/ -v
```
12 tests au total : schéma (3), plages de valeurs (4), reproductibilité (1), comportement réactif (4).

## Sources de référence utilisées pour calibrer les valeurs
- Trafic : profils inspirés de motifs PeMS / METR-LA (vitesse basse aux heures de pointe)
- Parking : courbe inspirée du dataset UCI « Parking Birmingham »
- Transport public : structure inspirée du standard GTFS
- Vélos/scooters : champs inspirés du standard MDS (Mobility Data Specification)