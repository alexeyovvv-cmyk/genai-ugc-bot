# 📡 API Документация Datanauts.co UGC Bot

## Обзор API

Datanauts.co UGC Bot предоставляет REST API для управления ботом, мониторинга и интеграции с внешними сервисами.

## 🔗 Endpoints

### Основные endpoints

#### `GET /health`
Проверка состояния сервиса.

**Ответ:**
```
Status: 200 OK
Content-Type: text/plain

OK
```

#### `GET /`
Корневой endpoint.

**Ответ:**
```
Status: 200 OK
Content-Type: text/plain

OK
```

#### `POST /webhook`
Telegram webhook endpoint для получения обновлений.

**Заголовки:**
```
Content-Type: application/json
```

**Тело запроса:**
```json
{
  "update_id": 123456789,
  "message": {
    "message_id": 1,
    "from": {
      "id": 12345,
      "is_bot": false,
      "first_name": "User",
      "username": "user"
    },
    "chat": {
      "id": 12345,
      "first_name": "User",
      "username": "user",
      "type": "private"
    },
    "date": 1640995200,
    "text": "/start"
  }
}
```

**Ответ:**
```
Status: 200 OK
Content-Type: application/json

{"ok": true}
```

## 🗄️ База данных API

### Модели данных

#### User (Пользователь)
```python
class User(Base):
    id: int                    # Внутренний ID
    tg_id: int                # Telegram ID
    credits: int              # Количество кредитов
    selected_voice_id: str     # Выбранный голос
    created_at: datetime       # Дата создания
```

#### UserState (Состояние пользователя)
```python
class UserState(Base):
    user_id: int                          # ID пользователя
    selected_character_idx: int           # Индекс персонажа
    character_text: str                   # Текст персонажа
    character_gender: str                 # Пол персонажа
    character_age: str                    # Возраст персонажа
    character_page: int                   # Страница персонажей
    voice_page: int                       # Страница голосов
    original_character_path: str          # Путь к оригиналу
    edited_character_path: str           # Путь к отредактированному
    edit_iteration_count: int             # Количество итераций редактирования
```

#### GenerationHistory (История генераций)
```python
class GenerationHistory(Base):
    id: int                    # ID записи
    user_id: int               # ID пользователя
    generation_type: str       # Тип генерации ('video', 'audio')
    r2_video_key: str          # R2 ключ видео
    r2_audio_key: str          # R2 ключ аудио
    r2_image_key: str          # R2 ключ изображения
    character_gender: str      # Пол персонажа
    character_age: str         # Возраст персонажа
    text_prompt: str           # Текст промпта
    credits_spent: int         # Потрачено кредитов
    created_at: datetime       # Дата создания
```

## 🔧 Внутренние API

### User Management API

#### `ensure_user(tg_id: int) -> None`
Создает пользователя если не существует.

**Параметры:**
- `tg_id` (int): Telegram ID пользователя

**Возвращает:**
- `None`

**Пример:**
```python
from tg_bot.utils.credits import ensure_user

ensure_user(12345)
```

#### `get_credits(tg_id: int) -> int`
Получает количество кредитов пользователя.

**Параметры:**
- `tg_id` (int): Telegram ID пользователя

**Возвращает:**
- `int`: Количество кредитов

**Пример:**
```python
from tg_bot.utils.credits import get_credits

credits = get_credits(12345)
print(f"User has {credits} credits")
```

#### `add_credits(tg_id: int, amount: int, reason: str) -> None`
Добавляет кредиты пользователю.

**Параметры:**
- `tg_id` (int): Telegram ID пользователя
- `amount` (int): Количество кредитов
- `reason` (str): Причина начисления

**Возвращает:**
- `None`

**Пример:**
```python
from tg_bot.utils.credits import add_credits

add_credits(12345, 10, "admin_bonus")
```

#### `spend_credits(tg_id: int, amount: int, reason: str) -> bool`
Списывает кредиты с пользователя.

**Параметры:**
- `tg_id` (int): Telegram ID пользователя
- `amount` (int): Количество кредитов
- `reason` (str): Причина списания

**Возвращает:**
- `bool`: True если успешно, False если недостаточно кредитов

**Пример:**
```python
from tg_bot.utils.credits import spend_credits

success = spend_credits(12345, 1, "ugc_video_creation")
if success:
    print("Credits spent successfully")
else:
    print("Insufficient credits")
```

### User State API

#### `set_character_gender(tg_id: int, gender: str) -> None`
Устанавливает пол персонажа для пользователя.

**Параметры:**
- `tg_id` (int): Telegram ID пользователя
- `gender` (str): Пол персонажа ('male', 'female')

**Возвращает:**
- `None`

#### `get_character_gender(tg_id: int) -> Optional[str]`
Получает пол персонажа пользователя.

**Параметры:**
- `tg_id` (int): Telegram ID пользователя

**Возвращает:**
- `Optional[str]`: Пол персонажа или None

#### `set_character_age(tg_id: int, age: str) -> None`
Устанавливает возраст персонажа для пользователя.

**Параметры:**
- `tg_id` (int): Telegram ID пользователя
- `age` (str): Возраст персонажа ('young', 'elderly')

**Возвращает:**
- `None`

#### `get_character_age(tg_id: int) -> Optional[str]`
Получает возраст персонажа пользователя.

**Параметры:**
- `tg_id` (int): Telegram ID пользователя

**Возвращает:**
- `Optional[str]`: Возраст персонажа или None

#### `set_character_page(tg_id: int, page: int) -> None`
Устанавливает текущую страницу персонажей.

**Параметры:**
- `tg_id` (int): Telegram ID пользователя
- `page` (int): Номер страницы

**Возвращает:**
- `None`

#### `get_character_page(tg_id: int) -> int`
Получает текущую страницу персонажей.

**Параметры:**
- `tg_id` (int): Telegram ID пользователя

**Возвращает:**
- `int`: Номер страницы

#### `set_voice_page(tg_id: int, page: int) -> None`
Устанавливает текущую страницу голосов.

**Параметры:**
- `tg_id` (int): Telegram ID пользователя
- `page` (int): Номер страницы

**Возвращает:**
- `None`

#### `get_voice_page(tg_id: int) -> int`
Получает текущую страницу голосов.

**Параметры:**
- `tg_id` (int): Telegram ID пользователя

**Возвращает:**
- `int`: Номер страницы

### File Management API

#### `list_character_images(gender: str, age: str, page: int = 0, limit: int = 5) -> Tuple[List[str], bool]`
Получает список изображений персонажей.

**Параметры:**
- `gender` (str): Пол персонажа
- `age` (str): Возраст персонажа
- `page` (int): Номер страницы
- `limit` (int): Количество на странице

**Возвращает:**
- `Tuple[List[str], bool]`: Список путей к изображениям и флаг наличия следующей страницы

**Пример:**
```python
from tg_bot.utils.files import list_character_images

images, has_next = list_character_images("male", "young", page=0, limit=5)
print(f"Found {len(images)} images, has next: {has_next}")
```

#### `get_character_image(gender: str, age: str, index: int) -> Optional[str]`
Получает конкретное изображение персонажа.

**Параметры:**
- `gender` (str): Пол персонажа
- `age` (str): Возраст персонажа
- `index` (int): Индекс изображения

**Возвращает:**
- `Optional[str]`: Путь к изображению или None

#### `list_voice_samples(gender: str, age: str, page: int = 0, limit: int = 5) -> Tuple[List[Tuple[str, str, str]], bool]`
Получает список голосовых сэмплов.

**Параметры:**
- `gender` (str): Пол персонажа
- `age` (str): Возраст персонажа
- `page` (int): Номер страницы
- `limit` (int): Количество на странице

**Возвращает:**
- `Tuple[List[Tuple[str, str, str]], bool]`: Список кортежей (имя, voice_id, путь) и флаг наличия следующей страницы

#### `get_voice_sample(gender: str, age: str, index: int) -> Optional[Tuple[str, str, str]]`
Получает конкретный голосовой сэмпл.

**Параметры:**
- `gender` (str): Пол персонажа
- `age` (str): Возраст персонажа
- `index` (int): Индекс голоса

**Возвращает:**
- `Optional[Tuple[str, str, str]]`: Кортеж (имя, voice_id, путь) или None

### Generation API

#### `tts_to_file(text: str, voice_id: str, user_id: Optional[int] = None) -> str`
Генерирует аудио из текста.

**Параметры:**
- `text` (str): Текст для озвучки
- `voice_id` (str): ID голоса
- `user_id` (Optional[int]): ID пользователя для загрузки в R2

**Возвращает:**
- `str`: Путь к сгенерированному аудио файлу

**Пример:**
```python
from tg_bot.services.elevenlabs_service import tts_to_file

audio_path = await tts_to_file("Hello world", "voice_id_123", user_id=12345)
print(f"Audio generated: {audio_path}")
```

#### `generate_talking_head_video(audio_path: str, image_path: str, user_id: Optional[int] = None) -> Optional[dict]`
Генерирует talking head видео.

**Параметры:**
- `audio_path` (str): Путь к аудио файлу
- `image_path` (str): Путь к изображению персонажа
- `user_id` (Optional[int]): ID пользователя

**Возвращает:**
- `Optional[dict]`: Словарь с результатами генерации или None

**Структура возвращаемого словаря:**
```python
{
    "local_path": "/path/to/video.mp4",
    "video_url": "https://r2.example.com/video.mp4",
    "r2_video_key": "users/12345/video.mp4"
}
```

#### `edit_character_image(image_path: str, prompt: str) -> Optional[str]`
Редактирует изображение персонажа.

**Параметры:**
- `image_path` (str): Путь к изображению
- `prompt` (str): Промпт для редактирования

**Возвращает:**
- `Optional[str]`: Путь к отредактированному изображению или None

### Storage API

#### `upload_file(local_path: str, r2_key: str) -> bool`
Загружает файл в R2 storage.

**Параметры:**
- `local_path` (str): Локальный путь к файлу
- `r2_key` (str): Ключ в R2 storage

**Возвращает:**
- `bool`: True если успешно

#### `download_file(r2_key: str, local_path: str) -> bool`
Скачивает файл из R2 storage.

**Параметры:**
- `r2_key` (str): Ключ в R2 storage
- `local_path` (str): Локальный путь для сохранения

**Возвращает:**
- `bool`: True если успешно

#### `get_presigned_url(r2_key: str, expiry_hours: int = 1) -> Optional[str]`
Получает presigned URL для временного доступа к файлу.

**Параметры:**
- `r2_key` (str): Ключ в R2 storage
- `expiry_hours` (int): Время жизни URL в часах

**Возвращает:**
- `Optional[str]`: Presigned URL или None

#### `delete_file(r2_key: str) -> bool`
Удаляет файл из R2 storage.

**Параметры:**
- `r2_key` (str): Ключ в R2 storage

**Возвращает:**
- `bool`: True если успешно

### Statistics API

#### `track_user_activity(tg_id: int) -> None`
Отслеживает активность пользователя.

**Параметры:**
- `tg_id` (int): Telegram ID пользователя

**Возвращает:**
- `None`

#### `get_new_users_count(date: Optional[str] = None) -> int`
Получает количество новых пользователей за день.

**Параметры:**
- `date` (Optional[str]): Дата в формате YYYY-MM-DD

**Возвращает:**
- `int`: Количество новых пользователей

#### `get_active_users_count(date: Optional[str] = None) -> int`
Получает количество активных пользователей за день.

**Параметры:**
- `date` (Optional[str]): Дата в формате YYYY-MM-DD

**Возвращает:**
- `int`: Количество активных пользователей

#### `get_credits_spent(date: Optional[str] = None) -> int`
Получает количество потраченных кредитов за день.

**Параметры:**
- `date` (Optional[str]): Дата в формате YYYY-MM-DD

**Возвращает:**
- `int`: Количество потраченных кредитов

#### `generate_statistics_report(target_date: Optional[str] = None) -> str`
Генерирует отчет по статистике.

**Параметры:**
- `target_date` (Optional[str]): Дата в формате YYYY-MM-DD

**Возвращает:**
- `str`: Текстовый отчет по статистике

## 🔐 Аутентификация и авторизация

### Telegram Bot Token
Все запросы к Telegram API требуют валидный bot token.

### Admin Commands
Админские команды доступны только авторизованным администраторам.

**Список администраторов:**
```python
ADMIN_TG_IDS = {12345, 67890}  # Telegram ID администраторов
```

## 📊 Rate Limiting

### Admin Commands
Админские команды имеют rate limiting:
- Максимум 1 команда в 2 секунды
- Блокировка на 10 секунд при превышении

### User Actions
Пользовательские действия не ограничены, но логируются для мониторинга.

## 🚨 Error Handling

### Стандартные коды ошибок

#### 400 Bad Request
```json
{
  "error": "Invalid request format",
  "message": "Request body is malformed"
}
```

#### 401 Unauthorized
```json
{
  "error": "Unauthorized",
  "message": "Invalid or missing authentication"
}
```

#### 403 Forbidden
```json
{
  "error": "Forbidden",
  "message": "Insufficient permissions"
}
```

#### 404 Not Found
```json
{
  "error": "Not Found",
  "message": "Resource not found"
}
```

#### 429 Too Many Requests
```json
{
  "error": "Rate Limited",
  "message": "Too many requests, please try again later"
}
```

#### 500 Internal Server Error
```json
{
  "error": "Internal Server Error",
  "message": "An unexpected error occurred"
}
```

## 📝 Примеры использования

### Создание пользователя
```python
from tg_bot.utils.credits import ensure_user, add_credits

# Создать пользователя
ensure_user(12345)

# Добавить кредиты
add_credits(12345, 10, "welcome_bonus")
```

### Генерация контента
```python
from tg_bot.services.elevenlabs_service import tts_to_file
from tg_bot.services.falai_service import generate_talking_head_video

# Генерировать аудио
audio_path = await tts_to_file("Hello world", "voice_123", user_id=12345)

# Генерировать видео
video_result = await generate_talking_head_video(
    audio_path=audio_path,
    image_path="character.jpg",
    user_id=12345
)
```

### Работа с файлами
```python
from tg_bot.services.r2_service import upload_file, get_presigned_url

# Загрузить файл
success = upload_file("local_file.mp4", "users/12345/video.mp4")

# Получить URL для скачивания
url = get_presigned_url("users/12345/video.mp4", expiry_hours=24)
```

### Получение статистики
```python
from tg_bot.utils.statistics import generate_statistics_report

# Получить отчет за сегодня
report = generate_statistics_report()

# Получить отчет за конкретную дату
report = generate_statistics_report("2024-12-01")
```

## 🔄 Webhook Events

### Message Events
```json
{
  "update_id": 123456789,
  "message": {
    "message_id": 1,
    "from": {"id": 12345, "first_name": "User"},
    "chat": {"id": 12345, "type": "private"},
    "date": 1640995200,
    "text": "/start"
  }
}
```

### Callback Query Events
```json
{
  "update_id": 123456789,
  "callback_query": {
    "id": "callback_id",
    "from": {"id": 12345, "first_name": "User"},
    "message": {"message_id": 1, "chat": {"id": 12345}},
    "data": "button_clicked"
  }
}
```

## 📚 SDK и библиотеки

### Python SDK
```python
# Установка
pip install aiogram python-dotenv sqlalchemy elevenlabs fal-client boto3

# Использование
from tg_bot.utils.credits import get_credits
from tg_bot.services.elevenlabs_service import tts_to_file
```

### JavaScript SDK
```javascript
// Установка
npm install aiogram

// Использование
const { Bot } = require('aiogram');
const bot = new Bot('YOUR_BOT_TOKEN');
```

## 🧪 Тестирование API

### Unit тесты
```python
import pytest
from tg_bot.utils.credits import get_credits, add_credits

def test_credits_operations():
    # Тест получения кредитов
    credits = get_credits(12345)
    assert credits >= 0
    
    # Тест добавления кредитов
    add_credits(12345, 10, "test")
    new_credits = get_credits(12345)
    assert new_credits == credits + 10
```

### Integration тесты
```python
import pytest
from tg_bot.services.elevenlabs_service import tts_to_file

@pytest.mark.asyncio
async def test_tts_generation():
    audio_path = await tts_to_file("Test", "voice_123")
    assert audio_path is not None
    assert os.path.exists(audio_path)
```

---

**Версия API**: 2.0  
**Статус**: Production Ready  
**Последнее обновление**: Декабрь 2024
