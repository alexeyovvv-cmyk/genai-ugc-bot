# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей
COPY tg_bot/requirements.txt .

# Обновляем pip и устанавливаем зависимости
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаем директории для данных (если их нет)
RUN mkdir -p data/audio/voices data/characters data/video

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Открываем порт (Railway автоматически назначает PORT)
# EXPOSE будет установлен Railway автоматически

# Команда запуска
CMD ["python", "-m", "tg_bot.main"]
