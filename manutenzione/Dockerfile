# Pagina di manutenzione: solo libreria standard, nessuna dipendenza.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app
COPY index.html server.py ./

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin web
USER web

EXPOSE 8080
CMD ["python", "server.py"]
