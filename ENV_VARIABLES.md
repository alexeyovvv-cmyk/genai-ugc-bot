# 🔧 Переменные окружения для Railway

## ✅ Обязательные переменные

Эти переменные **ОБЯЗАТЕЛЬНО** нужно установить в Railway → Variables:

### 1. Telegram Bot
```
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```
Получить: [@BotFather](https://t.me/BotFather)

### 2. Railway Domain (для вебхуков)
```
RAILWAY_PUBLIC_DOMAIN=your-app-production.up.railway.app
```
⚠️ **БЕЗ** `https://`, только домен!

Как получить:
1. Settings → Networking → Generate Domain
2. Скопируй домен (например: `my-bot.up.railway.app`)

### 3. Base Directory
```
BASE_DIR=/app
```
Стандартное значение для Railway.

## 🔑 API ключи (нужны для работы функций)

### OpenAI (для генерации хуков)
```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```
Получить: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

### ElevenLabs (для генерации голоса)
```
ELEVEN_API_KEY=...
```
Получить: [elevenlabs.io/app/settings/api-keys](https://elevenlabs.io/app/settings/api-keys)

### Replicate (для генерации видео через Veo3)
```
REPLICATE_API_TOKEN=r8_...
```
Получить: [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens)

## 🗄️ База данных

```
DATABASE_URL=postgresql://...
```
⚠️ **Устанавливается автоматически** Railway при добавлении PostgreSQL!

Не нужно вручную добавлять.

## 📝 Полный список для копирования

Скопируй это в Railway → Variables и замени значения:

```
TELEGRAM_BOT_TOKEN=ваш_токен_бота
RAILWAY_PUBLIC_DOMAIN=your-app.up.railway.app
BASE_DIR=/app
OPENAI_API_KEY=ваш_ключ_openai
OPENAI_MODEL=gpt-4o-mini
ELEVEN_API_KEY=ваш_ключ_elevenlabs
REPLICATE_API_TOKEN=ваш_токен_replicate
```

## ⚠️ Важные замечания

1. **RAILWAY_PUBLIC_DOMAIN** - только домен, БЕЗ `https://`
   - ✅ Правильно: `my-bot.up.railway.app`
   - ❌ Неправильно: `https://my-bot.up.railway.app`

2. **DATABASE_URL** - добавляется автоматически при добавлении PostgreSQL

3. **Без этих переменных бот НЕ ЗАПУСТИТСЯ**:
   - `TELEGRAM_BOT_TOKEN` - бот вообще не запустится
   - `RAILWAY_PUBLIC_DOMAIN` - вебхуки не настроятся (бот будет пытаться использовать polling)

4. **Без API ключей соответствующие функции не работают**, но бот запустится

## 🧪 Проверка

После установки переменных:

1. Redeploy бота в Railway
2. Проверь логи - должно быть:
   ```
   Setting webhook to: https://your-domain.up.railway.app/webhook
   Webhook set successfully!
   Starting webhook server on port 8080
   ```
3. Напиши боту `/start`
4. Попробуй каждую функцию

## 🔍 Troubleshooting

### Бот не запускается
```
OpenAIError: The api_key client option must be set
```
**Решение**: Теперь исправлено! Просто git push последние изменения.

### Вебхук не установлен
```
Setting webhook to: https://None/webhook
```
**Решение**: Добавь `RAILWAY_PUBLIC_DOMAIN` в переменные.

### Функции не работают
```
ValueError: ELEVEN_API_KEY not set
```
**Решение**: Добавь соответствующий API ключ.

---

**Готово!** После установки всех переменных бот работает 🎉

