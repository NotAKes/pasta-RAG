FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# 1. Обновляем npm до последней версии перед установкой пакетов
#RUN npm install -g npm@latest

COPY frontend/package*.json ./

# Устанавливаем зависимости
RUN npm install

# Копируем исходники и собираем
COPY frontend/ ./
RUN npm run build

# --- ЭТАП 2: Бэкенд (Python + FastAPI + Bot) ---
FROM python:3.10-slim

# Переменные окружения для Python и HuggingFace
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/hf_cache

WORKDIR /app

# 2. Устанавливаем системные зависимости
# libpq-dev нужен для PostgreSQL, curl для healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 3. Обновляем pip и устанавливаем зависимости
# --no-cache-dir ВАЖЕН для экономии места!
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Копируем собранный фронтенд из первого этапа
COPY --from=frontend-builder /app/frontend/dist /app/static

# Запуск через uvicorn (как мы и обсуждали для продакшена)
# Убедись, что файл называется api.py, а внутри app = FastAPI()
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
