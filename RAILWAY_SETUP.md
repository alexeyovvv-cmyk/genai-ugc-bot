# Настройка бота на Railway с вебхуками

## 🚀 Быстрая настройка

### 1. Добавь PostgreSQL базу данных (БЕСПЛАТНО)

1. Открой свой проект на Railway
2. Нажми **"New"** → **"Database"** → **"Add PostgreSQL"**
3. Railway автоматически установит переменную `DATABASE_URL` ✅
4. **Важно**: Railway предоставляет 512MB PostgreSQL бесплатно!

### 2. Включи публичный домен

1. В настройках сервиса найди **"Settings"** → **"Networking"**
2. Нажми **"Generate Domain"** (это создаст публичный URL типа `your-app.up.railway.app`)
3. Скопируй этот домен (без https://)

### 3. Настрой переменные окружения

В разделе **"Variables"** добавь:

```
TELEGRAM_BOT_TOKEN=твой_токен_бота
OPENAI_API_KEY=твой_ключ_openai
ELEVEN_API_KEY=твой_ключ_elevenlabs
REPLICATE_API_TOKEN=твой_ключ_replicate
BASE_DIR=/app
RAILWAY_PUBLIC_DOMAIN=your-app.up.railway.app
```

⚠️ **Важно**: `RAILWAY_PUBLIC_DOMAIN` должен быть БЕЗ `https://`, только домен!

Пример: `my-bot-production.up.railway.app`

### 4. Переделплой

После добавления `RAILWAY_PUBLIC_DOMAIN` нажми **"Redeploy"** или просто сделай `git push`

### 5. Проверь логи

В логах должно появиться:
```
Setting webhook to: https://your-app.up.railway.app/webhook
Webhook set successfully!
Starting webhook server on port 8080
```

### 6. Протестируй бота

Напиши боту `/start` в Telegram - он должен ответить!

## 🔍 Проверка статуса

### Проверь что вебхук установлен:

```bash
curl https://api.telegram.org/bot<ТВО_ТОКЕН>/getWebhookInfo
```

Должен показать твой Railway URL.

### Health check:

Открой в браузере: `https://your-app.up.railway.app/health`

Должен показать `OK`

## ❌ Проблемы и решения

### Бот не отвечает?

1. **Проверь логи** - найди ошибки
2. **Проверь переменные** - все ли установлены?
3. **Проверь вебхук**:
   ```bash
   curl https://api.telegram.org/bot<ТОКЕН>/getWebhookInfo
   ```
4. **Перезапусти бот** - иногда помогает

### База данных не работает?

- Убедись что PostgreSQL сервис запущен (зеленая иконка)
- Проверь что `DATABASE_URL` установлена автоматически
- Railway PostgreSQL 512MB бесплатно - никаких доплат!

### Вебхук не устанавливается?

- Проверь что `RAILWAY_PUBLIC_DOMAIN` правильный (БЕЗ https://)
- Проверь что домен сгенерирован в настройках Railway
- Перезапусти деплоймент

## 💰 Стоимость

- **Railway Hobby Plan**: $5/месяц (500 часов = 24/7)
- **PostgreSQL**: **БЕСПЛАТНО** до 512MB
- **Итого**: **$5/месяц** для круглосуточной работы

## ✅ Чек-лист

- [ ] PostgreSQL база добавлена
- [ ] Публичный домен сгенерирован
- [ ] `RAILWAY_PUBLIC_DOMAIN` установлен
- [ ] Все API ключи добавлены
- [ ] Бот передеплоен
- [ ] В логах "Webhook set successfully!"
- [ ] Бот отвечает на `/start`

---

**Готово!** Бот работает 24/7 через вебхуки 🎉

