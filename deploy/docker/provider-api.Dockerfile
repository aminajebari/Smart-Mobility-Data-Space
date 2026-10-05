# Module 2 - provider API template (one container per provider, PROVIDER_ID selects which)
FROM python:3.12-slim
WORKDIR /app/distributed-api
COPY feat/distributed-api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# Only Module 1's read-only access layer is needed; raw data arrives through a volume shared with the simulator
COPY feat/data-simulation/access/ /app/data-simulation/access/
COPY feat/distributed-api/ ./
ENV PYTHONUNBUFFERED=1 DATA_SIMULATION_PATH=/app/data-simulation RUNTIME_DIR=/app/runtime PROVIDER_API_PORT=8001
EXPOSE 8001
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ['PROVIDER_API_PORT'])"
CMD ["sh", "-c", "uvicorn provider_api.main:create_app --factory --host 0.0.0.0 --port $PROVIDER_API_PORT"]
