import json
from pathlib import Path
from datetime import datetime, date
from typing import Optional

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"


def get_latest_records(provider_id: str, limit: int = 50) -> list[dict]:
    """Retourne les N derniers records d'un provider (les plus récents en dernier)."""
    provider_dir = DATA_DIR / provider_id
    if not provider_dir.exists():
        return []

    files = sorted(provider_dir.glob("*.jsonl"))
    records = []
    for file in reversed(files):  # on part du fichier le plus récent
        with open(file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in reversed(lines):
            records.append(json.loads(line))
            if len(records) >= limit:
                return list(reversed(records))
    return list(reversed(records))


def get_records_since(provider_id: str, since: datetime) -> list[dict]:
    """Retourne tous les records postérieurs à un timestamp donné."""
    provider_dir = DATA_DIR / provider_id
    if not provider_dir.exists():
        return []

    records = []
    for file in sorted(provider_dir.glob("*.jsonl")):
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                if datetime.fromisoformat(record["timestamp"]) >= since:
                    records.append(record)
    return records


def list_available_providers() -> list[str]:
    """Liste tous les providers ayant au moins un fichier de données."""
    if not DATA_DIR.exists():
        return []
    return [p.name for p in DATA_DIR.iterdir() if p.is_dir()]