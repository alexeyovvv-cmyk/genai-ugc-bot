# 🚀 Гайд по деплою Modal GPU сервиса

## ✅ Что уже сделано

1. ✅ Создана структура `modal_services/`
2. ✅ Создан Modal сервис `overlay_service.py` с GPU обработкой
3. ✅ Создан клиент `modal_client.py` для Railway
4. ✅ Интегрировано в `autopipeline.py` с fallback на CPU

## 📋 Следующие шаги (выполни сам)

### Шаг 1: Установка Modal CLI (если еще не установлен)

```bash
pip install modal
```

### Шаг 2: Аутентификация Modal

```bash
modal token new
```

Это откроет браузер для авторизации.

### Шаг 3: Создание Modal Secret для Shotstack

Зайди в Modal dashboard: https://modal.com/settings/secrets

Создай новый secret с именем **`shotstack`** и добавь:
- `SHOTSTACK_API_KEY` = твой ключ Shotstack
- `SHOTSTACK_STAGE` = `v1` (или `stage` если используешь тестовый)

### Шаг 4: Деплой Modal сервиса

```bash
cd /home/dev/vibe_coding
modal deploy modal_services/overlay_service.py
```

**Ожидаемый output:**
```
✓ Created function datanauts-overlay.process_overlay
✓ Created web function datanauts-overlay.submit
✓ Created web function datanauts-overlay.status
✓ Created web function datanauts-overlay.result

Web endpoints:
  https://alexeyovvv-cmyk--datanauts-overlay-submit.modal.run
  https://alexeyovvv-cmyk--datanauts-overlay-status.modal.run
  https://alexeyovvv-cmyk--datanauts-overlay-result.modal.run
```

**Скопируй URL для `submit` endpoint!**

> **Примечание:** Код уже обновлен для новой версии Modal API:
> - `modal.App` вместо `modal.Stub`
> - `image.copy_local_dir()` вместо `modal.Mount`

### Шаг 5: Добавить env var в Railway

Зайди в Railway dashboard → твой проект → Variables

Добавь новую переменную:
```
MODAL_OVERLAY_ENDPOINT=https://alexeyovvv-cmyk--datanauts-overlay-submit.modal.run
```

(Замени на свой URL из шага 4)

Railway автоматически перезапустится с новой переменной.

### Шаг 6: Тестирование

#### 6.1 Локальный тест Modal функции (опционально)

```bash
# Тест с реальным видео URL
modal run modal_services/overlay_service.py::process_overlay \
  --video-url "https://твой-тестовый-видео-url.mp4" \
  --engine mediapipe \
  --shape circle
```

#### 6.2 Тест через API (опционально)

```bash
# Submit job
curl -X POST https://твой-submit-url.modal.run \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://test-video.mp4",
    "engine": "mediapipe",
    "shape": "circle"
  }'

# Ответ: {"job_id": "call_xyz123...", "status": "submitted"}

# Check status
curl "https://твой-status-url.modal.run?job_id=call_xyz123"

# Get result
curl "https://твой-result-url.modal.run?job_id=call_xyz123"
```

#### 6.3 End-to-end тест через Telegram бота

1. Создай видео с монтажом через бота (выбери "персонаж с бекграундом")
2. Проверь логи Railway - должны появиться:
   ```
   [AUTOPIPELINE] 🚀 Using Modal GPU service for overlay generation
   [MODAL] 🚀 Submitting job to GPU: engine=mediapipe, shape=circle
   [MODAL] ✅ Job submitted: call_xyz
   [MODAL] 📊 Status: processing (elapsed: 10s)
   [MODAL] 📊 Status: processing (elapsed: 20s)
   [MODAL] ✅ Completed in 45s
   [AUTOPIPELINE] ✅ circle overlay ready
   ```
3. Время обработки должно быть **< 60 секунд** (вместо 10 минут!)

#### 6.4 Тест fallback на CPU

1. Временно удали `MODAL_OVERLAY_ENDPOINT` из Railway
2. Создай видео - должен увидеть:
   ```
   [AUTOPIPELINE] 💻 Using local CPU for overlay generation
   ```
3. Верни env var обратно

## 🎯 Ожидаемые результаты

**До Modal GPU:**
- Время обработки overlay: ~10 минут (0.5 fps на CPU)
- Общее время монтажа: ~12 минут

**После Modal GPU:**
- Время обработки overlay: **30-60 секунд** (5-10 fps на A10G GPU)
- Общее время монтажа: **2-3 минуты**
- **Ускорение в 10-20 раз!** 🔥

## 💰 Стоимость

**Modal A10G GPU:**
- $0.002/секунда = $7.2/час
- Примерно 30-60 секунд на видео = **$0.06-0.12 за видео**
- 100 видео/день = **$6-12/день** = **$180-360/месяц**

Ты платишь **только за время GPU использования**, не за простой.

## 🔧 Troubleshooting

### Проблема: "Modal secret not found"
**Решение:** Убедись что создал secret с именем `shotstack-credentials` в Modal dashboard

### Проблема: "Failed to submit Modal job"
**Решение:** Проверь что `MODAL_OVERLAY_ENDPOINT` правильный (должен заканчиваться на `-submit.modal.run`)

### Проблема: "Modal processing timeout"
**Решение:** 
- Проверь логи Modal: https://modal.com/logs
- Возможно видео слишком длинное или проблема с Shotstack
- Временно используй CPU fallback (убери env var)

### Проблема: URLs не работают после переделья
**Решение:** Modal URLs постоянные, но если передеплоил с другим именем stub/функции - нужно обновить env var

## 📊 Мониторинг

### Modal Dashboard
Зайди в https://modal.com/apps чтобы посмотреть:
- Логи всех вызовов
- Время выполнения
- Использование GPU
- Стоимость

### Railway Логи
Смотри логи autopipeline для:
- `[AUTOPIPELINE] 🚀 Using Modal GPU service` - использует Modal
- `[AUTOPIPELINE] 💻 Using local CPU` - использует CPU fallback
- `[MODAL] ✅ Completed in Xs` - время обработки Modal

## 🎉 Готово!

После выполнения всех шагов твой бот будет использовать GPU для обработки видео, что даст **10-20x ускорение**!

Если есть проблемы - проверь логи Modal и Railway.

