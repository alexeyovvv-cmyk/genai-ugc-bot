# 🛠️ Руководство по разработке Datanauts.co UGC Bot

## 📁 Структура проекта

### Основные директории
```
tg_bot/
├── main.py              # Точка входа (130 строк)
├── dispatcher.py         # Общий dispatcher
├── startup.py           # Инициализация
├── config.py            # Конфигурация
├── db.py                # База данных
├── models.py            # SQLAlchemy модели
├── states.py            # FSM состояния
├── keyboards.py         # Inline клавиатуры
├── admin.py             # Админские команды
├── handlers/            # Обработчики (9 модулей)
├── services/            # Внешние сервисы (5 модулей)
└── utils/               # Утилиты (10 модулей)
```

## 🔧 Разработка новых функций

### 1. Добавление нового handler

#### Шаг 1: Создать файл handler
```python
# handlers/new_feature.py
from aiogram import F
from aiogram.types import CallbackQuery, Message
from tg_bot.dispatcher import dp
from tg_bot.utils.logger import setup_logger

logger = setup_logger(__name__)

@dp.callback_query(F.data == "new_feature")
async def new_feature_handler(c: CallbackQuery):
    """Описание функции"""
    logger.info(f"User {c.from_user.id} used new feature")
    await c.message.answer("New feature response")
    await c.answer()
```

#### Шаг 2: Добавить в __init__.py
```python
# handlers/__init__.py
def register_all_handlers(dp: Dispatcher):
    from . import (
        start,
        character_selection,
        # ... existing handlers
        new_feature  # Добавить новый handler
    )
```

#### Шаг 3: Добавить клавиатуру (если нужно)
```python
# keyboards.py
def new_feature_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Action 1", callback_data="action_1")],
        [InlineKeyboardButton(text="Action 2", callback_data="action_2")],
        [InlineKeyboardButton(text="← Назад", callback_data="back_to_main")]
    ])
```

### 2. Добавление нового сервиса

#### Шаг 1: Создать сервис
```python
# services/new_service.py
import asyncio
from typing import Optional
from tg_bot.utils.logger import setup_logger

logger = setup_logger(__name__)

async def new_service_function(param: str) -> Optional[str]:
    """Описание сервиса"""
    try:
        logger.info(f"Starting new service with param: {param}")
        
        # Логика сервиса
        result = await some_async_operation(param)
        
        logger.info(f"Service completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Service failed: {e}")
        return None
```

#### Шаг 2: Добавить логгер
```python
# utils/logger.py
# Добавить в конец файла
new_service_logger = setup_logger("new_service")
```

### 3. Добавление новой утилиты

#### Шаг 1: Создать утилиту
```python
# utils/new_utility.py
from typing import List, Optional
from tg_bot.utils.logger import setup_logger

logger = setup_logger(__name__)

def new_utility_function(data: List[str]) -> Optional[str]:
    """Описание утилиты"""
    try:
        logger.info(f"Processing {len(data)} items")
        
        # Логика утилиты
        result = process_data(data)
        
        logger.info("Utility completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Utility failed: {e}")
        return None
```

## 🎬 Работа с форматами видео

### Выбор формата видео

Бот поддерживает два формата UGC видео:

1. **Говорящая голова** (`talking_head`) - классический формат с AI-персонажем
2. **Персонаж с бекграундом** (`character_with_background`) - персонаж на фоне пользовательского видео

### Проверка длительности видео

```python
from tg_bot.utils.video import check_video_duration_limit

# Проверить длительность видео (макс 15 сек)
is_valid, duration = check_video_duration_limit("video.mp4", max_seconds=15.0)

if is_valid:
    print(f"Video OK: {duration:.1f}s")
else:
    print(f"Video too long: {duration:.1f}s, max 15s")
```

### Работа с фоновыми видео

Фоновые видео хранятся на R2 в структуре `users/{user_id}/backgrounds/`:

```python
from tg_bot.utils.user_state import set_background_video_path, get_background_video_path
from tg_bot.services.r2_service import upload_file

# Загрузить фоновое видео на R2
r2_key = f"users/{user_id}/backgrounds/background_{timestamp}.mp4"
upload_file(local_path, r2_key)

# Сохранить путь в состоянии пользователя
set_background_video_path(user_id, r2_key)

# Получить путь к фоновому видео
bg_path = get_background_video_path(user_id)
```

### Добавление новых форматов

Чтобы добавить новый формат видео:

1. Добавить новое значение в `video_format` (models.py)
2. Создать кнопку в `format_selection_menu()` (keyboards.py)
3. Добавить handler в `format_selection.py`
4. Загрузить пример формата в `examples/{format_name}.mp4` на R2

### Примеры форматов на R2

Примеры форматов хранятся в папке `examples/` на R2:
- `examples/talking_head.mp4` - пример говорящей головы
- `examples/character_with_background.mp4` - пример персонажа с бекграундом

Для создания/обновления примеров используйте скрипт:
```bash
python create_r2_examples.py
```

## 🗄️ Работа с базой данных

### Добавление новой модели
```python
# models.py
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from .db import Base

class NewModel(Base):
    __tablename__ = "new_table"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    data = Column(Text)
    created_at = Column(DateTime, default=func.now())
```

### Создание миграции
```python
# startup.py
# Добавить в функцию setup_startup()
migration_sql = """
ALTER TABLE users ADD COLUMN IF NOT EXISTS new_field VARCHAR;
CREATE TABLE IF NOT EXISTS new_table (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
conn.execute(text(migration_sql))
```

### Работа с данными
```python
# В любом модуле
from sqlalchemy import select
from tg_bot.db import SessionLocal
from tg_bot.models import NewModel

def get_user_data(user_id: int):
    with SessionLocal() as db:
        data = db.scalar(
            select(NewModel).where(NewModel.user_id == user_id)
        )
        return data

# Пример работы с персонажами (новая сигнатура)
from tg_bot.utils.files import list_character_images, get_character_image

# Получить всех персонажей для пола
images, has_next = list_character_images("male", page=0, limit=5)
for image_path, age in images:
    print(f"Character: {image_path}, Age: {age}")

# Получить конкретного персонажа
character_data = get_character_image("male", 0)
if character_data:
    image_path, age = character_data
    print(f"Selected: {image_path}, Age: {age}")
```

## 🎨 Создание клавиатур

### Простая клавиатура
```python
# keyboards.py
def simple_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Кнопка 1", callback_data="button_1")],
        [InlineKeyboardButton(text="Кнопка 2", callback_data="button_2")],
    ])
```

### Клавиатура с пагинацией
```python
# keyboards.py
def paginated_menu(page: int, has_next: bool, total: int):
    buttons = []
    
    # Основные кнопки
    for i in range(5):
        buttons.append([InlineKeyboardButton(
            text=f"Item {page * 5 + i + 1}",
            callback_data=f"item_{page * 5 + i}"
        )])
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="← Предыдущая",
            callback_data=f"page_{page - 1}"
        ))
    if has_next:
        nav_buttons.append(InlineKeyboardButton(
            text="Следующая →",
            callback_data=f"page_{page + 1}"
        ))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton(
        text="← Назад",
        callback_data="back_to_main"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
```

### Клавиатура с состояниями
```python
# keyboards.py
def state_dependent_menu(user_state: str):
    if user_state == "editing":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Продолжить", callback_data="continue")],
            [InlineKeyboardButton(text="Завершить", callback_data="finish")],
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Начать", callback_data="start")],
        ])
```

## 🔄 Работа с состояниями FSM

### Добавление нового состояния
```python
# states.py
from aiogram.fsm.state import StatesGroup, State

class NewFeatureStates(StatesGroup):
    waiting_input = State()
    processing = State()
    waiting_confirmation = State()
```

### Использование состояний
```python
# handlers/new_feature.py
from tg_bot.states import NewFeatureStates

@dp.callback_query(F.data == "start_new_feature")
async def start_new_feature(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Введите данные:")
    await state.set_state(NewFeatureStates.waiting_input)

@dp.message(NewFeatureStates.waiting_input)
async def process_input(m: Message, state: FSMContext):
    # Обработка ввода
    await state.set_state(NewFeatureStates.processing)
    # ... логика обработки
```

## 📊 Логирование

### Использование логгера
```python
from tg_bot.utils.logger import setup_logger

logger = setup_logger(__name__)

# Разные уровни логирования
logger.info("Информационное сообщение")
logger.warning("Предупреждение")
logger.error("Ошибка")
logger.debug("Отладочная информация")
```

### Структурированное логирование
```python
# Логирование с контекстом
logger.info(f"[FEATURE] User {user_id} started action with param: {param}")

# Логирование ошибок с traceback
try:
    risky_operation()
except Exception as e:
    logger.error(f"[FEATURE] Operation failed: {e}")
    import traceback
    logger.error(f"Traceback: {traceback.format_exc()}")
```

## 🧪 Тестирование

### Unit тесты
```python
# tests/test_utils.py
import pytest
from tg_bot.utils.new_utility import new_utility_function

def test_new_utility_function():
    # Arrange
    test_data = ["item1", "item2", "item3"]
    
    # Act
    result = new_utility_function(test_data)
    
    # Assert
    assert result is not None
    assert len(result) > 0
```

### Integration тесты
```python
# tests/test_handlers.py
import pytest
from aiogram import Bot
from aiogram.types import CallbackQuery, User, Chat
from tg_bot.handlers.new_feature import new_feature_handler

@pytest.mark.asyncio
async def test_new_feature_handler():
    # Создать мок объекты
    user = User(id=12345, is_bot=False, first_name="Test")
    chat = Chat(id=12345, type="private")
    callback_query = CallbackQuery(
        id="test_id",
        from_user=user,
        chat_instance="test",
        data="new_feature"
    )
    
    # Выполнить тест
    await new_feature_handler(callback_query)
    
    # Проверить результат
    assert True  # Добавить проверки
```

## 🚀 Деплой

### Локальная разработка
```bash
# Запуск в режиме разработки
python -m tg_bot.main

# С переменными окружения
TELEGRAM_BOT_TOKEN=your_token python -m tg_bot.main
```

### Railway деплой
```bash
# 1. Подключить GitHub репозиторий к Railway
# 2. Настроить переменные окружения в Railway dashboard
# 3. Деплой произойдет автоматически при push в main
```

### Переменные окружения для Railway
```bash
# Обязательные
TELEGRAM_BOT_TOKEN=your_bot_token
WEBHOOK_URL=https://your-app.railway.app/webhook
DATABASE_URL=postgresql://user:pass@host:port/db

# AI сервисы
ELEVEN_API_KEY=your_elevenlabs_key
FALAI_API_TOKEN=your_falai_token

# R2 Storage
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=your_bucket
R2_ENDPOINT_URL=https://your-account.r2.cloudflarestorage.com

# Видеомонтаж (Shotstack)
SHOTSTACK_API_KEY=your_shotstack_key
SHOTSTACK_STAGE=v1

# Modal GPU (опционально, для ускорения монтажа)
MODAL_OVERLAY_ENDPOINT=https://user--app-submit.modal.run

# Админка
ADMIN_FEEDBACK_CHAT_ID=your_admin_chat_id
```

### Modal GPU деплой

**Для ускорения видеомонтажа в 10-20 раз используется Modal GPU:**

#### 1. Установка Modal CLI
```bash
pip install modal
modal token new  # Авторизация
```

#### 2. Создание secrets в Modal
```bash
# Создать secret "shotstuck" с:
# - SHOTSTACK_API_KEY
# - SHOTSTACK_STAGE (опционально)
```

#### 3. Деплой Modal сервиса
```bash
cd /path/to/vibe_coding
modal deploy modal_services/overlay_service.py
```

После деплоя получишь URL вида:
```
✓ Created web function submit => https://user--datanauts-overlay-submit.modal.run
✓ Created web function status => https://user--datanauts-overlay-status.modal.run
✓ Created web function result => https://user--datanauts-overlay-result.modal.run
```

#### 4. Добавить URL в Railway
```bash
# В Railway добавить env var:
MODAL_OVERLAY_ENDPOINT=https://user--datanauts-overlay-submit.modal.run
```

#### 5. Проверка
```bash
# Тест Modal функции локально
modal run modal_services/overlay_service.py::process_overlay \
  --video-url "https://test-video" \
  --engine mediapipe \
  --shape circle

# Тест через API
curl -X POST https://user--datanauts-overlay-submit.modal.run \
  -H "Content-Type: application/json" \
  -d '{"video_url": "...", "container": "mov", "engine": "mediapipe", "shape": "circle"}'
```

#### Производительность:
- **С Modal GPU (A10G)**: 30-60 секунд
- **Без Modal (Railway CPU)**: 10+ минут
- **Ускорение**: 10-20x
- **Стоимость**: ~$0.06-0.12 за видео

## 🔍 Отладка

### Локальная отладка
```python
# Добавить в код для отладки
import pdb; pdb.set_trace()

# Или использовать logging
logger.debug(f"Debug info: {variable}")
```

### Логи в Railway
```bash
# Просмотр логов в Railway dashboard
# Или через CLI
railway logs
```

### Проверка webhook
```bash
# Проверить статус webhook
curl -X GET "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

## 📈 Мониторинг

### Health check
```python
# В main.py уже есть endpoint /health
# Проверить: https://your-app.railway.app/health
```

### Метрики
```python
# Добавить метрики в код
logger.info(f"[METRICS] User {user_id} completed action in {duration}ms")
```

## 🐛 Решение проблем

### Частые проблемы

#### 1. Ошибка импорта
```python
# Проблема: ModuleNotFoundError
# Решение: Проверить структуру импортов
from tg_bot.utils.logger import setup_logger  # Правильно
from utils.logger import setup_logger         # Неправильно
```

#### 2. Ошибка базы данных
```python
# Проблема: Database connection error
# Решение: Проверить DATABASE_URL
# Для SQLite: sqlite:///./genai.db
# Для PostgreSQL: postgresql://user:pass@host:port/db
```

#### 3. Ошибка webhook
```python
# Проблема: Webhook not set
# Решение: Проверить WEBHOOK_URL и TELEGRAM_BOT_TOKEN
```

#### 4. Ошибка R2
```python
# Проблема: R2 upload failed
# Решение: Проверить R2 credentials и bucket permissions
```

### Отладка handlers
```python
# Добавить try-catch в handlers
@dp.callback_query(F.data == "test")
async def test_handler(c: CallbackQuery):
    try:
        # Логика handler
        pass
    except Exception as e:
        logger.error(f"Handler error: {e}")
        await c.message.answer("Произошла ошибка. Попробуйте позже.")
```

## 📚 Полезные ресурсы

### Документация
- [aiogram 3.x](https://docs.aiogram.dev/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [ElevenLabs API](https://docs.elevenlabs.io/)
- [fal.ai API](https://fal.ai/docs)
- [Cloudflare R2](https://developers.cloudflare.com/r2/)

### Инструменты
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Railway](https://railway.app/)
- [PostgreSQL](https://www.postgresql.org/)

## 🤝 Участие в разработке

### Git workflow
```bash
# 1. Создать feature branch
git checkout -b feature/new-feature

# 2. Внести изменения
git add .
git commit -m "Add new feature"

# 3. Push в репозиторий
git push origin feature/new-feature

# 4. Создать Pull Request
# 5. Code review
# 6. Merge в main
```

### Code style
```python
# Использовать type hints
def function(param: str) -> Optional[str]:
    pass

# Добавлять docstrings
def function(param: str) -> Optional[str]:
    """Описание функции.
    
    Args:
        param: Описание параметра
        
    Returns:
        Описание возвращаемого значения
    """
    pass

# Использовать logger вместо print
logger.info("Message")  # Правильно
print("Message")        # Неправильно
```

### Коммиты
```bash
# Формат коммитов
feat: add new feature
fix: fix bug in handler
docs: update documentation
refactor: improve code structure
test: add unit tests
```

---

**Версия руководства**: 2.1  
**Статус**: Актуально  
**Последнее обновление**: Октябрь 2025

## 📝 Новое в v2.1

- 🚀 **Modal GPU интеграция** - ускорение видеомонтажа в 10-20 раз
- 📊 **Детальное логирование** - префиксы [MONTAGE], [AUTOPIPELINE], [OVERLAY], [MODAL]
- 🎬 **video_editing_service.py** - видеомонтаж с Shotstack
- ⚙️ **Гибридная архитектура** - Modal GPU + Railway CPU с автоматическим fallback
- ⏱️ **timing.py утилита** - контекст-менеджер для измерения времени
