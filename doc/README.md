# 🎬 Datanauts.co UGC Bot

Telegram-бот для создания UGC-рекламных роликов с помощью ИИ. Позволяет пользователям выбирать персонажей, редактировать их, выбирать голоса и генерировать видео с синхронизацией губ.

## 🏗️ Архитектура проекта

### Общая структура

```
tg_bot/
├── main.py                    # Точка входа (упрощенная, ~130 строк)
├── dispatcher.py              # Общий dispatcher для всех handlers
├── startup.py                 # Логика инициализации бота
├── config.py                  # Конфигурация и переменные окружения
├── db.py                      # Настройка базы данных
├── models.py                  # SQLAlchemy модели
├── states.py                  # FSM состояния
├── keyboards.py               # Inline клавиатуры
├── admin.py                   # Админские команды
├── handlers/                  # Модули обработчиков (новая структура)
│   ├── __init__.py
│   ├── start.py              # /start, FAQ, профиль
│   ├── format_selection.py   # Выбор формата видео (новое!)
│   ├── character_selection.py # Выбор персонажа
│   ├── character_editing.py  # Редактирование персонажа
│   ├── voice_selection.py    # Выбор голоса
│   ├── generation.py         # Генерация аудио/видео
│   ├── my_generations.py     # История генераций
│   ├── feedback.py           # Обратная связь
│   ├── credits.py            # Кредиты
│   └── navigation.py         # Навигация
├── services/                  # Внешние сервисы
│   ├── elevenlabs_service.py # TTS через ElevenLabs
│   ├── falai_service.py      # Видео через fal.ai OmniHuman
│   ├── nano_banana_service.py # Редактирование через fal.ai
│   ├── r2_service.py         # Cloudflare R2 storage
│   └── scheduler_service.py  # Планировщик задач
└── utils/                     # Утилиты
    ├── logger.py             # Централизованное логирование
    ├── credits.py            # Управление кредитами
    ├── user_state.py         # Состояние пользователя
    ├── user_storage.py       # История генераций
    ├── user_activity.py      # Активность пользователей
    ├── statistics.py          # Статистика
    ├── files.py              # Работа с файлами
    ├── voices.py             # Управление голосами
    ├── audio.py              # Аудио утилиты
    ├── video.py              # Видео утилиты (новое!)
    └── constants.py          # Константы
```

## 🔧 Ключевые модули

### 1. **main.py** - Точка входа
- **Размер**: ~130 строк (было 1950)
- **Назначение**: Инициализация бота, регистрация handlers, запуск
- **Ключевые функции**:
  - Проверка переменных окружения
  - Инициализация bot/dispatcher
  - Регистрация всех handlers
  - Webhook/polling логика

### 2. **handlers/** - Модульная структура обработчиков

#### **start.py** - Начальные команды
```python
@CommandStart()
async def cmd_start(m: Message)

@dp.callback_query(F.data == "faq")
async def show_faq(c: CallbackQuery)

@dp.callback_query(F.data == "profile")
async def show_profile(c: CallbackQuery)
```

#### **character_selection.py** - Выбор персонажа
```python
@dp.callback_query(F.data == "select_character")
async def select_character(c: CallbackQuery, state: FSMContext)

@dp.callback_query(F.data == "gender_male")
async def gender_male_selected(c: CallbackQuery, state: FSMContext)
# Сразу показывает галерею без выбора возраста

@dp.callback_query(F.data.startswith("char_pick:"))
async def character_picked(c: CallbackQuery, state: FSMContext)
# Автоматически определяет возраст из выбранного персонажа
```

#### **character_editing.py** - Редактирование персонажа
```python
@dp.callback_query(F.data == "edit_character_yes")
async def edit_character_yes(c: CallbackQuery, state: FSMContext)

@dp.message(F.text, UGCCreation.waiting_edit_prompt)
async def handle_edit_prompt(m: Message, state: FSMContext)
```

#### **voice_selection.py** - Выбор голоса
```python
async def show_voice_gallery(c: CallbackQuery, state: FSMContext)

@dp.callback_query(F.data.startswith("voice_pick:"))
async def voice_picked(c: CallbackQuery, state: FSMContext)
```

#### **generation.py** - Генерация контента
```python
@dp.callback_query(F.data == "audio_confirmed")
async def audio_confirmed(c: CallbackQuery, state: FSMContext)

@dp.message(F.text, UGCCreation.waiting_character_text)
async def character_text_received(m: Message, state: FSMContext)
```

### 3. **services/** - Внешние сервисы

#### **elevenlabs_service.py** - TTS
- Синтез речи через ElevenLabs API
- Поддержка множества голосов
- Загрузка в R2 storage

#### **falai_service.py** - Видео генерация
- Talking head видео через fal.ai OmniHuman
- Синхронизация губ с аудио
- Обработка изображений персонажей

#### **nano_banana_service.py** - Редактирование
- AI-редактирование персонажей
- Изменение фона, одежды, аксессуаров
- Интеграция с fal.ai nano-banana

#### **r2_service.py** - Облачное хранилище
- Cloudflare R2 (S3-совместимое)
- Presigned URLs для временного доступа
- Lifecycle policies для автоочистки

### 4. **utils/** - Утилиты

#### **logger.py** - Централизованное логирование
```python
def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger
def get_logger(name: str) -> logging.Logger

# Предустановленные логгеры
ugc_logger = setup_logger("ugc_creation")
tts_logger = setup_logger("tts")
falai_logger = setup_logger("falai")
```

#### **user_state.py** - Управление состоянием
```python
# Character selection
set_character_gender(tg_id: int, gender: str)
get_character_gender(tg_id: int) -> Optional[str]
set_character_age(tg_id: int, age: str)  # Устанавливается автоматически при выборе
get_character_age(tg_id: int) -> Optional[str]

# Pagination
set_character_page(tg_id: int, page: int)
get_character_page(tg_id: int) -> int
set_voice_page(tg_id: int, page: int)
get_voice_page(tg_id: int) -> int

# Character editing
set_original_character_path(tg_id: int, path: str)
set_edited_character_path(tg_id: int, path: str)
clear_edit_session(tg_id: int)
```

#### **credits.py** - Система кредитов
```python
ensure_user(tg_id: int)  # Создание пользователя с бонусом
get_credits(tg_id: int) -> int
add_credits(tg_id: int, amount: int, reason: str)
spend_credits(tg_id: int, amount: int, reason: str) -> bool
```

## 🔄 Пользовательский флоу

### 1. **Регистрация и начало**
```
/start → Добро пожаловать + бонус кредиты
```

### 2. **Выбор формата видео** (новое!)
```
Создать UGC (/create или кнопка) → Выбор формата:
  ├─ 👤 Говорящая голова → продолжить обычный флоу
  └─ 🎬 Персонаж с бекграундом → загрузка фонового видео (макс 15 сек) → продолжить флоу
```

**Форматы видео:**
- **Говорящая голова** - классический формат с AI-персонажем
- **Персонаж с бекграундом** - персонаж на фоне вашего видео (требует загрузки фонового видео)

### 3. **Создание UGC рекламы**
```
Выбор пола → Галерея персонажей (все возрасты вместе)
```

### 4. **Редактирование персонажа** (опционально)
```
Выбор персонажа → Редактировать? → Промпт → Результат → Использовать/Продолжить/Оригинал
```

### 5. **Выбор голоса**
```
Галерея голосов → Выбор голоса → Ввод текста
```

### 6. **Генерация**
```
TTS → Прослушивание → Подтверждение → Видео генерация → Результат
```

## 🗄️ База данных

### Модели (SQLAlchemy)

#### **User** - Пользователи
```python
class User(Base):
    id: int = Column(Integer, primary_key=True)
    tg_id: int = Column(BigInteger, unique=True, nullable=False)
    credits: int = Column(Integer, default=0)
    selected_voice_id: Optional[str] = Column(String)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
```

#### **UserState** - Состояние пользователя
```python
class UserState(Base):
    user_id: int = Column(Integer, ForeignKey("users.id"), primary_key=True)
    selected_character_idx: Optional[int] = Column(Integer)
    character_text: Optional[str] = Column(Text)
    character_gender: Optional[str] = Column(String)
    character_age: Optional[str] = Column(String)
    character_page: int = Column(Integer, default=0)
    voice_page: int = Column(Integer, default=0)
    original_character_path: Optional[str] = Column(String)
    edited_character_path: Optional[str] = Column(String)
    edit_iteration_count: int = Column(Integer, default=0)
    video_format: Optional[str] = Column(String)  # 'talking_head' или 'character_with_background'
    background_video_path: Optional[str] = Column(String)  # R2 путь к фоновому видео
```

#### **GenerationHistory** - История генераций
```python
class GenerationHistory(Base):
    id: int = Column(Integer, primary_key=True)
    user_id: int = Column(Integer, ForeignKey("users.id"))
    generation_type: str = Column(String)  # 'video', 'audio'
    r2_video_key: Optional[str] = Column(String)
    r2_audio_key: Optional[str] = Column(String)
    character_gender: Optional[str] = Column(String)
    character_age: Optional[str] = Column(String)
    text_prompt: Optional[str] = Column(Text)
    credits_spent: int = Column(Integer)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
```

## 🚀 Развертывание

### Переменные окружения
```bash
# Обязательные
TELEGRAM_BOT_TOKEN=your_bot_token
WEBHOOK_URL=https://your-domain.com/webhook

# AI сервисы
ELEVEN_API_KEY=your_elevenlabs_key
FALAI_API_TOKEN=your_falai_token

# База данных
DATABASE_URL=postgresql://user:pass@host:port/db

# R2 Storage
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=your_bucket
R2_ENDPOINT_URL=https://your-account.r2.cloudflarestorage.com

# Админка
ADMIN_FEEDBACK_CHAT_ID=your_admin_chat_id
```

### Railway развертывание
```bash
# 1. Подключить GitHub репозиторий
# 2. Настроить переменные окружения
# 3. Деплой автоматический при push
```

## 🧪 Тестирование

### Локальное тестирование
```bash
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Настроить .env файл
cp .env.example .env

# 3. Запустить бота
python -m tg_bot.main
```

### Проверка функциональности
- ✅ Регистрация пользователей
- ✅ Выбор персонажа (пол/возраст/галерея)
- ✅ Редактирование персонажа
- ✅ Выбор голоса
- ✅ TTS генерация
- ✅ Видео генерация
- ✅ История генераций
- ✅ Админские команды

## 📈 Мониторинг и логи

### Централизованное логирование
```python
from tg_bot.utils.logger import setup_logger

logger = setup_logger(__name__)
logger.info("User action completed")
logger.error("Error occurred")
logger.warning("Warning message")
```

### Логи по модулям
- `ugc_creation` - Создание UGC контента
- `tts` - TTS генерация
- `falai` - Видео генерация
- `r2` - Облачное хранилище
- `admin` - Админские команды
- `statistics` - Статистика

## 🔮 Дальнейшее развитие

### Краткосрочные задачи (1-2 недели)
1. **Улучшение UI/UX**
   - Более красивые клавиатуры
   - Прогресс-бары для генерации
   - Предпросмотр персонажей

2. **Оптимизация производительности**
   - Кэширование R2 URLs
   - Асинхронная обработка файлов
   - Оптимизация запросов к БД

3. **Расширение функциональности**
   - Больше голосов и персонажей
   - Новые стили редактирования
   - Пакетная генерация

### Среднесрочные задачи (1-2 месяца)
1. **Аналитика и метрики**
   - Dashboard для админов
   - A/B тестирование
   - Пользовательская аналитика

2. **Монетизация**
   - Подписки
   - Платные функции
   - Реферальная система

3. **Интеграции**
   - API для внешних сервисов
   - Webhook уведомления
   - Экспорт в социальные сети

### Долгосрочные задачи (3+ месяца)
1. **Масштабирование**
   - Микросервисная архитектура
   - Kubernetes развертывание
   - Горизонтальное масштабирование

2. **AI/ML улучшения**
   - Собственные модели
   - Персонализация
   - Автоматическая оптимизация

3. **Международная экспансия**
   - Мультиязычность
   - Локальные платежи
   - Региональные особенности

## 🛠️ Разработка

### Добавление нового handler
1. Создать файл в `handlers/new_feature.py`
2. Добавить импорт в `handlers/__init__.py`
3. Регистрировать декораторы с `@dp.callback_query` или `@dp.message`

### Добавление нового сервиса
1. Создать файл в `services/new_service.py`
2. Добавить в `utils/logger.py` специализированный логгер
3. Интегрировать в соответствующие handlers

### Работа с базой данных
1. Изменить модель в `models.py`
2. Создать миграцию в `startup.py`
3. Обновить утилиты в `utils/`

## 📚 Документация API

### Основные endpoints
- `/webhook` - Telegram webhook
- `/health` - Health check
- `/` - Root endpoint

### Внешние API
- **ElevenLabs** - TTS синтез
- **fal.ai** - Видео генерация и редактирование
- **Cloudflare R2** - Файловое хранилище

## 🤝 Участие в разработке

### Git workflow
1. Создать feature branch
2. Внести изменения
3. Протестировать локально
4. Создать Pull Request
5. Code review
6. Merge в main

### Code style
- PEP 8 для Python
- Type hints обязательны
- Docstrings для всех функций
- Логирование через централизованный logger

---

## 📞 Поддержка

При возникновении вопросов или проблем:
1. Проверить логи в Railway dashboard
2. Обратиться к администратору через бота
3. Создать issue в GitHub репозитории

**Версия**: 2.0 (после рефакторинга)  
**Последнее обновление**: Декабрь 2024  
**Статус**: Production Ready ✅
