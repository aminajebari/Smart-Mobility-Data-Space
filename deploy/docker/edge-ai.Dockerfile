# Module 4 - Edge AI inference node (ONNX Runtime only, no training stack in the image)
FROM python:3.12-slim
WORKDIR /app/edge-ai
COPY feat/edge-ai/requirements-runtime.txt ./
RUN pip install --no-cache-dir -r requirements-runtime.txt
COPY feat/edge-ai/edge_ai/ ./edge_ai/
COPY feat/edge-ai/models/metadata.json feat/edge-ai/models/congestion_rf.onnx ./models/
ENV PYTHONUNBUFFERED=1 EDGE_PORT=8020
EXPOSE 8020
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ['EDGE_PORT'])"
CMD ["sh", "-c", "uvicorn edge_ai.service:create_app --factory --host 0.0.0.0 --port $EDGE_PORT"]
