# Smart Mobility Data Space

A modular Smart Mobility Data Space where mobility providers keep local control of their data, expose controlled APIs, apply Gaia-X-inspired sharing policies, run Edge AI locally, and visualize the complete system through a dashboard.

## Team & Branches

| # | Member | Branch | Ownership |
|---|--------|--------|-----------|
| 1 | Mobility Data & Simulation Engineer | `feat/data-simulation` | Mobility data & provider simulators |
| 2 | Distributed API Engineer | `feat/distributed-api` | Distributed FastAPI services |
| 3 | Data Space / Gaia-X Engineer | `feat/data-space` | Gaia-X / Data Space governance |
| 4 | Edge AI Engineer | `feat/edge-ai` | Edge AI congestion prediction |
| 5 | Dashboard & DevOps Engineer | `feat/dashboard-devops` | Dashboard, Docker & Kubernetes |

## Shared Architecture & Rules

All five branches must respect the same interfaces so they can be merged with minimal rework.

- Provider simulators generate and keep raw mobility data locally.
- FastAPI services are the only public access point to provider data.
- Data Space logic decides whether a partner is allowed to access a dataset or result.
- Edge AI runs locally and shares predictions/results rather than unnecessary raw data.
- The dashboard consumes documented APIs only; it must not read another module's local files directly.
- Every service must expose `/health` and use environment variables for ports/URLs.

### Common JSON Record

```json
{
  "provider_id": "traffic_sensor_1",
  "timestamp": "2026-09-15T10:30:00",
  "latitude": 36.8065,
  "longitude": 10.1815,
  "speed": 24.5,
  "traffic_density": 0.78,
  "incident": false
}
```

## Module Breakdown

### 1. Mobility Data & Simulation Engineer
**Branch:** `feat/data-simulation` &nbsp;|&nbsp; **Primary goal:** Provide realistic local mobility data for all other modules.

**Implementation tasks**
- Create independent simulators for at least: traffic sensors, bus/public transport, smart parking, and shared bikes/scooters.
- Generate time-dependent values such as speed, traffic density, parking occupancy, incidents, schedules and geolocation.
- Keep each provider dataset isolated in its own local folder/database to demonstrate data sovereignty.
- Add deterministic seeds and configuration files so the same scenario can be reproduced during the demo.
- Create a simple scenario generator: normal traffic → increasing density → incident → congestion.

**Expected deliverables**
- Python simulation package with one command to start each provider.
- Sample datasets + documented schemas.
- Configuration file for simulation rate, provider ID and location.
- Unit tests validating value ranges and schema consistency.

**Integration contract**
- Outputs JSON records using the shared schema.
- Provides a local Python/data access function for Member 2 only; no direct dependency on AI, dashboard or Gaia-X modules.

---

### 2. Distributed API Engineer
**Branch:** `feat/distributed-api` &nbsp;|&nbsp; **Primary goal:** Expose every provider through consistent, documented and controlled REST APIs.

**Implementation tasks**
- Build FastAPI services for each provider using a shared service template.
- Implement endpoints such as `/health`, `/data`, `/datasets`, `/publish`, `/search` and `/logs`.
- Add filtering by time/provider/location where relevant.
- Add simple API-key or JWT authentication and request logging.
- Generate OpenAPI/Swagger documentation automatically.
- Add inter-service client helpers so one provider can request authorized information from another.

**Expected deliverables**
- Running FastAPI provider services.
- OpenAPI/Swagger documentation.
- Authentication/access middleware.
- Request/exchange logs and API tests.

**Integration contract**
- Reads local provider data produced by Member 1.
- Calls Member 3 authorization/policy checks before serving protected data.
- Exposes stable REST endpoints consumed by Members 4 and 5.

---

### 3. Data Space / Gaia-X Engineer
**Branch:** `feat/data-space` &nbsp;|&nbsp; **Primary goal:** Implement sovereignty, policy control, partner discovery and traceability.

**Implementation tasks**
- Create a partner registry describing mobility providers and their available datasets/services.
- Create a catalogue endpoint/model containing dataset metadata rather than copying raw data.
- Define simple policies: public, partner-only, role-based, purpose-limited or denied.
- Implement an authorization decision service: requester + dataset + purpose → allow/deny.
- Simulate a data-sharing agreement/contract before protected access.
- Persist traceability logs: who requested what, when, purpose, policy and decision.

**Expected deliverables**
- Partner/service catalogue.
- Policy definitions and policy evaluator.
- Contract/authorization simulation.
- Audit log API and test scenarios for allowed/denied requests.

**Integration contract**
- Member 2 calls the policy service before returning protected resources.
- Member 5 reads catalogue, policy status and exchange logs through APIs.
- Does not depend on the AI model implementation.

---

### 4. Edge AI Engineer
**Branch:** `feat/edge-ai` &nbsp;|&nbsp; **Primary goal:** Run useful mobility intelligence locally at the edge.

**Implementation tasks**
- Focus on one strong use case: traffic congestion prediction.
- Build features from speed, traffic density, incident flag and time information.
- Train and evaluate a lightweight model using historical/simulated records.
- Report clear metrics such as F1/accuracy for classes or MAE/RMSE for regression.
- Export the trained model to ONNX or TensorFlow Lite.
- Create an edge inference service exposing `/predict` and `/model-info`.
- Benchmark model size and inference latency between the original model and the Edge format.

**Expected deliverables**
- Training notebook/script and saved model.
- ONNX/TFLite edge model.
- Inference API.
- Evaluation + latency/model-size benchmark.

**Integration contract**
- Consumes standardized records through Member 2 APIs or local test fixtures.
- Publishes predictions as JSON; raw training data remains local.
- Member 5 visualizes prediction results and performance indicators.

---

### 5. Dashboard & DevOps Engineer
**Branch:** `feat/dashboard-devops` &nbsp;|&nbsp; **Primary goal:** Integrate the project visually and deploy all modules reproducibly.

**Implementation tasks**
- Build a dashboard showing connected providers, API health, mobility KPIs, Edge AI predictions and Data Space exchanges.
- Include a traffic view/chart where the congestion scenario is visible over time.
- Create Dockerfiles for all services and a root `docker-compose.yml` for fast local integration.
- Create Kubernetes manifests for Minikube or Kind: Deployments, Services and ConfigMaps/Secrets where needed.
- Add readiness/liveness health checks and centralized environment configuration.
- Create one-command startup instructions for the final demo.

**Expected deliverables**
- Functional dashboard.
- Dockerized project + Docker Compose integration.
- Kubernetes manifests and deployment documentation.
- System-level smoke test proving all services communicate.

**Integration contract**
- Consumes APIs only; never reads the other members' local files directly.
- Coordinates integration variables/ports but does not rewrite other members' business logic.
- Owns the final end-to-end deployment configuration.

## Final Integration Scenario

The final demo should prove the complete chain instead of showing five disconnected modules:

1. Traffic simulator increases density and introduces an incident.
2. Provider API publishes the current mobility state.
3. Edge node predicts congestion locally.
4. A partner requests the prediction or dataset through the distributed API.
5. Data Space policy checks the requester and returns allow/deny.
6. The exchange is written to the audit log.
7. Dashboard updates provider status, traffic indicators, AI prediction and exchange trace.

## Git Workflow

- Each member develops only on their assigned feature branch.
- Create small pull requests into an integration branch before merging to `main`.
- No module may change another module's public API without notifying the team.
- Keep shared schemas and API contracts in a small `/shared` directory reviewed by all five members.
- Merge only after automated tests and one end-to-end smoke test pass.
