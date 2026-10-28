FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && useradd --create-home --uid 10001 ledger
COPY ledgershield ./ledgershield
COPY backend ./backend
COPY docs/experiments ./docs/experiments
COPY migrations ./migrations
COPY alembic.ini ./
USER ledger
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=45s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3)"
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --no-access-log"]
