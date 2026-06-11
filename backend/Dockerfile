FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.lock.txt backend/requirements-dev.lock.txt /app/backend/
RUN python -m pip install --no-cache-dir -U pip && \
    python -m pip install --no-cache-dir -r /app/backend/requirements.lock.txt

COPY backend /app/backend

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

