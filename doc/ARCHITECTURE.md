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

#### **character_selection.py** - Выбор персонажа
```python
# Ответственность: Выбор и навигация по персонажам
- Выбор пола персонажа
- Выбор возраста персонажа
- Пагинация галереи
- Выбор конкретного персонажа
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
- Character selection (gender, age, page)
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
- list_character_images() - список изображений
- get_character_image() - получение изображения
- get_character_image_url() - URL для R2
- Кэширование presigned URLs
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
           edit_iteration_count)

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

## 📊 Мониторинг

### Логирование
```python
# Структурированные логи
logger.info(f"[UGC] User {user_id} started generation")
logger.error(f"[TTS] Failed to generate audio: {error}")
logger.warning(f"[R2] Upload failed, using local storage")
```

### Метрики
- Количество пользователей
- Генерации в день
- Использование кредитов
- Ошибки API
- Время отклика сервисов

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

**Версия архитектуры**: 2.0  
**Статус**: Production Ready  
**Последнее обновление**: Декабрь 2024
