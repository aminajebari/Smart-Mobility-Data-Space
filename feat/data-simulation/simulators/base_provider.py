import json
import yaml
import numpy as np
from pathlib import Path
from datetime import datetime
import jsonschema

ROOT = Path(__file__).parent.parent
SCHEMA_PATH = ROOT / "schemas" / "mobility_record.schema.json"
CONFIG_PATH = ROOT / "config" / "config.yaml"
SEEDS_PATH = ROOT / "config" / "seeds.yaml"


class BaseProvider:
    def __init__(self, provider_id: str):
        self.provider_id = provider_id
        self.config = self._load_yaml(CONFIG_PATH)["providers"][provider_id]
        self.seed = self._load_yaml(SEEDS_PATH)["seeds"][provider_id]
        self.rng = np.random.default_rng(self.seed)
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.output_dir = ROOT / "data" / provider_id
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _load_yaml(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def generate_record(self, timestamp: datetime) -> dict:
        raise NotImplementedError

    def validate(self, record: dict):
        jsonschema.validate(instance=record, schema=self.schema)

    def write_record(self, record: dict):
        self.validate(record)
        date_str = record["timestamp"][:10]
        file_path = self.output_dir / f"{date_str}.jsonl"
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")