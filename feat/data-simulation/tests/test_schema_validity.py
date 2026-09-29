import json
from pathlib import Path
import jsonschema
import pytest

# Chemin vers le schéma (à la racine du module feat/data-simulation)
SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "mobility_record.schema.json"

with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    SCHEMA = json.load(f)

# Un exemple de record valide (capteur de trafic)
VALID_RECORD = {
    "provider_id": "traffic_sensor_1",
    "timestamp": "2026-09-15T10:30:00",
    "latitude": 36.8065,
    "longitude": 10.1815,
    "speed": 24.5,
    "traffic_density": 0.78,
    "incident": False,
}

# Un exemple de record invalide (density hors limites, speed négative)
INVALID_RECORD = {
    "provider_id": "traffic_sensor_1",
    "timestamp": "2026-09-15T10:30:00",
    "latitude": 36.8065,
    "longitude": 10.1815,
    "speed": -5,
    "traffic_density": 1.5,
    "incident": False,
}


def test_valid_record_passes():
    """Un record correct ne doit lever aucune erreur."""
    jsonschema.validate(instance=VALID_RECORD, schema=SCHEMA)


def test_invalid_record_fails():
    """Un record hors des bornes doit être rejeté."""
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=INVALID_RECORD, schema=SCHEMA)


def test_missing_required_field_fails():
    """Un champ obligatoire manquant doit être rejeté."""
    broken = VALID_RECORD.copy()
    del broken["timestamp"]
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=broken, schema=SCHEMA)