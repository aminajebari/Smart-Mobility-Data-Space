"""Provider API: shared FastAPI template, one instance per mobility provider.

The only public access point to a provider's data. Every data request is
authenticated (API key), checked against the Data Space policy service and logged.
"""
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import yaml
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from .client import PartnerRequestError, ProviderClient
from .data_access import PublishedStore, SimulationData, distance_km, filter_records
from .dataspace_client import DataSpaceClient, DataSpaceUnavailable
from .request_log import RequestLog
from .settings import Settings

log = logging.getLogger("provider_api")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False,
                              description="Participant API key. Omit it to access public datasets anonymously.")


class PublishBody(BaseModel):
    dataset_id: str
    records: list[dict] = Field(default_factory=list, description="Records to append (results such as predictions)")


class ContractBody(BaseModel):
    dataset_id: str
    purpose: str


def create_app(settings: Optional[Settings] = None, data_space: Optional[DataSpaceClient] = None,
               simulation: Optional[SimulationData] = None, partner_client: Optional[ProviderClient] = None,
               background: bool = True) -> FastAPI:
    settings = settings or Settings.from_env()
    providers_cfg = yaml.safe_load(settings.providers_config.read_text(encoding="utf-8"))["providers"]
    if settings.provider_id not in providers_cfg:
        raise RuntimeError(f"PROVIDER_ID '{settings.provider_id}' is not defined in {settings.providers_config}")

    pid = settings.provider_id
    provider_cfg = providers_cfg[pid]
    datasets: dict[str, dict] = provider_cfg["datasets"]
    primary_dataset = next(d for d, c in datasets.items() if c["source"] == "simulation")

    data_space = data_space or DataSpaceClient(settings.data_space_url, settings.data_space_token)
    simulation = simulation or SimulationData(settings.data_simulation_path)
    partner_client = partner_client or ProviderClient(settings.own_api_key, data_space, settings.partner_urls)
    published = PublishedStore(settings.runtime_dir)
    request_log = RequestLog(settings.runtime_dir)
    stop = threading.Event()

    def dataset_records(dataset_id: str, limit: int, since: Optional[datetime] = None, wide: bool = False) -> list[dict]:
        source = datasets[dataset_id]["source"]
        if source == "simulation":
            if since:
                return simulation.since(pid, since)
            return simulation.latest(pid, max(limit, 1000) if wide else limit)
        if source == "published":
            return published.read(dataset_id)
        return []

    def publish_metadata():
        """Refresh this provider's offerings in the Data Space catalogue (self-description)."""
        for dataset_id, cfg in datasets.items():
            if cfg["source"] == "none":
                continue
            records = dataset_records(dataset_id, 10 ** 7)
            last = records[-1].get("timestamp") if records else None
            data_space.publish(dataset_id, pid, settings.public_url, len(records), last)

    def catalogue_loop():
        while not stop.is_set():
            try:
                publish_metadata()
            except Exception as exc:  # the Data Space may not be up yet; retry on next tick
                log.warning("catalogue publish failed: %s", exc)
            stop.wait(settings.catalogue_refresh_seconds)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if background:
            threading.Thread(target=catalogue_loop, daemon=True, name="catalogue-publisher").start()
        yield
        stop.set()

    app = FastAPI(
        title=f"Provider API - {provider_cfg['name']}",
        version="1.0.0",
        lifespan=lifespan,
        description=(f"Controlled REST access to the data of provider **{pid}**. Raw data stays local; "
                     "every request is authorized by the Data Space policy service and logged."),
    )

    def requester(api_key: Optional[str] = Depends(api_key_header)) -> str:
        if api_key is None:
            return "anonymous"
        participant = settings.api_keys.get(api_key)
        if participant is None:
            raise HTTPException(status_code=401, detail="invalid API key")
        return participant

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        if request.url.path not in ("/health", "/docs", "/openapi.json", "/favicon.ico"):
            key = request.headers.get("X-API-Key")
            request_log.add(
                method=request.method, path=request.url.path, query=str(request.url.query),
                requester=settings.api_keys.get(key, "invalid-key") if key else "anonymous",
                status=response.status_code, duration_ms=round((time.perf_counter() - started) * 1000, 1),
                dataset_id=getattr(request.state, "dataset_id", None),
                decision=getattr(request.state, "decision", None),
            )
        return response

    # -- system --------------------------------------------------------------
    @app.get("/health", tags=["system"])
    def health():
        return {"status": "ok", "service": "provider-api", "provider_id": pid,
                "datasets": list(datasets), "local_data": pid in simulation.providers()}

    # -- datasets ------------------------------------------------------------
    @app.get("/datasets", tags=["datasets"])
    def list_datasets():
        try:
            catalogue = {d["id"]: d for d in data_space.catalogue(provider_id=pid)}
        except Exception:
            catalogue = {}
        result = []
        for dataset_id, cfg in datasets.items():
            records = dataset_records(dataset_id, 10 ** 7)
            entry = catalogue.get(dataset_id, {})
            result.append({
                "dataset_id": dataset_id,
                "provider_id": pid,
                "title": cfg.get("title", dataset_id),
                "source": cfg["source"],
                "tags": cfg.get("tags", []),
                "record_count": len(records),
                "last_timestamp": records[-1].get("timestamp") if records else None,
                "fields": sorted(records[-1].keys()) if records else entry.get("fields", []),
                "policy": entry.get("policy"),
            })
        return result

    @app.get("/data", tags=["data"])
    def get_data(
        request: Request,
        dataset_id: Optional[str] = Query(None, description=f"Defaults to {primary_dataset}"),
        purpose: str = Query("unspecified", description="Declared usage purpose, checked by the usage policy"),
        limit: int = Query(50, ge=1, le=1000),
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        incident: Optional[bool] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius_km: Optional[float] = Query(None, gt=0),
        who: str = Depends(requester),
    ):
        dataset_id = dataset_id or primary_dataset
        if dataset_id not in datasets:
            raise HTTPException(status_code=404, detail=f"dataset '{dataset_id}' is not served by {pid}")
        request.state.dataset_id = dataset_id
        try:
            decision = data_space.authorize(who, dataset_id, purpose, via=f"provider-api:{pid}")
        except DataSpaceUnavailable as exc:
            # fail closed: without a policy decision no protected data leaves the provider
            raise HTTPException(status_code=503, detail=f"policy service unavailable: {exc}")
        request.state.decision = decision["decision"]
        if decision["decision"] != "allow":
            raise HTTPException(status_code=403, detail={"reason": decision["reason"], "dataset_id": dataset_id,
                                                         "purpose": purpose, "audit_id": decision.get("audit_id")})

        since_naive = since.replace(tzinfo=None) if since else None
        until_naive = until.replace(tzinfo=None) if until else None
        wide = any(v is not None for v in (until, incident, lat, radius_km))
        records = dataset_records(dataset_id, limit, since_naive, wide)
        records = filter_records(records, since_naive, until_naive, incident, lat, lon, radius_km)[-limit:]
        return {
            "dataset_id": dataset_id,
            "provider_id": pid,
            "count": len(records),
            "authorization": {k: decision.get(k) for k in ("decision", "reason", "policy_type", "contract_id", "audit_id")},
            "records": records,
        }

    @app.post("/publish", tags=["data"])
    def publish(body: PublishBody, request: Request, who: str = Depends(requester)):
        """Publish records to a derived dataset and refresh its catalogue entry."""
        cfg = datasets.get(body.dataset_id)
        if cfg is None:
            raise HTTPException(status_code=404, detail=f"dataset '{body.dataset_id}' is not served by {pid}")
        request.state.dataset_id = body.dataset_id
        if who not in [pid, *cfg.get("publishers", [])]:
            raise HTTPException(status_code=403, detail=f"'{who}' is not allowed to publish to {body.dataset_id}")
        if body.records and cfg["source"] != "published":
            raise HTTPException(status_code=409, detail="raw datasets are produced locally by the provider simulator")
        if any("timestamp" not in r for r in body.records):
            raise HTTPException(status_code=422, detail="every record needs a timestamp")

        total = published.append(body.dataset_id, body.records) if body.records else len(dataset_records(body.dataset_id, 10 ** 7))
        last = body.records[-1]["timestamp"] if body.records else None
        try:
            catalogue_updated = data_space.publish(body.dataset_id, pid, settings.public_url, total, last)
        except DataSpaceUnavailable:
            catalogue_updated = False
        return {"dataset_id": body.dataset_id, "stored": len(body.records), "total": total,
                "catalogue_updated": catalogue_updated}

    @app.get("/search", tags=["datasets"])
    def search(q: Optional[str] = None, tag: Optional[str] = None,
               lat: Optional[float] = None, lon: Optional[float] = None, radius_km: Optional[float] = Query(None, gt=0),
               scope: str = Query("local", pattern="^(local|data_space)$",
                                  description="local = this provider, data_space = federated catalogue search")):
        """Search datasets by keyword, tag and location (metadata only)."""
        try:
            entries = data_space.catalogue(q=q, tag=tag, provider_id=None if scope == "data_space" else pid)
        except Exception:
            if scope == "data_space":
                raise HTTPException(status_code=503, detail="catalogue unavailable")
            needle = (q or "").lower()
            entries = [{"id": d, "provider_id": pid, "title": c.get("title", d), "tags": c.get("tags", []),
                        "location": provider_cfg.get("location")}
                       for d, c in datasets.items()
                       if needle in f"{d} {c.get('title', '')} {' '.join(c.get('tags', []))}".lower()
                       and (not tag or tag in c.get("tags", []))]
        if lat is not None and lon is not None and radius_km is not None:
            entries = [e for e in entries if e.get("location") and distance_km(lat, lon, *e["location"]) <= radius_km]
        return entries

    @app.get("/logs", tags=["system"])
    def logs(limit: int = Query(100, ge=1, le=2000), who: str = Depends(requester)):
        if who not in [pid, *settings.log_readers]:
            raise HTTPException(status_code=403, detail="only the provider or an operator can read request logs")
        return request_log.latest(limit)

    # -- inter-service exchange ----------------------------------------------------
    @app.post("/partners/contracts", tags=["partners"])
    def partner_contract(body: ContractBody, who: str = Depends(requester)):
        """Negotiate, on behalf of this provider, a data-sharing contract for a partner dataset."""
        if who != pid:
            raise HTTPException(status_code=403, detail="only this provider can act on its own behalf")
        try:
            response = data_space.negotiate_contract(pid, body.dataset_id, body.purpose)
        except DataSpaceUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail"))
        return response.json()

    @app.get("/partners/data", tags=["partners"])
    def partner_data(dataset_id: str, purpose: str, limit: int = Query(20, ge=1, le=1000),
                     who: str = Depends(requester)):
        """Request authorized data from another provider, using this provider's own identity."""
        if who != pid:
            raise HTTPException(status_code=403, detail="only this provider can act on its own behalf")
        try:
            return partner_client.get_data(dataset_id, purpose, limit)
        except PartnerRequestError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    return app


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(create_app(), host=os.environ.get("HOST", "0.0.0.0"),
                port=int(os.environ.get("PROVIDER_API_PORT", "8001")))
