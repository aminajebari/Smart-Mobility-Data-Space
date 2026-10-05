# Module 1 - provider simulator (one container per provider, PROVIDER_ID selects which)
FROM python:3.12-slim
WORKDIR /app/data-simulation
RUN pip install --no-cache-dir jsonschema pyyaml numpy
COPY feat/data-simulation/ ./
ENV PYTHONUNBUFFERED=1 PROVIDER_ID=traffic_sensor_1
CMD ["sh", "-c", "python cli.py start --provider $PROVIDER_ID"]
