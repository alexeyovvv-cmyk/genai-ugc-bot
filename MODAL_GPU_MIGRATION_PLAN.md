# 🚀 План миграции видео-монтажа на Modal GPU

## 📊 Текущее состояние

### Проблема
- **Railway CPU**: Обработка видео занимает **10-15 минут** (0.5 fps)
- **Узкое место**: `prepare_overlay.py` - удаление фона через rembg/mediapipe
- **Попытка оптимизации**: Мультипроцессинг упал из-за нехватки ресурсов Railway
  - Error: `pthread_create failed, error code: 11 - Resource temporarily unavailable`
  - Причина: Каждый worker создаёт ONNX Runtime сессию → исчерпание памяти/threads

### Архитектура сейчас
```
User → Telegram Bot (Railway) 
         ↓
     video_editing_service.py
         ↓
     subprocess: autopipeline.py (CPU)
         ↓
     prepare_overlay.py (МЕДЛЕННО 🐢 - 10 минут)
         ↓
     Shotstack API → готовое видео
```

---

## 🎯 Целевая архитектура с Modal GPU

```
User → Telegram Bot (Railway)
         ↓
     video_editing_service.py
         ↓
     Modal GPU API (HTTP request) 🚀
         ↓
     prepare_overlay.py на A10G GPU
         ↓
     Shotstack API → готовое видео
```

**Ожидаемая производительность:**
- На A10G GPU: **5-10 fps** (вместо 0.5 fps)
- Время обработки: **30-60 секунд** (вместо 10 минут)
- **Прирост: 10-20x быстрее!** 🔥

---

## 🏗️ План миграции (пошагово)

### **Этап 1: Настройка Modal** (30 минут)

#### 1.1 Установка Modal CLI
```bash
pip install modal
```

#### 1.2 Создание Modal аккаунта и токена
```bash
modal token new
```

#### 1.3 Создание secrets в Modal dashboard
- `SHOTSTACK_API_KEY` - API ключ Shotstack
- Опционально: `SHOTSTACK_STAGE` (по умолчанию "stage")

---

### **Этап 2: Создание Modal GPU сервиса** (1-2 часа)

#### 2.1 Создать файл `modal_video_overlay_service.py`

```python
"""
Modal GPU service для обработки video overlay с удалением фона.
Запускается на A10G GPU, обрабатывает видео за 30-60 секунд.
"""
import modal
from pathlib import Path
import tempfile
import sys

# Определить Modal stub
stub = modal.Stub("datanauts-video-overlay")

# GPU-образ с нужными библиотеками
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "ffmpeg",
        "libgl1",
        "libglib2.0-0",
        "libsm6",
        "libxext6",
        "libxrender1",
        "libgomp1"
    )
    .pip_install(
        "opencv-python==4.8.1.78",
        "mediapipe==0.10.8",
        "numpy==1.24.3",
        "requests==2.31.0",
        "rembg==2.0.50",
        "onnxruntime-gpu==1.16.3",  # GPU версия!
        "pillow==10.1.0",
    )
)

# Монтирование локальных файлов
video_editing_mount = modal.Mount.from_local_dir(
    "./video_editing",
    remote_path="/root/video_editing"
)

@stub.function(
    gpu="A10G",  # GPU: A10G (~$0.002/сек = $7.2/час, но платим только за использование)
    # Альтернативы: "T4" (дешевле), "A100" (быстрее, дороже)
    image=image,
    mounts=[video_editing_mount],
    timeout=600,  # 10 минут макс
    secrets=[modal.Secret.from_name("shotstack-credentials")],
    # Настройки для оптимизации
    cpu=2.0,  # CPU cores для параллельной работы с GPU
    memory=4096,  # 4GB RAM
)
def process_video_overlay(
    video_url: str,
    container: str = "mov",
    threshold: float = 0.6,
    feather: int = 7,
    engine: str = "mediapipe",  # или "rembg"
    rembg_model: str = "u2net_human_seg",
    shape: str = "circle",
    circle_radius: float = 0.35,
    circle_center_x: float = 0.5,
    circle_center_y: float = 0.5,
) -> dict:
    """
    Обработка видео на GPU: удаление фона и создание прозрачного оверлея.
    
    Args:
        video_url: URL исходного видео
        container: "mov" или "webm"
        threshold: порог сегментации (0.0-1.0)
        feather: размер размытия краёв
        engine: "mediapipe" (быстрее) или "rembg" (качественнее)
        rembg_model: модель rembg (если engine="rembg")
        shape: "rect" или "circle"
        circle_*: параметры круглой маски
        
    Returns:
        dict с:
          - overlay_url: URL готового оверлея на Shotstack
          - duration: длительность видео
          - processing_time: время обработки
    """
    import sys
    import os
    import time
    sys.path.insert(0, "/root/video_editing")
    
    import prepare_overlay
    
    start_time = time.time()
    
    # Получить credentials из secrets
    shotstack_api_key = os.environ["SHOTSTACK_API_KEY"]
    shotstack_stage = os.environ.get("SHOTSTACK_STAGE", "stage")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / f"overlay_{shape}.{container}"
        
        # Вызвать существующую функцию prepare_overlay
        overlay_url = prepare_overlay.prepare_overlay(
            video_url,
            output_path,
            shotstack_stage,
            shotstack_api_key,
            container,
            threshold=threshold,
            feather=feather,
            debug=False,
            engine=engine,
            rembg_model=rembg_model,
            rembg_alpha_matting=False,
            rembg_fg_threshold=240,
            rembg_bg_threshold=10,
            rembg_erode_size=10,
            rembg_base_size=1000,
            shape=shape,
            circle_radius=circle_radius,
            circle_center_x=circle_center_x,
            circle_center_y=circle_center_y,
        )
        
        processing_time = time.time() - start_time
        
        return {
            "overlay_url": overlay_url,
            "processing_time": processing_time,
            "status": "success"
        }

# Web endpoint для вызова из Railway
@stub.function(image=image)
@modal.web_endpoint(method="POST")
def process_overlay_endpoint(data: dict):
    """
    REST API endpoint для асинхронной обработки.
    
    POST /process_overlay_endpoint
    Body: {
        "video_url": "https://...",
        "container": "mov",
        "engine": "mediapipe",
        "shape": "circle",
        ...
    }
    
    Returns:
        {"job_id": "call_xyz123..."}
    """
    # Запустить обработку асинхронно
    call = process_video_overlay.spawn(**data)
    return {"job_id": call.object_id, "status": "processing"}

@stub.function(image=image)
@modal.web_endpoint(method="GET")
def get_result(job_id: str):
    """
    Получить результат обработки.
    
    GET /get_result?job_id=call_xyz123
    
    Returns:
        - {"status": "processing"} - ещё обрабатывается
        - {"status": "completed", "result": {...}} - готово
        - {"status": "failed", "error": "..."} - ошибка
    """
    from modal.functions import FunctionCall
    
    try:
        call = FunctionCall.from_id(job_id)
        
        try:
            result = call.get(timeout=0)  # Не ждать
            return {"status": "completed", "result": result}
        except TimeoutError:
            return {"status": "processing"}
            
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}

# Синхронный endpoint (для простоты)
@stub.function(
    gpu="A10G",
    image=image,
    mounts=[video_editing_mount],
    timeout=600,
    secrets=[modal.Secret.from_name("shotstack-credentials")],
    cpu=2.0,
    memory=4096,
)
@modal.web_endpoint(method="POST")
def process_overlay_sync(data: dict):
    """
    Синхронный endpoint - ждёт завершения обработки.
    
    POST /process_overlay_sync
    Body: {"video_url": "...", ...}
    
    Returns: {"overlay_url": "...", "processing_time": 45.2}
    """
    return process_video_overlay.local(**data)
```

#### 2.2 Деплой на Modal
```bash
cd /home/dev/vibe_coding
modal deploy modal_video_overlay_service.py
```

**Output:**
```
✓ Created function datanauts-video-overlay.process_video_overlay
✓ Created web function datanauts-video-overlay.process_overlay_sync
✓ View at https://modal.com/apps/YOUR_USERNAME/datanauts-video-overlay

Web endpoints:
  https://YOUR_USERNAME--datanauts-video-overlay-process-overlay-sync.modal.run
  https://YOUR_USERNAME--datanauts-video-overlay-process-overlay-endpoint.modal.run
  https://YOUR_USERNAME--datanauts-video-overlay-get-result.modal.run
```

---

### **Этап 3: Интеграция с Railway** (1 час)

#### 3.1 Создать `modal_client.py` в `tg_bot/services/`

```python
"""
Клиент для вызова Modal GPU service для видео-монтажа.
"""
import requests
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ModalOverlayClient:
    """Клиент для Modal GPU service обработки video overlay."""
    
    def __init__(self, modal_endpoint_url: str):
        """
        Args:
            modal_endpoint_url: URL Modal web endpoint
                Например: https://username--app-function.modal.run
        """
        self.endpoint_url = modal_endpoint_url.rstrip('/')
        
    def process_overlay_sync(
        self,
        video_url: str,
        container: str = "mov",
        engine: str = "mediapipe",
        shape: str = "circle",
        **kwargs
    ) -> str:
        """
        Синхронная обработка overlay (ждёт завершения).
        
        Args:
            video_url: URL исходного видео
            container: "mov" или "webm"
            engine: "mediapipe" или "rembg"
            shape: "rect" или "circle"
            **kwargs: дополнительные параметры
            
        Returns:
            str: URL готового overlay на Shotstack
            
        Raises:
            Exception: при ошибке обработки
        """
        logger.info(f"[MODAL] 🚀 Sending overlay request to GPU (engine={engine}, shape={shape})")
        
        payload = {
            "video_url": video_url,
            "container": container,
            "engine": engine,
            "shape": shape,
            **kwargs
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(
                self.endpoint_url,
                json=payload,
                timeout=600,  # 10 минут макс
            )
            response.raise_for_status()
            result = response.json()
            
            elapsed = time.time() - start_time
            
            overlay_url = result.get("overlay_url")
            processing_time = result.get("processing_time", elapsed)
            
            logger.info(f"[MODAL] ✅ GPU processing completed in {processing_time:.1f}s")
            logger.info(f"[MODAL] 📊 Total request time: {elapsed:.1f}s")
            logger.info(f"[MODAL] 🔗 Overlay URL: {overlay_url}")
            
            return overlay_url
            
        except requests.Timeout:
            logger.error(f"[MODAL] ❌ Request timeout after {time.time() - start_time:.0f}s")
            raise Exception("Modal GPU processing timeout")
        except requests.RequestException as exc:
            logger.error(f"[MODAL] ❌ Request failed: {exc}")
            raise Exception(f"Modal GPU service error: {exc}")
```

#### 3.2 Модифицировать `autopipeline.py`

Добавить функцию для использования Modal вместо локальной обработки:

```python
# В начало файла
import os

def generate_overlay_urls_modal(
    head_url: str,
    shapes: list[str],
    container: str,
    engine: str,
    rembg_model: str,
    modal_endpoint_url: str,
) -> dict[str, str]:
    """
    Генерация оверлеев через Modal GPU service.
    """
    from modal_client import ModalOverlayClient
    
    client = ModalOverlayClient(modal_endpoint_url)
    urls = {}
    
    for shape in shapes:
        logger.info(f"[AUTOPIPELINE] ▶️ Sending {shape} overlay to Modal GPU")
        
        overlay_url = client.process_overlay_sync(
            video_url=head_url,
            container=container,
            engine=engine,
            rembg_model=rembg_model,
            shape=shape,
            circle_radius=0.35,
            circle_center_x=0.5,
            circle_center_y=0.5,
        )
        
        logger.info(f"[AUTOPIPELINE] ✅ {shape} overlay ready: {overlay_url}")
        urls[shape] = overlay_url
    
    return urls

# Модифицировать generate_overlay_urls() для поддержки Modal
def generate_overlay_urls(head_url, shapes, container, stage, api_key, engine, rembg_model):
    """Генерация оверлеев - локально или через Modal GPU."""
    
    # Проверить, настроен ли Modal endpoint
    modal_endpoint = os.getenv("MODAL_OVERLAY_ENDPOINT")
    
    if modal_endpoint:
        logger.info("[AUTOPIPELINE] 🚀 Using Modal GPU service for overlay generation")
        return generate_overlay_urls_modal(
            head_url, shapes, container, engine, rembg_model, modal_endpoint
        )
    else:
        logger.info("[AUTOPIPELINE] 💻 Using local CPU for overlay generation")
        # Существующая локальная логика
        # ...
```

#### 3.3 Добавить environment variable в Railway

В Railway dashboard → Environment Variables:

```bash
MODAL_OVERLAY_ENDPOINT=https://YOUR_USERNAME--datanauts-video-overlay-process-overlay-sync.modal.run
```

---

### **Этап 4: Тестирование** (30 минут)

#### 4.1 Локальное тестирование Modal
```bash
# Запустить Modal функцию локально (для теста)
modal run modal_video_overlay_service.py::process_video_overlay \
  --video-url "https://example.com/video.mp4" \
  --engine mediapipe \
  --shape circle
```

#### 4.2 Тестирование через Web endpoint
```bash
curl -X POST https://YOUR_ENDPOINT.modal.run \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "engine": "mediapipe",
    "shape": "circle"
  }'
```

#### 4.3 End-to-end тест через Telegram Bot
1. Запустить Railway с `MODAL_OVERLAY_ENDPOINT`
2. Создать видео с монтажом через бота
3. Проверить логи:
   - `[AUTOPIPELINE] 🚀 Using Modal GPU service`
   - `[MODAL] ✅ GPU processing completed in X.Xs`
4. Убедиться, что время обработки < 60 секунд

---

### **Этап 5: Мониторинг и оптимизация** (ongoing)

#### 5.1 Мониторинг Modal
- Modal dashboard: https://modal.com/apps
- Метрики: время выполнения, GPU utilization, стоимость
- Логи всех вызовов

#### 5.2 Оптимизация стоимости

**Выбор GPU:**
- **T4**: $0.60/час (~$0.01 за видео) - дешевле, медленнее
- **A10G**: $7.20/час (~$0.03 за видео) - оптимально
- **A100**: $18/час (~$0.08 за видео) - быстрее, дороже

**Стратегии:**
- Keep-warm: оставить 1 instance прогретым (для холодных стартов)
- Batch processing: обрабатывать несколько видео подряд
- Engine optimization: mediapipe быстрее rembg

#### 5.3 Fallback на CPU

Добавить logic для fallback на локальную обработку при недоступности Modal:

```python
try:
    return generate_overlay_urls_modal(...)
except Exception as exc:
    logger.warning(f"[AUTOPIPELINE] ⚠️ Modal GPU failed: {exc}")
    logger.info(f"[AUTOPIPELINE] 💻 Falling back to local CPU processing")
    # Локальная обработка
```

---

## 💰 Стоимость

### Modal A10G GPU
- **Цена**: $0.002/секунда = $7.2/час
- **Обработка**: ~30-60 секунд на видео
- **Стоимость за видео**: $0.06-0.12
- **100 видео/день**: $6-12/день = $180-360/месяц

### Сравнение с Railway
- **Railway Pro**: ~$20/месяц (фиксированно, но медленно)
- **Modal**: pay-per-use (быстрее, дороже при больших объёмах)

**Рекомендация:**
- До 200 видео/день: Modal выгоднее (на demand)
- Более 200 видео/день: подумать о dedicated GPU

---

## 🎯 Критерии успеха

✅ **Производительность:**
- Обработка overlay: < 60 секунд (было 10 минут)
- Общее время монтажа: < 2 минут (было 12 минут)

✅ **Надёжность:**
- Успешность обработки: > 95%
- Fallback на CPU при недоступности Modal

✅ **Стоимость:**
- Прогнозируемая стоимость: < $500/месяц (при 100 видео/день)

---

## 🚀 План действий (чеклист)

- [ ] **Этап 1: Настройка Modal** (30 мин)
  - [ ] Установить Modal CLI
  - [ ] Создать токен
  - [ ] Создать secrets

- [ ] **Этап 2: Создание сервиса** (1-2 часа)
  - [ ] Создать `modal_video_overlay_service.py`
  - [ ] Задеплоить на Modal
  - [ ] Протестировать endpoints

- [ ] **Этап 3: Интеграция** (1 час)
  - [ ] Создать `modal_client.py`
  - [ ] Модифицировать `autopipeline.py`
  - [ ] Добавить env var в Railway

- [ ] **Этап 4: Тестирование** (30 мин)
  - [ ] Локальный тест Modal
  - [ ] Тест через API
  - [ ] End-to-end тест через бота

- [ ] **Этап 5: Production** (ongoing)
  - [ ] Мониторинг метрик
  - [ ] Оптимизация стоимости
  - [ ] Настройка fallback

**Общее время: 3-4 часа** ⏱️

---

## 📚 Дополнительные ресурсы

- Modal Docs: https://modal.com/docs
- Modal Examples: https://github.com/modal-labs/modal-examples
- Modal GPU Pricing: https://modal.com/pricing
- Shotstack API: https://shotstack.io/docs/api

---

**Готов начать миграцию?** 🚀

