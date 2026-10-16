FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app
COPY frontend ./frontend

RUN useradd --create-home --uid 10001 appuser \
    && mkdir /data \
    && mkdir /data/profile-uploads \
    && chown -R appuser:appuser /data

ENV PROFILE_UPLOAD_DIR=/data/profile-uploads

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
