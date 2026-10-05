# Data Space / Gaia-X Engineer: feat/data-space

Governance service of the Smart Mobility Data Space: **partner registry, dataset catalogue, usage
policies, data-sharing contracts, authorization decisions and audit trail**. It never stores or
serves raw mobility data. The catalogue only holds metadata (Gaia-X style self-descriptions).

## Run

```powershell
pip install -r requirements.txt
uvicorn dataspace.main:app --port 8010      # Swagger: http://localhost:8010/docs
python -m pytest -q                         # 17 tests (policy rules + allowed/denied API scenarios)
```

| Variable | Default | Role |
|---|---|---|
| `DATA_SPACE_PORT` | 8010 | port when started with `python -m dataspace.main` |
| `DATA_SPACE_DB` | `runtime/dataspace.db` | SQLite file for contracts, audit log, live catalogue metadata |
| `DATA_SPACE_SERVICE_TOKEN` | empty (disabled) | shared secret required on write endpoints (`X-Service-Token`) |
| `DATA_SPACE_CONFIG_DIR` | `config/` | `participants.yaml` and `catalogue.yaml` |

## Gaia-X principles → implementation

| Principle | Where |
|---|---|
| Data sovereignty | Providers own their offerings: only the owner can publish metadata or change a policy; the owner always keeps access to its own data, even under `denied` |
| Access control | `POST /authorize`: requester + dataset + purpose → allow/deny, called by every provider API before serving data |
| Secure sharing between partners | `membership` (member/guest) and `roles` in the registry; contracts required for sensitive datasets |
| Usage policies | `public`, `partner_only`, `role_based`, `purpose_limited`, `denied` + `requires_contract`, `retention_days`, `redistribution` ([`config/catalogue.yaml`](config/catalogue.yaml)) |
| Traceability | every decision is persisted in the audit log: who, what, when, purpose, policy, decision, reason, contract |
| Catalogue / discovery | `GET /catalogue?q=&tag=`; each provider API publishes its `access_url`, which partners use to find it |

## Policy evaluation order ([`dataspace/policy.py`](dataspace/policy.py))

1. `denied` → deny (except the owner).
2. Owner → allow.
3. `public` → allow, even anonymous.
4. Unknown requester → deny. `guest` membership → deny.
5. `role_based`: requester roles ∩ `allowed_roles` must not be empty.
6. `allowed_purposes` (any type, mandatory for `purpose_limited`): the declared purpose must be listed.
7. `requires_contract`: an active, non-expired contract for (requester, dataset, purpose) must exist,
   otherwise the request is denied with "no active data-sharing contract".

## Contract flow

```
partner ──POST /contracts {requester, dataset, purpose}──▶ policy evaluated
        ◀── 201 contract (terms: purpose, retention, redistribution, expiry)   or 403 refused
partner ──GET provider-api/data──▶ provider-api ──POST /authorize──▶ allow (contract id) + audit entry
```

## Test scenarios (tests/test_api.py)

Public dataset allowed for a guest · `denied` dataset refused · access denied until a contract exists
and then allowed · contract refused for a disallowed purpose · revoked contract denies again ·
role-based allow/deny · every decision audited · write endpoints require the service token ·
only the owner can publish or change its policy.
