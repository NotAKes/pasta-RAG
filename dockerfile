# syntax=docker/dockerfile:1

# Comments are provided throughout this file to help you get started.
# If you need more help, visit the Dockerfile reference guide at
# https://docs.docker.com/go/dockerfile-reference/

# Want to help us make this template better? Share your feedback here: https://forms.gle/ybq9Krt8jtBL3iCk7

FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1

ENV PYTHONUNBUFFERED=1

WORKDIR /app

ARG UID=10001

RUN useradd -m -s /bin/bash botuser

RUN mkdir -p /app/hf_cache && chown -R botuser:botuser /app/hf_cache

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/model_cache && chmod 777 /app/model_cache

RUN mkdir -p /nonexistent && chmod 777 /nonexistent

RUN pip install --upgrade pip

RUN python --version

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    python -m pip install -r requirements.txt

RUN chown -R botuser:botuser /app



USER botuser

COPY . .

USER root

# RUN ping api.telegram.org

CMD ["python", "main.py"]
