ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/hf_cache

WORKDIR /app

# Создаем пользователя и все нужные папки заранее
RUN useradd -m -s /bin/bash botuser && \
    mkdir -p /app/hf_cache /app/model_weights && \
    touch /app/logs.log && \
    chown -R botuser:botuser /app && \
    chmod -R 775 /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --chown=botuser:botuser requirements.txt .
USER botuser
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY --chown=botuser:botuser . .

# Даем финальные права перед переключением пользователя


CMD ["python", "main.py"]