# Module 5 - dashboard aggregation API (also ships the system smoke test)
FROM python:3.12-slim
WORKDIR /app/dashboard-api
COPY feat/dashboard-devops/dashboard-api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY feat/dashboard-devops/dashboard-api/ ./
COPY scripts/smoke_test.py /app/scripts/smoke_test.py
ENV PYTHONUNBUFFERED=1 DASHBOARD_API_PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ['DASHBOARD_API_PORT'])"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $DASHBOARD_API_PORT"]
