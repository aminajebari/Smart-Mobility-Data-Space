# Smart Mobility Data Space — Dashboard

A responsive operations dashboard for the Smart Mobility Data Space. It runs either on built-in mock data or **live** against the dashboard API (`../dashboard-api`), which aggregates the provider, Data Space and Edge AI APIs. Deployment (Docker, Compose, Kubernetes) is described in [`../README.md`](../README.md).

## Run locally

Requirements: Node.js 20 or newer and npm.

```bash
npm install
npm run dev
```

Open the URL printed by Vite (normally `http://localhost:5173`). Other useful commands:

```bash
npm test
npm run build
npm run preview
```

## Structure

```text
src/
├── components/       Reusable KPI, status, chart, prediction, and table UI
├── config/           Centralized environment configuration
├── hooks/            Dashboard data loading state
├── mock/             All current dashboard data
├── pages/            Dashboard page composition
├── services/         Mock/HTTP API abstraction
├── test/             Test setup
└── types/            Shared TypeScript domain models
```

The congestion chart is an accessible, responsive SVG component. Congestion zones are derived from the `incident` flag of each traffic point, so the live congestion scenario appears as it happens. No chart runtime dependency is required.

## Mock data and live integration

All displayed provider states, service health, KPIs, time-series values, Edge AI predictions, and data exchanges currently come from [`src/mock/dashboardData.ts`](src/mock/dashboardData.ts). UI components do not import mock data directly. They receive typed data through `dashboardService` and `useDashboardData`.

Copy `.env.example` to `.env.local` to configure the data source:

```env
VITE_USE_MOCK_DATA=true
VITE_API_BASE_URL=http://localhost:8000/api
```

For live data, start the backend (`python scripts/run_local.py` from the repo root, or `docker compose up`) and set `VITE_USE_MOCK_DATA=false`. The HTTP implementation then requests `${VITE_API_BASE_URL}/dashboard` (served by the dashboard API) and refreshes every `VITE_REFRESH_MS` milliseconds (default 5000). The response matches the `DashboardData` type in `src/types/dashboard.ts`; `mode: 'live'` switches the labels from "mock" to "live". In the Docker image the app is built with `VITE_API_BASE_URL=/api` and nginx proxies `/api` to the dashboard API.

Environment files containing local values are ignored by Git; `.env.example` documents the expected variables. The default URL exists only in centralized configuration and is never hardcoded in UI components.

## Current scope

- Connected/disconnected mobility providers
- Health and latency of every distributed service
- Five live-operations KPIs
- Traffic density and speed time series with a visible congestion window
- Edge AI predictions (live from the edge node, or clearly labeled mock data)
- Recent governed data exchanges from the Data Space audit log, with allow/deny counts
- Responsive desktop/tablet/mobile layout
- Frontend smoke test and chart tests

There are no dependencies on another team member's files or local environment. Future data integration is REST-only.
