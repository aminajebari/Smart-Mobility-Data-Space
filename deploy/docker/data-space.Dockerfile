# Module 3 - Data Space / Gaia-X governance service
FROM python:3.12-slim
WORKDIR /app/data-space
COPY feat/data-space/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY feat/data-space/ ./
ENV PYTHONUNBUFFERED=1 DATA_SPACE_DB=/data/dataspace.db DATA_SPACE_PORT=8010
EXPOSE 8010
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ['DATA_SPACE_PORT'])"
CMD ["sh", "-c", "uvicorn dataspace.main:app --host 0.0.0.0 --port $DATA_SPACE_PORT"]
