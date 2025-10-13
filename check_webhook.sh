#!/bin/bash

# Скрипт для проверки статуса вебхука Telegram бота

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Проверка статуса вебхука Telegram бота"
echo "=========================================="
echo ""

# Проверяем наличие токена в .env
if [ -f .env ]; then
    source .env
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo -e "${RED}❌ TELEGRAM_BOT_TOKEN не найден${NC}"
    echo "Укажи токен бота:"
    read TELEGRAM_BOT_TOKEN
fi

# Получаем информацию о вебхуке
echo "Запрашиваю информацию о вебхуке..."
echo ""

response=$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo")

# Проверяем успешность запроса
if echo "$response" | grep -q '"ok":true'; then
    echo -e "${GREEN}✅ Запрос успешен${NC}"
    echo ""
    
    # Извлекаем URL вебхука
    webhook_url=$(echo "$response" | grep -o '"url":"[^"]*"' | cut -d'"' -f4)
    
    if [ -z "$webhook_url" ]; then
        echo -e "${YELLOW}⚠️  Вебхук не установлен (бот работает в режиме polling)${NC}"
    else
        echo -e "${GREEN}✅ Вебхук установлен:${NC}"
        echo "   $webhook_url"
    fi
    
    # Проверяем количество ожидающих обновлений
    pending_count=$(echo "$response" | grep -o '"pending_update_count":[0-9]*' | cut -d':' -f2)
    if [ "$pending_count" -gt 0 ]; then
        echo -e "${YELLOW}⚠️  Ожидающих обновлений: $pending_count${NC}"
    else
        echo -e "${GREEN}✅ Ожидающих обновлений: 0${NC}"
    fi
    
    # Проверяем последнюю ошибку
    last_error=$(echo "$response" | grep -o '"last_error_message":"[^"]*"' | cut -d'"' -f4)
    if [ ! -z "$last_error" ]; then
        echo -e "${RED}❌ Последняя ошибка: $last_error${NC}"
    fi
    
    echo ""
    echo "Полный ответ:"
    echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
    
else
    echo -e "${RED}❌ Ошибка при запросе${NC}"
    echo "$response"
fi

echo ""
echo "=========================================="
echo "Для удаления вебхука (переход на polling):"
echo "curl https://api.telegram.org/bot\$TELEGRAM_BOT_TOKEN/deleteWebhook"

