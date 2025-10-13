# 🎉 Обновление: Поддержка вебхуков для Railway

## Что изменилось?

Бот теперь автоматически определяет окружение и использует:
- **Вебхуки** на Railway/production для эффективной работы 24/7
- **Polling** локально для разработки

## ✅ Что сделано

1. ✅ Добавлена автоматическая настройка вебхуков через `RAILWAY_PUBLIC_DOMAIN`
2. ✅ Добавлен `aiohttp>=3.9.0` в requirements.txt
3. ✅ Создан скрипт проверки статуса вебхука: `check_webhook.sh`
4. ✅ Обновлена документация с правильными инструкциями
5. ✅ Исправлена стоимость (PostgreSQL бесплатно до 512MB)

## 🚀 Что нужно сделать в Railway

### Шаг 1: Добавь PostgreSQL (если еще не добавил)

```
New → Database → Add PostgreSQL
```

Railway автоматически установит `DATABASE_URL` ✅

### Шаг 2: Сгенерируй публичный домен

```
Settings → Networking → Generate Domain
```

Скопируй домен (например: `my-bot-production.up.railway.app`)

### Шаг 3: Добавь переменную окружения

В разделе **Variables** добавь:

```
RAILWAY_PUBLIC_DOMAIN=my-bot-production.up.railway.app
```

⚠️ **Важно**: БЕЗ `https://`, только домен!

### Шаг 4: Запушь изменения

```bash
git add .
git commit -m "Add webhook support for Railway"
git push
```

Railway автоматически передеплоит бота.

### Шаг 5: Проверь логи

В Railway логах должно появиться:

```
Setting webhook to: https://my-bot-production.up.railway.app/webhook
Webhook set successfully!
Starting webhook server on port 8080
```

## 🧪 Проверка

### Проверь статус вебхука локально:

```bash
./check_webhook.sh
```

Или вручную:

```bash
curl https://api.telegram.org/bot<ТВОЙ_ТОКЕН>/getWebhookInfo
```

### Проверь health check:

Открой в браузере:
```
https://my-bot-production.up.railway.app/health
```

Должен показать `OK`

### Тестируй бота:

1. Напиши боту `/start`
2. Попробуй сгенерировать аудио
3. Попробуй сгенерировать видео

## 📁 Новые файлы

- `RAILWAY_SETUP.md` - Быстрая инструкция по настройке
- `check_webhook.sh` - Скрипт проверки статуса вебхука
- `WEBHOOK_UPDATE.md` - Это файл (резюме изменений)

## 🔧 Технические детали

### Как работает определение режима:

```python
port = os.getenv("PORT")  # Railway устанавливает автоматически
railway_public_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")  # Ты добавляешь вручную

if port and railway_public_domain:
    # Вебхуки (Railway)
    webhook_url = f"https://{railway_public_domain}/webhook"
    await bot.set_webhook(webhook_url)
else:
    # Polling (локальная разработка)
    await dp.start_polling(bot)
```

### Endpoints:

- `/webhook` - Прием обновлений от Telegram
- `/health` - Health check для Railway
- `/` - Тоже health check

## 💰 Стоимость

- **Railway Hobby**: $5/месяц
- **PostgreSQL**: **БЕСПЛАТНО** (до 512MB)
- **Итого**: **$5/месяц**

## ❓ FAQ

**Q: Нужно ли платить за PostgreSQL?**
A: Нет! Railway дает 512MB бесплатно, этого хватит надолго.

**Q: Бот не отвечает после деплоя?**
A: Проверь что `RAILWAY_PUBLIC_DOMAIN` установлен и домен сгенерирован в настройках.

**Q: Как переключиться обратно на polling?**
A: Просто удали переменную `RAILWAY_PUBLIC_DOMAIN` в Railway.

**Q: Можно ли использовать свой домен?**
A: Да! Просто укажи его в `RAILWAY_PUBLIC_DOMAIN` (без https://).

## 🎯 Следующие шаги

1. Запушь изменения в GitHub
2. Добавь `RAILWAY_PUBLIC_DOMAIN` в Railway
3. Подожди перезапуск
4. Проверь логи
5. Тестируй бота

---

**Готово!** Бот работает через вебхуки 🚀

