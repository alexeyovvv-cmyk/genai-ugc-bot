#!/bin/bash
# Быстрое обновление бота в Cloud Run

set -e

echo "🔨 Пересборка Docker образа..."
gcloud builds submit --tag gcr.io/datanauts-asia/genai-ugc-bot

echo "🚀 Развертывание обновленной версии..."
gcloud run deploy genai-ugc-bot \
  --image gcr.io/datanauts-asia/genai-ugc-bot \
  --region europe-north1

echo "✅ Готово! Бот обновлен."
echo "🔗 URL: https://genai-ugc-bot-541938082823.europe-north1.run.app"
echo "📋 Логи: gcloud run services logs read genai-ugc-bot --region europe-north1 --limit 50"
