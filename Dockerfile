# Container image for the speccheck web app.
#   docker build -t speccheck .
#   docker run -p 8000:8000 -e SPECCHECK_PASSWORD=changeme \
#       -v "$PWD/data:/data" -e SPECCHECK_DB=/data/speccheck.db speccheck
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY speccheck ./speccheck
RUN pip install --no-cache-dir ".[web,pdf]"

# Persist the SQLite database outside the image by mounting a volume at /data.
ENV SPECCHECK_DB=/data/speccheck.db
RUN mkdir -p /data

EXPOSE 8000
# $PORT is honored by most PaaS hosts (Render, Railway); defaults to 8000.
CMD ["sh", "-c", "uvicorn speccheck.web:app --host 0.0.0.0 --port ${PORT:-8000}"]
