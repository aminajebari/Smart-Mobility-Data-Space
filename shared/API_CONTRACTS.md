# Shared API contracts

Reviewed by all five members. Do not change a public endpoint or field here without notifying the team.
Every service exposes `GET /health` and an auto-generated Swagger UI at `/docs` (OpenAPI at `/openapi.json`).

## Services and ports

| Service | Module | Default port | Configured by |
|---|---|---|---|
| Provider API `traffic_sensor_1` | 2 | 8001 | `PROVIDER_ID`, `PROVIDER_API_PORT` |
| Provider API `bus_line_12` | 2 | 8002 | same template |
| Provider API `parking_lot_5` | 2 | 8003 | same template |
| Provider API `bikes_zone_a` | 2 | 8004 | same template |
| Data Space governance | 3 | 8010 | `DATA_SPACE_PORT` |
| Edge AI node | 4 | 8020 | `EDGE_PORT` |
| Dashboard API | 5 | 8000 | `DASHBOARD_API_PORT` |
| Dashboard (nginx) | 5 | 8080 (host) | `DASHBOARD_PORT` |

## Common record

[`schemas/mobility_record.schema.json`](schemas/mobility_record.schema.json), a copy of Module 1's schema.
Required: `provider_id`, `timestamp` (ISO 8601, local time, no timezone), `latitude`, `longitude`.
Provider-specific: `speed`, `traffic_density`, `incident`, `occupancy`, `route_id`, `delay_min`, `battery_level`, `status`.

## Identity and authorization

- Requesters authenticate on provider APIs with `X-API-Key`. The key maps to a **participant id** of the
  Data Space registry (`API_KEYS=key:participant,...`). No key = `anonymous` (only `public` datasets).
- Every data request declares a **purpose** (`?purpose=`). Vocabulary: `congestion_prediction`,
  `traffic_management`, `monitoring`, `route_optimization`, `research`, `commercial`.
- Provider APIs call `POST /authorize` on the Data Space **before** returning data and fail closed (503)
  if it is unreachable. Write endpoints of the Data Space require `X-Service-Token`.

## Dataset ids

`<provider_id>.<name>`. Catalogue: `GET {data-space}/catalogue`.

| Dataset | Policy | Contract |
|---|---|---|
| `traffic_sensor_1.traffic_flow` | purpose_limited (congestion_prediction, traffic_management, monitoring, research) | required |
| `traffic_sensor_1.congestion_forecast` | partner_only (edge AI results) | no |
| `bus_line_12.vehicle_status` | public | no |
| `bus_line_12.passenger_counts` | denied | - |
| `parking_lot_5.occupancy` | public | no |
| `bikes_zone_a.fleet_status` | role_based (micromobility/transport operator, public authority, operator) | no |

## Module 2: provider API

| Method & path | Purpose |
|---|---|
| `GET /health` | liveness, provider id, whether local data exists |
| `GET /datasets` | datasets served by this provider + catalogue policy |
| `GET /data?dataset_id&purpose&limit&since&until&incident&lat&lon&radius_km` | policy-checked records |
| `POST /publish` `{dataset_id, records[]}` | publish results to a derived dataset (authorized publishers only) |
| `GET /search?q&tag&lat&lon&radius_km&scope=local\|data_space` | dataset discovery (metadata) |
| `GET /logs?limit` | request log (provider itself or `LOG_READERS`) |
| `POST /partners/contracts` `{dataset_id, purpose}` | negotiate a contract on behalf of this provider |
| `GET /partners/data?dataset_id&purpose&limit` | fetch a partner dataset using this provider's identity |

`GET /data` response:

```json
{"dataset_id": "traffic_sensor_1.traffic_flow", "provider_id": "traffic_sensor_1", "count": 1,
 "authorization": {"decision": "allow", "reason": "...", "policy_type": "purpose_limited", "contract_id": "ctr-...", "audit_id": 42},
 "records": [{"provider_id": "traffic_sensor_1", "timestamp": "2026-10-05T15:12:44", "...": "..."}]}
```

Errors: `401` invalid key, `403` policy denial (`detail.reason`, `detail.audit_id`), `404` dataset not served here,
`503` policy service unavailable.

## Module 3: Data Space governance

| Method & path | Purpose |
|---|---|
| `GET /participants[?type&role]`, `GET /participants/{id}`, `POST /participants`* | partner registry |
| `GET /catalogue[?q&provider_id&tag&policy_type]`, `GET /catalogue/{id}` | dataset self-descriptions (metadata only) |
| `POST /catalogue/{id}/publish`* | owner refreshes `access_url`, `record_count`, `last_published` |
| `GET /policies`, `GET /policies/{id}`, `PUT /policies/{id}`* (owner, `X-Participant-Id`) | usage policies |
| `GET /purposes` | purpose vocabulary |
| `POST /contracts` `{requester_id, dataset_id, purpose, duration_days}` | negotiate a data-sharing agreement |
| `GET /contracts`, `POST /contracts/{id}/revoke`* | agreements |
| `POST /authorize`* `{requester_id, dataset_id, purpose, via}` | decision `allow`/`deny` + reason, always audited |
| `GET /audit[?limit&requester_id&dataset_id&provider_id&decision]`, `GET /audit/stats` | traceability |

\* requires `X-Service-Token`.

## Module 4: Edge AI

| Method & path | Purpose |
|---|---|
| `POST /predict` `{records: [...]}` | local inference on the last 6 records |
| `GET /model-info` | features, metrics (F1, ROC-AUC...), size/latency benchmark |
| `GET /predictions/latest`, `GET /predictions?limit` | results of the background edge loop |

Published forecast record (`traffic_sensor_1.congestion_forecast`):
`timestamp, predicted_at, congestion_probability, congested, traffic_level, estimated_travel_time_min, model_version`.

## Module 5: dashboard API

`GET /api/dashboard` returns the `DashboardData` document defined in
`feat/dashboard-devops/dashboard/src/types/dashboard.ts` (`providers`, `services`, `kpis`, `traffic`,
`predictions`, `exchanges`, `updatedAt`, plus `mode` and `exchangeStats`).
