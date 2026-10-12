# Dashboard & DevOps Engineer: feat/dashboard-devops

| Folder | Content |
|---|---|
| [`dashboard/`](dashboard) | React + Vite dashboard (mock mode, or live through the dashboard API) |
| [`dashboard-api/`](dashboard-api) | FastAPI backend-for-frontend: aggregates provider, Data Space and Edge AI APIs into `GET /api/dashboard` |
| [`../../deploy/docker/`](../../deploy/docker) | Dockerfiles for every service + nginx config |
| [`../../docker-compose.yml`](../../docker-compose.yml) | one-command local integration |
| [`../../deploy/k8s/`](../../deploy/k8s) | Kubernetes manifests (Minikube / Kind) |
| [`../../scripts/smoke_test.py`](../../scripts/smoke_test.py) | system smoke test of the final integration scenario |

## Dashboard API

The dashboard never reads another module's files. The dashboard API calls documented endpoints only:

| Widget | Source |
|---|---|
| Connected providers | provider `/health` + age of the latest record from `/data` |
| API health | `/health` latency of every service (`healthy` / `warning` > 800 ms or loop error / `offline`) |
| KPIs | latest records from each provider `/data` (as participant `dashboard_operator`, purpose `monitoring`) |
| Traffic chart | last 120 traffic records, bucketed into 24 points, with incident flags for congestion zones |
| Edge AI predictions | `traffic_sensor_1.congestion_forecast` through the traffic provider API (governed path) + Edge `/model-info` |
| Data space exchanges | Data Space `/audit` (the dashboard's own polling is hidden) + `/audit/stats` |

The traffic dataset requires a contract, so the dashboard API negotiates one on first access, as any partner would.

```powershell
cd dashboard-api; pip install -r requirements.txt
uvicorn app.main:app --port 8000          # GET http://localhost:8000/api/dashboard
python -m pytest -q                       # 4 tests
```

Variables: `PROVIDER_URLS`, `DATA_SPACE_URL`, `EDGE_URL`, `DASHBOARD_API_KEY`, `DASHBOARD_PURPOSE`,
`DASHBOARD_CACHE_SECONDS`, `DASHBOARD_TRAFFIC_POINTS`, `PROVIDER_STALE_SECONDS`, `CORS_ORIGINS`.

## Docker Compose

```bash
cp .env.example .env              # optional
docker compose up --build -d      # dashboard: http://localhost:8080
docker compose --profile test run --rm smoke-test
docker compose stop traffic-simulator && docker compose --profile demo run --rm scenario   # forced congestion
docker compose start traffic-simulator
docker compose down -v
```

Each provider has a private named volume shared only by its simulator and its API.

## Kubernetes (Minikube)

```bash
minikube start
eval $(minikube docker-env)        # PowerShell: & minikube -p minikube docker-env --shell powershell | Invoke-Expression
docker compose build               # images smds/*:1.0 built inside Minikube's Docker
kubectl apply -k deploy/k8s
kubectl get pods -n smart-mobility -w
minikube service dashboard -n smart-mobility
kubectl apply -f deploy/k8s/smoke-test-job.yaml && kubectl logs -f job/smoke-test -n smart-mobility
```

Kind: `kind create cluster`, `docker compose build`, then `kind load docker-image smds/simulator:1.0 smds/provider-api:1.0 smds/data-space:1.0 smds/edge-ai:1.0 smds/dashboard-api:1.0 smds/dashboard:1.0`
and `kubectl port-forward svc/dashboard 8080:80 -n smart-mobility`.

| Manifest | Objects |
|---|---|
| `00-namespace.yaml` | namespace `smart-mobility` |
| `01-config.yaml` | ConfigMap (URLs, intervals) + Secret (API keys, service token) |
| `10-data-space.yaml` | PVC (SQLite), Deployment, Service |
| `20-providers.yaml` | 4 pods, each with a **simulator + provider API** sharing a pod-local `emptyDir` (raw data never leaves the pod), 4 Services |
| `30-edge-ai.yaml`, `40-dashboard.yaml` | Deployments + Services; dashboard on NodePort 30080 |
| `smoke-test-job.yaml` | in-cluster smoke test Job |

Every Deployment has readiness and liveness probes on `/health` and resource requests/limits.
Forced congestion in Kubernetes: `kubectl exec -n smart-mobility deploy/traffic-sensor-1 -c simulator -- python scenario/scenario_generator.py`.
