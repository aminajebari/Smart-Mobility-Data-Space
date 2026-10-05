# Smart Mobility Data Space — Dashboard

A responsive operations dashboard prototype for the Smart Mobility Data Space. This branch contains **only the frontend dashboard** and uses realistic mock mobility data. Docker, Docker Compose, Kubernetes, and backend services are intentionally out of scope for this phase.

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

The congestion chart is an accessible, responsive SVG component and highlights the simulated 08:00–09:30 congestion event. No chart runtime dependency is required.

## Mock data and future REST integration

All displayed provider states, service health, KPIs, time-series values, Edge AI predictions, and data exchanges currently come from [`src/mock/dashboardData.ts`](src/mock/dashboardData.ts). UI components do not import mock data directly. They receive typed data through `dashboardService` and `useDashboardData`.

Copy `.env.example` to `.env.local` to configure the data source:

```env
VITE_USE_MOCK_DATA=true
VITE_API_BASE_URL=http://localhost:8000/api
```

For future integration, set `VITE_USE_MOCK_DATA=false`. The existing HTTP implementation then requests `${VITE_API_BASE_URL}/dashboard`. The response should match the `DashboardData` type in `src/types/dashboard.ts`. This service boundary allows the mock implementation to be replaced or expanded into service-specific REST calls without rewriting any dashboard component.

Environment files containing local values are ignored by Git; `.env.example` documents the expected variables. The default URL exists only in centralized configuration and is never hardcoded in UI components.

## Current scope

- Connected/disconnected mobility providers
- Mock health for planned distributed services
- Five live-operations KPIs
- Traffic density and speed time series with a visible congestion window
- Clearly labeled mock Edge AI predictions
- Recent governed data exchanges and authorization results
- Responsive desktop/tablet/mobile layout
- Frontend smoke test

There are no dependencies on another team member's files or local environment. Future data integration is REST-only.
