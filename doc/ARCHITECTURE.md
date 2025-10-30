# 🏗️ Техническая архитектура Datanauts.co UGC Bot

## Обзор системы

Datanauts.co UGC Bot - это Telegram-бот для создания AI-генерированного UGC контента. Система построена на микросервисной архитектуре с четким разделением ответственности между модулями.

## 🎯 Принципы архитектуры

### 1. **Модульность**
- Каждый handler отвечает за одну область функциональности
- Сервисы изолированы и переиспользуемы
- Утилиты не зависят от бизнес-логики

### 2. **Разделение ответственности**
- **Handlers** - обработка пользовательских действий
- **Services** - интеграция с внешними API
- **Utils** - вспомогательные функции
- **Models** - структура данных

### 3. **Централизованное управление**
- Общий dispatcher для всех handlers
- Централизованное логирование
- Единая точка конфигурации

## 🔄 Потоки данных

### 1. **Пользовательский поток**
```
User → Telegram → Bot → Handler → Service → External API
                ↓
            Database ← Utils ← Response
```

### 2. **Генерация контента**
```
Text Input → TTS Service → Audio File → Video Service → Final Video
     ↓              ↓           ↓            ↓
User State → R2 Storage → R2 Storage → R2 Storage
```

### 3. **Состояние пользователя**
```
FSM State → UserState DB → Handler Logic → Next State
```

## 🗂️ Детальная структура модулей

### **handlers/** - Слой представления

#### **start.py** - Инициализация
```python
# Ответственность: Первое взаимодействие с пользователем
- /start команда
- FAQ и помощь
- Профиль пользователя
- Навигация по основному меню
```

#### **format_selection.py** - Выбор формата видео
```python
# Ответственность: Выбор формата UGC видео
- Отображение экрана выбора формата
- Отправка примеров форматов из R2
- Обработка выбора "говорящая голова"
- Обработка выбора "персонаж с бекграундом"
- Загрузка и валидация фонового видео
- Проверка длительности видео (макс 15 сек)
- Сохранение фонового видео на R2
```

#### **character_selection.py** - Выбор персонажа
```python
# Ответственность: Выбор и навигация по персонажам
- Выбор пола персонажа
- Пагинация галереи (все возрасты вместе)
- Выбор конкретного персонажа
- Автоматическое определение возраста
- Навигация между этапами
```

#### **character_editing.py** - Редактирование
```python
# Ответственность: AI-редактирование персонажей
- Предложение редактирования
- Обработка промптов пользователя
- Интеграция с nano-banana service
- Управление результатами редактирования
- Очистка временных файлов
```

#### **voice_selection.py** - Выбор голоса
```python
# Ответственность: Выбор голоса для озвучки
- Галерея голосов с пагинацией
- Предпросмотр голосов
- Выбор голоса
- Навигация между персонажем и голосом
```

#### **generation.py** - Генерация контента
```python
# Ответственность: Создание финального контента
- TTS генерация
- Проверка длительности аудио
- Видео генерация через fal.ai
- Управление кредитами
- Сохранение в историю
- Обработка ошибок
```

#### **my_generations.py** - История
```python
# Ответственность: Управление историей генераций
- Отображение истории пользователя
- Статистика генераций
- Ссылки на скачивание
- Управление доступом к файлам
```

#### **feedback.py** - Обратная связь
```python
# Ответственность: Коммуникация с пользователями
- Форма обратной связи
- Передача сообщений админам
- Обработка приватных сообщений
```

#### **credits.py** - Кредиты
```python
# Ответственность: Управление кредитной системой
- Отображение баланса
- История операций
- Запросы на пополнение
- Команды для просмотра кредитов
```

#### **navigation.py** - Навигация
```python
# Ответственность: Переходы между разделами
- Возврат в главное меню
- Навигация по UGC процессу
- Команды быстрого доступа
- Обработка команд /main, /create_ads
```

### **services/** - Слой интеграции

#### **elevenlabs_service.py** - TTS
```python
# Интеграция: ElevenLabs API
# Функции:
- tts_to_file() - синтез речи
- _synth_sync() - синхронный вызов API
- Загрузка в R2 storage
- Обработка ошибок API
```

#### **falai_service.py** - Видео
```python
# Интеграция: fal.ai OmniHuman
# Функции:
- generate_talking_head_video() - создание видео
- _sync_generate_talking_head() - синхронный вызов
- Загрузка файлов в fal.ai
- Скачивание результата
- Обработка статусов генерации
```

#### **video_editing_service.py** - Видеомонтаж
```python
# Интеграция: Shotstack API + Modal GPU
# Функции:
- add_subtitles_to_video() - добавление субтитров к видео
- composite_head_with_background() - композитинг персонажа с фоном
- download_video_from_url() - скачивание видео с R2
- Детальное логирование времени выполнения
- Интеграция с autopipeline (subprocess)
```

#### **modal_client.py** - Modal GPU клиент
```python
# Интеграция: Modal GPU сервис
# Функции:
- ModalOverlayClient() - клиент для асинхронной обработки
- submit_overlay_job() - отправка задачи на GPU
- poll_job_status() - проверка статуса задачи
- get_job_result() - получение результата
- process_overlay_async() - полный цикл submit → poll → result
```

#### **nano_banana_service.py** - Редактирование
```python
# Интеграция: fal.ai nano-banana
# Функции:
- edit_character_image() - редактирование изображений
- _sync_edit_character_image() - синхронный вызов
- Обработка промптов пользователя
- Загрузка результатов в R2
```

#### **r2_service.py** - Хранилище
```python
# Интеграция: Cloudflare R2
# Функции:
- upload_file() - загрузка файлов
- download_file() - скачивание файлов
- get_presigned_url() - временные ссылки
- delete_file() - удаление файлов
- configure_lifecycle() - автоочистка
- cleanup_temp_files() - очистка временных файлов
```

#### **scheduler_service.py** - Планировщик
```python
# Интеграция: APScheduler
# Функции:
- setup_scheduler() - настройка планировщика
- daily_statistics() - ежедневная статистика
- cleanup_tasks() - задачи очистки
```

### **utils/** - Слой утилит

#### **logger.py** - Логирование
```python
# Централизованное логирование
- setup_logger() - настройка логгеров
- get_logger() - получение логгера
- Предустановленные логгеры для модулей
- Структурированное форматирование
```

#### **user_state.py** - Состояние
```python
# Управление состоянием пользователя
- Character selection (gender, page)
- Age determination (автоматически при выборе персонажа)
- Voice selection (page, voice_id)
- Character editing (paths, iterations)
- Text input (character_text)
- Audio paths (last_audio)
```

#### **credits.py** - Кредиты
```python
# Кредитная система
- ensure_user() - создание пользователя
- get_credits() - получение баланса
- add_credits() - начисление
- spend_credits() - списание
- Атомарные операции с транзакциями
```

#### **user_storage.py** - Хранилище
```python
# Управление историей генераций
- save_user_generation() - сохранение
- get_user_generations() - получение истории
- get_user_storage_stats() - статистика
- Presigned URLs для доступа к файлам
```

#### **statistics.py** - Статистика
```python
# Аналитика и метрики
- track_user_activity() - отслеживание активности
- get_new_users_count() - новые пользователи
- get_active_users_count() - активные пользователи
- generate_statistics_report() - отчеты
```

#### **files.py** - Файлы
```python
# Работа с файлами персонажей
- list_character_images(gender, page, limit) - объединяет все возрасты
- get_character_image(gender, index) - возвращает (path, age)
- get_character_image_url() - URL для R2
- Кэширование presigned URLs
- Автоматическое определение возраста из папки
```

#### **voices.py** - Голоса
```python
# Управление голосами
- list_voice_samples() - список голосов
- get_voice_sample() - получение голоса
- list_all_voice_samples() - все голоса
- Поддержка R2 и локального хранения
```

#### **audio.py** - Аудио
```python
# Аудио утилиты
- check_audio_duration_limit() - проверка длительности
- Валидация аудио файлов
- Обработка форматов
```

#### **video.py** - Видео
```python
# Видео утилиты
- get_video_duration() - получение длительности видео
- check_video_duration_limit() - проверка лимита (макс 15 сек)
- Поддержка MP4, MOV, AVI форматов
- Использование mutagen/ffprobe/moviepy
```

## 🔄 Паттерны проектирования

### 1. **Repository Pattern**
```python
# В user_state.py
def get_character_gender(tg_id: int) -> Optional[str]:
    with SessionLocal() as db:
        # Абстракция доступа к данным
```

### 2. **Service Layer Pattern**
```python
# В services/
class ElevenLabsService:
    async def tts_to_file(self, text: str, voice_id: str) -> str:
        # Инкапсуляция бизнес-логики
```

### 3. **Factory Pattern**
```python
# В logger.py
def setup_logger(name: str) -> logging.Logger:
    # Создание настроенных логгеров
```

### 4. **Observer Pattern**
```python
# В statistics.py
def track_user_activity(tg_id: int):
    # Отслеживание событий
```

## 🗄️ База данных

### Схема данных
```sql
-- Пользователи
users (id, tg_id, credits, selected_voice_id, created_at)

-- Состояние пользователя
user_state (user_id, selected_character_idx, character_text, 
           character_gender, character_age, character_page, 
           voice_page, original_character_path, edited_character_path, 
           edit_iteration_count, video_format, background_video_path)

-- Активы (файлы)
assets (id, user_id, type, path, r2_key, r2_url, r2_url_expires_at, 
        file_size, version, meta_json, created_at)

-- История кредитов
credit_logs (id, user_id, delta, reason, created_at)

-- Активность пользователей
user_activity (id, user_id, last_activity_date, created_at)

-- История генераций
generation_history (id, user_id, generation_type, r2_video_key, 
                   r2_audio_key, r2_image_key, character_gender, 
                   character_age, text_prompt, credits_spent, created_at)
```

### Индексы
```sql
-- Оптимизация запросов
CREATE INDEX idx_users_tg_id ON users(tg_id);
CREATE INDEX idx_user_state_user_id ON user_state(user_id);
CREATE INDEX idx_assets_user_id ON assets(user_id);
CREATE INDEX idx_credit_logs_user_id ON credit_logs(user_id);
CREATE INDEX idx_generation_history_user_id ON generation_history(user_id);
CREATE INDEX idx_generation_history_created_at ON generation_history(created_at);
```

## 🔐 Безопасность

### 1. **Аутентификация**
- Telegram ID как основной идентификатор
- Проверка приватных чатов
- Валидация пользовательского ввода

### 2. **Авторизация**
- Админские команды только для авторизованных
- Rate limiting для админских команд
- Проверка прав доступа

### 3. **Защита данных**
- Presigned URLs с ограниченным временем жизни
- Шифрование чувствительных данных
- Очистка временных файлов

## 🎬 Видеомонтаж и Modal GPU

### Архитектура гибридной обработки

Для формата "Персонаж с бекграундом" используется гибридная архитектура:

```
Railway (video_editing_service.py)
    ↓
Subprocess: autopipeline.py
    ├─ Скачивание видео (R2)
    ├─ Анализ речи (ffprobe + speech detection)
    ├─ Генерация overlay → Modal GPU (prepare_overlay)
    │   ↓
    │   Modal GPU Service (A10G)
    │   ├─ Background removal (rembg/mediapipe)
    │   ├─ Alpha matting
    │   ├─ Shape masking (circle/rect)
    │   └─ Upload to Shotstack
    ├─ Конфигурация template (Shotstack JSON)
    ├─ Выравнивание субтитров
    └─ Render через Shotstack API
    ↓
Final video URL
```

### Modal GPU интеграция

**Зачем:**
- Обработка overlay на CPU занимала ~10 минут (0.5 fps)
- Modal GPU (A10G) обрабатывает за ~30-60 секунд
- **Ускорение в 10-20 раз**

**Как работает:**
1. `autopipeline.py` проверяет `MODAL_OVERLAY_ENDPOINT` env var
2. Если Modal доступен → отправляет задачу через `ModalOverlayClient`
3. Клиент делает POST запрос → получает `job_id`
4. Polling каждые 5 секунд до статуса `completed`
5. Получение результата (Shotstack URL overlay видео)
6. Fallback на CPU если Modal недоступен

**Стоимость:**
- ~$0.06-0.12 за видео на A10G GPU
- Оплата только за использование (serverless)

### Детальное логирование

Для диагностики производительности реализовано структурированное логирование:

**Префиксы:**
- `[MONTAGE]` - video_editing_service.py
- `[AUTOPIPELINE]` - autopipeline.py
- `[OVERLAY]` - prepare_overlay.py
- `[ASSEMBLE]` - assemble.py (Shotstack)
- `[MODAL]` - Modal GPU клиент
- `[TIMING]` - таймеры выполнения

**Метрики:**
- ⏱️ Длительность каждого этапа
- 📊 Размеры файлов (MB)
- 🚀 Скорость передачи (MB/s)
- 📈 Прогресс обработки (fps для overlay)
- ✅/❌ Статусы операций

**Пример логов:**
```
[MONTAGE] ▶️ Starting video montage for user 12345
[MONTAGE] ⏱️ R2 URL generation completed in 0.05s
[AUTOPIPELINE] ▶️ Starting autopipeline
[AUTOPIPELINE] 🚀 Using Modal GPU service for overlay generation
[MODAL] 📊 Job call_xyz status: processing (elapsed: 10s)
[MODAL] ✅ Job call_xyz completed in 45.2s
[AUTOPIPELINE] ✅ Overlays generated via Modal GPU in 45.2s
[ASSEMBLE] ⏱️ Shotstack render completed in 15.3s (billable: 2.1s)
[MONTAGE] ✅ Video montage completed in 62.8s
```

## 📊 Мониторинг

### Логирование
```python
# Структурированные логи
logger.info(f"[UGC] User {user_id} started generation")
logger.error(f"[TTS] Failed to generate audio: {error}")
logger.warning(f"[R2] Upload failed, using local storage")
logger.info(f"[TIMING] ⏱️ Operation completed in {duration:.2f}s")
```

### Метрики
- Количество пользователей
- Генерации в день
- Использование кредитов
- Ошибки API
- Время отклика сервисов
- **Производительность монтажа:**
  - Время обработки overlay (Modal GPU vs CPU)
  - Время Shotstack render
  - Общее время монтажа
  - Стоимость Modal GPU

## 🚀 Производительность

### Оптимизации
1. **Кэширование**
   - Presigned URLs в памяти
   - Статистика пользователей
   - Настройки персонажей

2. **Асинхронность**
   - Все I/O операции асинхронные
   - Параллельная обработка файлов
   - Неблокирующие API вызовы

3. **Очистка ресурсов**
   - Автоматическая очистка временных файлов
   - Lifecycle policies в R2
   - Периодическая очистка БД

## 🔧 Конфигурация

### Переменные окружения
```bash
# Основные
TELEGRAM_BOT_TOKEN=...
WEBHOOK_URL=...
DATABASE_URL=...

# AI сервисы
ELEVEN_API_KEY=...
FALAI_API_TOKEN=...

# Хранилище
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=...
R2_ENDPOINT_URL=...

# Видеомонтаж
SHOTSTACK_API_KEY=...
SHOTSTACK_STAGE=v1
MODAL_OVERLAY_ENDPOINT=https://user--app-submit.modal.run  # Опционально

# Админка
ADMIN_FEEDBACK_CHAT_ID=...
```

### Константы
```python
# В constants.py
COST_UGC_VIDEO = 1
DEFAULT_CREDITS = 10
MAX_AUDIO_DURATION = 15.0
R2_URL_EXPIRY_HOURS = 24
```

## 🧪 Тестирование

### Стратегия тестирования
1. **Unit тесты** - отдельные функции
2. **Integration тесты** - взаимодействие модулей
3. **E2E тесты** - полные пользовательские сценарии
4. **Load тесты** - производительность

### Тестовые данные
```python
# Фикстуры для тестов
@pytest.fixture
def test_user():
    return User(tg_id=12345, credits=10)

@pytest.fixture
def test_character():
    return {"gender": "male", "age": "young", "index": 0}
```

## 📈 Масштабирование

### Горизонтальное масштабирование
1. **Множественные инстансы бота**
2. **Load balancer для webhook**
3. **Shared database**
4. **Distributed file storage**

### Вертикальное масштабирование
1. **Увеличение ресурсов сервера**
2. **Оптимизация запросов к БД**
3. **Кэширование на уровне приложения**
4. **CDN для статических файлов**

## 🔮 Будущие улучшения

### Архитектурные изменения
1. **Микросервисы** - разделение на отдельные сервисы
2. **Message queues** - асинхронная обработка
3. **Event sourcing** - аудит всех действий
4. **CQRS** - разделение команд и запросов

### Технологические улучшения
1. **GraphQL API** - гибкие запросы
2. **WebSocket** - real-time уведомления
3. **Redis** - кэширование и сессии
4. **Kubernetes** - оркестрация контейнеров

---

**Версия архитектуры**: 2.1  
**Статус**: Production Ready  
**Последнее обновление**: Октябрь 2025

## 📝 История изменений

### v2.1 (Октябрь 2025)
- ✅ Добавлена Modal GPU интеграция для видеомонтажа (10-20x ускорение)
- ✅ Реализовано детальное логирование производительности
- ✅ Добавлен `video_editing_service.py` для монтажа персонажа с бекграундом
- ✅ Интеграция с Shotstack API
- ✅ Гибридная архитектура: Modal GPU + Railway CPU с fallback
- ✅ Утилита `timing.py` для измерения времени выполнения

### v2.0 (Декабрь 2024)
- ✅ Рефакторинг handlers в модульную структуру
- ✅ Централизованное логирование
- ✅ Система форматов видео
- ✅ Cloudflare R2 интеграция
