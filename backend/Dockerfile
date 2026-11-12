FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev libxml2 libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Usuario sin privilegios; dueño del volumen de uploads.
RUN useradd --system --uid 10001 app && mkdir -p /data/uploads && chown app /data/uploads

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER app
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
