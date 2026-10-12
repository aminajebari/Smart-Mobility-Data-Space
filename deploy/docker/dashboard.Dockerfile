# Module 5 - React dashboard, built with Vite and served by nginx (which proxies /api to the dashboard API)
FROM node:20-alpine AS build
WORKDIR /app
COPY feat/dashboard-devops/dashboard/package.json feat/dashboard-devops/dashboard/package-lock.json ./
RUN npm ci
COPY feat/dashboard-devops/dashboard/ ./
ENV VITE_USE_MOCK_DATA=false VITE_API_BASE_URL=/api VITE_REFRESH_MS=4000
RUN npm run build

FROM nginx:1.27-alpine
COPY deploy/docker/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
ENV DASHBOARD_API_UPSTREAM=http://dashboard-api:8000
EXPOSE 80
