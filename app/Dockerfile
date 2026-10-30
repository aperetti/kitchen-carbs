FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 KC_DATA=/data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server ./server
COPY web ./web
COPY seed ./seed

# docker build --target test app  (used by tools/deploy.sh)
FROM base AS test
RUN pip install --no-cache-dir pytest==8.3.4 httpx==0.28.1
COPY tests ./tests
RUN python -m pytest -q tests

FROM base
RUN useradd --uid 1000 --create-home kc && mkdir -p /data && chown kc /data
USER kc
EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/auth/config')"
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
