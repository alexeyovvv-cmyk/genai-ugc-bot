# Deploy Modal Overlay Service

## Что изменилось

Добавлен параметр `circle_auto_center` для автоматического определения центра круга по маске лица.

## Деплой

```bash
cd /home/dev/vibe_coding/modal_services

# Deploy the service
modal deploy overlay_service.py
```

После деплоя Modal выдаст новые URL endpoints. Обнови `MODAL_OVERLAY_ENDPOINT` в Railway (если используется).

## Проверка

После деплоя автоцентровка круга заработает:
- По умолчанию: `circle_auto_center=True` (автоопределение)
- Ручной режим: передать `--no-circle-auto-center` в autopipeline

## Примечание

Modal автоматически обновит `video_editing/` директорию в образе при деплое, так что обновлённый `prepare_overlay.py` будет использован.

