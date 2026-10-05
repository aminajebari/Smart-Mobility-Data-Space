"""Data Space / Gaia-X governance service.

Partner registry, dataset catalogue (metadata only), usage policies,
data-sharing contracts, authorization decisions and the audit trail.
"""
import os
from pathlib import Path
from typing import Optional

import yaml
from fastapi import Depends, FastAPI, Header, HTTPException, Query

from . import policy as policy_engine
from .models import (AuditEntry, AuthorizationDecision, AuthorizationRequest, Contract, ContractRequest,
                     Dataset, Participant, Policy, PublishRequest)
from .store import Store

MODULE_ROOT = Path(__file__).parent.parent


def create_app(config_dir: Optional[str] = None, db_path: Optional[str] = None,
               service_token: Optional[str] = None) -> FastAPI:
    config_dir = Path(config_dir or os.environ.get("DATA_SPACE_CONFIG_DIR", MODULE_ROOT / "config"))
    db_path = db_path or os.environ.get("DATA_SPACE_DB", str(MODULE_ROOT / "runtime" / "dataspace.db"))
    service_token = service_token if service_token is not None else os.environ.get("DATA_SPACE_SERVICE_TOKEN", "")

    participants_cfg = yaml.safe_load((config_dir / "participants.yaml").read_text(encoding="utf-8"))
    catalogue_cfg = yaml.safe_load((config_dir / "catalogue.yaml").read_text(encoding="utf-8"))

    participants: dict[str, Participant] = {p["id"]: Participant(**p) for p in participants_cfg["participants"]}
    datasets: dict[str, Dataset] = {d["id"]: Dataset(**d) for d in catalogue_cfg["datasets"]}
    purposes: list[str] = catalogue_cfg.get("purposes", [])
    store = Store(db_path)

    app = FastAPI(
        title="Smart Mobility Data Space - Governance (Gaia-X)",
        version="1.0.0",
        description="Partner registry, catalogue, usage policies, contracts, authorization and audit trail.",
    )
    app.state.store = store

    def require_service(x_service_token: Optional[str] = Header(None)):
        """Write operations are reserved to trusted connectors (provider APIs, operators)."""
        if service_token and x_service_token != service_token:
            raise HTTPException(status_code=401, detail="invalid or missing X-Service-Token")

    def get_dataset(dataset_id: str) -> Dataset:
        if dataset_id not in datasets:
            raise HTTPException(status_code=404, detail=f"unknown dataset: {dataset_id}")
        status = store.dataset_status().get(dataset_id, {})
        live = {k: status[k] for k in ("access_url", "last_published", "record_count") if status.get(k) is not None}
        return datasets[dataset_id].model_copy(update=live)

    # -- health ------------------------------------------------------------
    @app.get("/health", tags=["system"])
    def health():
        return {"status": "ok", "service": "data-space", "participants": len(participants),
                "datasets": len(datasets), "audit_entries": store.audit_stats()["total"]}

    # -- partner registry --------------------------------------------------
    @app.get("/participants", response_model=list[Participant], tags=["registry"])
    def list_participants(type: Optional[str] = None, role: Optional[str] = None):
        result = list(participants.values())
        if type:
            result = [p for p in result if p.type == type]
        if role:
            result = [p for p in result if role in p.roles]
        return result

    @app.get("/participants/{participant_id}", response_model=Participant, tags=["registry"])
    def get_participant(participant_id: str):
        if participant_id not in participants:
            raise HTTPException(status_code=404, detail=f"unknown participant: {participant_id}")
        return participants[participant_id]

    @app.post("/participants", response_model=Participant, status_code=201, tags=["registry"],
              dependencies=[Depends(require_service)])
    def register_participant(participant: Participant):
        if participant.id in participants:
            raise HTTPException(status_code=409, detail="participant already registered")
        participants[participant.id] = participant
        return participant

    # -- catalogue -----------------------------------------------------------
    @app.get("/catalogue", response_model=list[Dataset], tags=["catalogue"])
    def catalogue(q: Optional[str] = Query(None, description="keyword in id, title, description or tags"),
                  provider_id: Optional[str] = None, tag: Optional[str] = None,
                  policy_type: Optional[str] = None):
        result = [get_dataset(d) for d in datasets]
        if q:
            needle = q.lower()
            result = [d for d in result if needle in " ".join([d.id, d.title, d.description, *d.tags]).lower()]
        if provider_id:
            result = [d for d in result if d.provider_id == provider_id]
        if tag:
            result = [d for d in result if tag in d.tags]
        if policy_type:
            result = [d for d in result if d.policy.type == policy_type]
        return result

    @app.get("/catalogue/{dataset_id}", response_model=Dataset, tags=["catalogue"])
    def catalogue_item(dataset_id: str):
        return get_dataset(dataset_id)

    @app.post("/catalogue/{dataset_id}/publish", response_model=Dataset, tags=["catalogue"],
              dependencies=[Depends(require_service)])
    def publish(dataset_id: str, body: PublishRequest):
        dataset = get_dataset(dataset_id)
        if body.provider_id != dataset.provider_id:
            raise HTTPException(status_code=403, detail="only the owning provider can publish this dataset")
        store.upsert_dataset_status(dataset_id, body.access_url, body.last_published, body.record_count)
        return get_dataset(dataset_id)

    @app.get("/purposes", tags=["policies"])
    def list_purposes():
        return purposes

    # -- policies ------------------------------------------------------------
    @app.get("/policies", tags=["policies"])
    def list_policies():
        return {d.id: d.policy for d in datasets.values()}

    @app.get("/policies/{dataset_id}", response_model=Policy, tags=["policies"])
    def get_policy(dataset_id: str):
        return get_dataset(dataset_id).policy

    @app.put("/policies/{dataset_id}", response_model=Policy, tags=["policies"],
             dependencies=[Depends(require_service)])
    def update_policy(dataset_id: str, new_policy: Policy, x_participant_id: str = Header(...)):
        dataset = get_dataset(dataset_id)
        if x_participant_id != dataset.provider_id:
            raise HTTPException(status_code=403, detail="only the owning provider can change its usage policy")
        datasets[dataset_id] = datasets[dataset_id].model_copy(update={"policy": new_policy})
        return new_policy

    # -- contracts -------------------------------------------------------------
    @app.post("/contracts", response_model=Contract, status_code=201, tags=["contracts"])
    def negotiate_contract(body: ContractRequest):
        """Simulated data-sharing agreement: accepted only if the usage policy permits the request."""
        dataset = get_dataset(body.dataset_id)
        requester = participants.get(body.requester_id)
        if requester is None:
            raise HTTPException(status_code=403, detail="requester is not a registered participant")
        if purposes and body.purpose not in purposes:
            raise HTTPException(status_code=422, detail=f"unknown purpose '{body.purpose}'")
        result = policy_engine.evaluate(requester, dataset, body.purpose)
        if not result.allowed:
            raise HTTPException(status_code=403, detail=f"contract refused: {result.reason}")
        existing = store.find_active_contract(body.requester_id, body.dataset_id, body.purpose)
        if existing:
            return existing
        terms = {
            "purpose": body.purpose,
            "policy_type": dataset.policy.type,
            "retention_days": dataset.policy.retention_days,
            "redistribution": dataset.policy.redistribution,
            "rulebook": "Smart Mobility Data Space rulebook v1",
        }
        return store.create_contract(body.requester_id, dataset.provider_id, dataset.id, body.purpose,
                                     body.duration_days, terms)

    @app.get("/contracts", response_model=list[Contract], tags=["contracts"])
    def list_contracts(requester_id: Optional[str] = None, dataset_id: Optional[str] = None):
        return store.list_contracts(requester_id, dataset_id)

    @app.post("/contracts/{contract_id}/revoke", response_model=Contract, tags=["contracts"],
              dependencies=[Depends(require_service)])
    def revoke_contract(contract_id: str):
        contract = store.revoke_contract(contract_id)
        if contract is None:
            raise HTTPException(status_code=404, detail="unknown contract")
        return contract

    # -- authorization -----------------------------------------------------------
    @app.post("/authorize", response_model=AuthorizationDecision, tags=["authorization"],
              dependencies=[Depends(require_service)])
    def authorize(body: AuthorizationRequest):
        """Decision point called by provider APIs before serving protected data. Every decision is audited."""
        dataset = datasets.get(body.dataset_id)
        if dataset is None:
            decision, reason, policy_type, provider_id, contract_id = "deny", "unknown dataset", None, None, None
        else:
            provider_id, policy_type, contract_id = dataset.provider_id, dataset.policy.type, None
            result = policy_engine.evaluate(participants.get(body.requester_id), dataset, body.purpose)
            decision, reason = ("allow" if result.allowed else "deny"), result.reason
            if result.allowed and result.needs_contract:
                contract = store.find_active_contract(body.requester_id, body.dataset_id, body.purpose)
                if contract:
                    contract_id = contract["id"]
                    reason += f"; contract {contract_id} active"
                else:
                    decision, reason = "deny", "no active data-sharing contract for this dataset and purpose"

        audit_id = store.add_audit(requester_id=body.requester_id, provider_id=provider_id,
                                   dataset_id=body.dataset_id, purpose=body.purpose, policy_type=policy_type,
                                   decision=decision, reason=reason, contract_id=contract_id, via=body.via)
        return AuthorizationDecision(decision=decision, reason=reason, requester_id=body.requester_id,
                                     dataset_id=body.dataset_id, purpose=body.purpose, policy_type=policy_type,
                                     contract_id=contract_id, audit_id=audit_id)

    # -- audit / traceability -------------------------------------------------------
    @app.get("/audit", response_model=list[AuditEntry], tags=["audit"])
    def audit(limit: int = Query(50, ge=1, le=1000), requester_id: Optional[str] = None,
              dataset_id: Optional[str] = None, provider_id: Optional[str] = None,
              decision: Optional[str] = Query(None, pattern="^(allow|deny)$")):
        return store.list_audit(limit, requester_id, dataset_id, provider_id, decision)

    @app.get("/audit/stats", tags=["audit"])
    def audit_stats():
        return store.audit_stats()

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("DATA_SPACE_PORT", "8010")))
