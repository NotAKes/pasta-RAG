FROM python:3.10-slim

# Оптимизация Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Указываем путь к кэшу моделей сразу в окружении
ENV HF_HOME=/app/hf_cache

WORKDIR /app

# Создаем пользователя и нужные папки одним слоем
RUN useradd -m -s /bin/bash botuser && \
    mkdir -p /app/hf_cache && \
    chown -R botuser:botuser /app

# Устанавливаем системные зависимости и очищаем кэш apt за один раз
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Сначала копируем только requirements для использования кэша слоев
COPY --chown=botuser:botuser requirements.txt .

# Установка зависимостей без кэша pip (экономит 1-2 ГБ в /var)
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем остальной код от имени пользователя
COPY --chown=botuser:botuser . .

# Переключаемся на пользователя (безопасность)
USER botuser

CMD ["python", "main.py"]