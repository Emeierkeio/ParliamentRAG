# Servizio web: sito (sito/), API (/v1), server MCP (/mcp) e chat in un solo processo uvicorn.
# Niente Playwright né dipendenze della pipeline: servono solo al giro notturno sulla VPS.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# dipendenze per prime: lo strato resta in cache finché requirements-api.txt non cambia
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# della pipeline serve solo la lettura dell'ambiente (pipeline/ambiente.py)
COPY pipeline/__init__.py pipeline/ambiente.py pipeline/
COPY schema/ schema/
COPY api/ api/
COPY sito/ sito/

# utente senza privilegi; dati/ è l'unica cartella scrivibile (spesa della chat in dati/api, foto in dati/foto)
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin web \
 && mkdir -p dati/api dati/foto/senatori \
 && chown -R web:web dati
USER web

# Railway assegna PORT; in locale il predefinito è 8000
ENV PORT=8000
EXPOSE 8000

# Railway non legge HEALTHCHECK (usa healthcheckPath in railway.toml): serve a docker run e ad altri ospiti
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/v1/salute', timeout=4)"

# un solo processo: il limite per IP vive in memoria e vale per processo.
# --forwarded-allow-ips '*' serve perché --proxy-headers abbia effetto dietro il proxy di Railway (schema https nei
# reindirizzamenti); l'IP per i limiti lo legge api/rete.py da X-Forwarded-For, solo con API_PROXY=1.
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port \"$PORT\" --proxy-headers --forwarded-allow-ips '*' --no-server-header"]
