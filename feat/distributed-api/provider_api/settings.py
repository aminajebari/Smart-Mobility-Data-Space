"""All configuration comes from environment variables (shared project rule)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

MODULE_ROOT = Path(__file__).parent.parent


def parse_mapping(raw: str) -> dict[str, str]:
    """Parse "a:b,c:d" (or "a=b,c=d") into a dict."""
    result = {}
    for item in filter(None, (part.strip() for part in raw.split(","))):
        sep = ":" if ":" in item and "=" not in item else "="
        key, _, value = item.partition(sep)
        result[key.strip()] = value.strip()
    return result


@dataclass
class Settings:
    provider_id: str
    port: int
    public_url: str
    data_simulation_path: str
    data_space_url: str
    data_space_token: str
    api_keys: dict[str, str]
    own_api_key: str
    log_readers: list[str]
    runtime_dir: Path
    providers_config: Path
    catalogue_refresh_seconds: int
    partner_urls: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "Settings":
        provider_id = os.environ.get("PROVIDER_ID", "traffic_sensor_1")
        port = int(os.environ.get("PROVIDER_API_PORT", "8001"))
        return cls(
            provider_id=provider_id,
            port=port,
            public_url=os.environ.get("PUBLIC_URL", f"http://localhost:{port}"),
            data_simulation_path=os.environ.get("DATA_SIMULATION_PATH", str(MODULE_ROOT.parent / "data-simulation")),
            data_space_url=os.environ.get("DATA_SPACE_URL", "http://localhost:8010").rstrip("/"),
            data_space_token=os.environ.get("DATA_SPACE_SERVICE_TOKEN", ""),
            # API key -> participant id. Keys identify the requester (connector authentication).
            api_keys=parse_mapping(os.environ.get("API_KEYS", "")),
            own_api_key=os.environ.get("PROVIDER_API_KEY", ""),
            log_readers=[p for p in os.environ.get("LOG_READERS", "dashboard_operator").split(",") if p],
            runtime_dir=Path(os.environ.get("RUNTIME_DIR", MODULE_ROOT / "runtime" / provider_id)),
            providers_config=Path(os.environ.get("PROVIDERS_CONFIG", MODULE_ROOT / "config" / "providers.yaml")),
            catalogue_refresh_seconds=int(os.environ.get("CATALOGUE_REFRESH_SECONDS", "30")),
            # Optional static fallback when the catalogue has no access_url yet: "bus_line_12=http://...,..."
            partner_urls=parse_mapping(os.environ.get("PARTNER_URLS", "")),
        )
