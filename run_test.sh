#!/bin/bash
# Скрипт для запуска тестового бота

echo "🧪 Запускаем тестового бота..."

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден!"
    echo "Создайте файл .env на основе env_template.txt"
    echo "И укажите токен тестового бота от @BotFather"
    exit 1
fi

# Загружаем переменные окружения
export $(cat .env | grep -v '^#' | xargs)

# Проверяем наличие тестового токена
if [ -z "$TELEGRAM_BOT_TOKEN_TEST" ] || [ "$TELEGRAM_BOT_TOKEN_TEST" = "your_test_bot_token_here" ]; then
    echo "❌ TELEGRAM_BOT_TOKEN_TEST не настроен в .env файле!"
    echo "Отредактируйте .env и укажите токен тестового бота"
    exit 1
fi

echo "✅ Переменные окружения загружены"
echo "🧪 Запускаем тестовый бот..."

cd tg_bot_test
python run_test.py
