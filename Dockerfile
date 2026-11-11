FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN python -m pip install --no-cache-dir \
    -r /app/requirements.txt

COPY app /app/app
COPY frontend /app/frontend
COPY data /app/data

EXPOSE 8000 8501
