#!/bin/bash
# Скрипт для запуска продакшн бота

echo "🚀 Запускаем продакшн бота..."

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден!"
    echo "Создайте файл .env на основе env_template.txt"
    echo "И укажите токен продакшн бота от @BotFather"
    exit 1
fi

# Загружаем переменные окружения
export $(cat .env | grep -v '^#' | xargs)

# Проверяем наличие токена
if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ "$TELEGRAM_BOT_TOKEN" = "your_production_bot_token_here" ]; then
    echo "❌ TELEGRAM_BOT_TOKEN не настроен в .env файле!"
    echo "Отредактируйте .env и укажите токен продакшн бота"
    exit 1
fi

echo "✅ Переменные окружения загружены"
echo "🏭 Запускаем продакшн бот..."

cd tg_bot
python main.py
