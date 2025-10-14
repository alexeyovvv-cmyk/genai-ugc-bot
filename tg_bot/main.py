# main.py — точка входа бота
import asyncio, os, pathlib
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from tg_bot.db import engine
from tg_bot.models import Base
from tg_bot.utils.credits import ensure_user, get_credits, spend_credits
from tg_bot.keyboards import (
    main_menu, 
    ugc_start_menu, 
    character_choice_menu, 
    back_to_main_menu,
    voice_choice_menu,
    audio_confirmation_menu,
    text_change_decision_menu,
    settings_menu,
    voice_settings_menu,
    bottom_navigation_menu,
    gender_selection_menu,
    age_selection_menu,
    character_gallery_menu,
    character_selection_menu
)
from tg_bot.states import UGCCreation
from tg_bot.services.falai_service import generate_talking_head_video
# from tg_bot.services.lipsync_service import generate_lipsync_video  # Заменено на falai_service
# from tg_bot.services.vertex_service import generate_video_veo3  # Временно отключено
from tg_bot.services.elevenlabs_service import tts_to_file
from tg_bot.services.prompt_enhancer_service import enhance_video_prompt
from tg_bot.utils.files import (
    list_start_frames, 
    list_character_images, 
    get_character_image,
    get_available_genders,
    get_available_ages
)
from tg_bot.utils.voices import list_voice_samples
from tg_bot.utils.audio import check_audio_duration_limit
from tg_bot.utils.user_state import (
    set_selected_character,
    get_selected_character,
    set_character_text,
    get_character_text,
    set_situation_prompt,
    get_situation_prompt,
    set_selected_voice,
    get_selected_voice,
    set_last_audio,
    get_last_audio,
)

# Функции для сохранения параметров персонажа
def set_character_gender(user_id: int, gender: str):
    """Сохранить выбранный пол персонажа"""
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE user_state 
            SET character_gender = :gender 
            WHERE tg_id = :user_id
        """), {"gender": gender, "user_id": user_id})
        conn.commit()

def get_character_gender(user_id: int) -> str:
    """Получить выбранный пол персонажа"""
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT character_gender FROM user_state 
            WHERE tg_id = :user_id
        """), {"user_id": user_id}).fetchone()
        return result[0] if result and result[0] else None

def set_character_age(user_id: int, age: str):
    """Сохранить выбранный возраст персонажа"""
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE user_state 
            SET character_age = :age 
            WHERE tg_id = :user_id
        """), {"age": age, "user_id": user_id})
        conn.commit()

def get_character_age(user_id: int) -> str:
    """Получить выбранный возраст персонажа"""
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT character_age FROM user_state 
            WHERE tg_id = :user_id
        """), {"user_id": user_id}).fetchone()
        return result[0] if result and result[0] else None

def set_character_page(user_id: int, page: int):
    """Сохранить текущую страницу персонажей"""
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE user_state 
            SET character_page = :page 
            WHERE tg_id = :user_id
        """), {"page": page, "user_id": user_id})
        conn.commit()

def get_character_page(user_id: int) -> int:
    """Получить текущую страницу персонажей"""
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT character_page FROM user_state 
            WHERE tg_id = :user_id
        """), {"user_id": user_id}).fetchone()
        return result[0] if result and result[0] is not None else 0

load_dotenv()

# Check for required environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    print("=" * 80)
    print("❌ ERROR: TELEGRAM_BOT_TOKEN not found in environment variables!")
    print("=" * 80)
    print("")
    print("Please set the following environment variable in Railway:")
    print("")
    print("  TELEGRAM_BOT_TOKEN=your_bot_token_here")
    print("")
    print("Get your token from: https://t.me/BotFather")
    print("")
    print("See ENV_VARIABLES.md for full list of required variables.")
    print("=" * 80)
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

print(f"✅ Bot token found: {TELEGRAM_BOT_TOKEN[:10]}...")

base_dir_env = os.getenv("BASE_DIR")
if base_dir_env is None:
    print("⚠️  Warning: BASE_DIR is not set in environment. Using current directory as BASE_DIR.")
    BASE_DIR = pathlib.Path(".")
else:
    BASE_DIR = pathlib.Path(base_dir_env)
    print(f"✅ BASE_DIR: {BASE_DIR}")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Выборы пользователя и путь к последнему аудио теперь сохраняются в БД

@dp.startup()
async def on_startup():
    # создаём таблицы
    print("🔧 Creating database tables if they don't exist...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created/verified successfully")
        
        # Run migration to add new columns if they don't exist
        print("🔄 Running migrations for new columns...")
        from sqlalchemy import text
        with engine.connect() as conn:
            try:
                # Try to add new columns (will be skipped if already exist)
                migration_sql = """
                ALTER TABLE user_state 
                ADD COLUMN IF NOT EXISTS selected_character_idx INTEGER,
                ADD COLUMN IF NOT EXISTS character_text VARCHAR,
                ADD COLUMN IF NOT EXISTS situation_prompt VARCHAR,
                ADD COLUMN IF NOT EXISTS character_gender VARCHAR,
                ADD COLUMN IF NOT EXISTS character_age VARCHAR,
                ADD COLUMN IF NOT EXISTS character_page INTEGER DEFAULT 0;
                """
                conn.execute(text(migration_sql))
                conn.commit()
                print("✅ Migrations completed successfully")
            except Exception as migration_error:
                print(f"⚠️  Migration warning: {migration_error}")
                # Continue anyway - tables might already be up to date
        
        # Show table names
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"📊 Available tables: {', '.join(tables) if tables else 'none yet'}")
        
        # Show database stats
        from sqlalchemy import select
        from tg_bot.db import SessionLocal
        from tg_bot.models import User, CreditLog
        with SessionLocal() as db:
            user_count = len(db.execute(select(User)).scalars().all())
            credit_log_count = len(db.execute(select(CreditLog)).scalars().all())
            print(f"[STARTUP] 👥 Users in database: {user_count}")
            print(f"[STARTUP] 📊 Credit operations logged: {credit_log_count}")
            
            if user_count > 0:
                print(f"[STARTUP] ✅ Database has {user_count} existing users - data persisted!")
                # Show user credits
                users = db.execute(select(User)).scalars().all()
                for user in users[:5]:  # Show first 5 users
                    print(f"[STARTUP]   User {user.tg_id}: {user.credits} credits")
            else:
                print(f"[STARTUP] ⚠️  Database is empty - first start or data was lost")
                
    except Exception as e:
        print(f"❌ Error creating database tables: {e}")
        raise

@dp.message(CommandStart())
async def cmd_start(m: Message):
    ensure_user(m.from_user.id)
    await m.answer(
        "🎬 <b>Добро пожаловать в GenAI UGC Ads!</b>\n\n"
        "Создавайте профессиональные рекламные видео с помощью ИИ.\n"
        "У вас есть 100 стартовых кредитов.\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "credits")
async def show_credits(c: CallbackQuery):
    from sqlalchemy import select
    from tg_bot.db import SessionLocal
    from tg_bot.models import User, CreditLog
    
    cts = get_credits(c.from_user.id)
    
    # Получаем последние 5 операций с кредитами
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.tg_id == c.from_user.id))
        if user:
            logs = db.execute(
                select(CreditLog)
                .where(CreditLog.user_id == user.id)
                .order_by(CreditLog.created_at.desc())
                .limit(5)
            ).scalars().all()
        else:
            logs = []
    
    # Формируем сообщение с историей
    history_text = ""
    if logs:
        history_text = "\n\n📊 <b>Последние операции:</b>\n"
        for log in logs:
            sign = "+" if log.delta > 0 else ""
            emoji = "📈" if log.delta > 0 else "📉"
            reason_map = {
                "signup_bonus": "Бонус при регистрации",
                "ugc_video_creation": "Генерация UGC видео",
                "refund_ugc_fail": "Возврат (ошибка)",
                "admin_add": "Начислено администратором"
            }
            reason_text = reason_map.get(log.reason, log.reason)
            history_text += f"{emoji} {sign}{log.delta} — {reason_text}\n"
    
    await c.message.answer(
        f"💰 <b>Баланс кредитов</b>\n\n"
        f"У тебя сейчас: <b>{cts} кредитов</b>\n\n"
        f"💡 <b>Стоимость услуг:</b>\n"
        f"• Генерация UGC видео: 1 кредит"
        f"{history_text}",
        parse_mode="HTML",
        reply_markup=main_menu()
    )
    await c.answer()

# --- FAQ ---
@dp.callback_query(F.data == "faq")
async def show_faq(c: CallbackQuery):
    faq_text = """
❓ <b>Как пользоваться ботом</b>

1️⃣ <b>Создать UGC рекламу</b>
   • Выбери персонажа из готовых вариантов
   • Напиши текст, который должен сказать персонаж
   • Опиши ситуацию для видео
   • Получи готовое видео с говорящим персонажем!

2️⃣ <b>Стоимость</b>
   • Генерация видео: 1 кредит
   • При регистрации: 100 бесплатных кредитов

3️⃣ <b>Технические детали</b>
   • Видео генерируется с помощью Google Veo3
   • Персонаж "говорит" текст в видео
   • Формат видео: 9:16 (вертикальное)
   • Длительность: 6 секунд

Если возникли вопросы — пиши в поддержку!
"""
    await c.message.answer(faq_text, parse_mode="HTML", reply_markup=back_to_main_menu())
    await c.answer()

# --- UGC Creation Flow ---
@dp.callback_query(F.data == "create_ugc")
async def start_ugc_creation(c: CallbackQuery):
    await c.message.edit_text(
        "🎬 <b>Создание UGC рекламы</b>\n\n"
        "Выбери один из вариантов:",
        parse_mode="HTML",
        reply_markup=ugc_start_menu()
    )
    await c.answer()

@dp.callback_query(F.data == "create_character")
async def create_character(c: CallbackQuery):
    await c.message.answer(
        "✨ <b>Создание персонажа</b>\n\n"
        "Эта функция пока недоступна, но скоро появится! 🚀\n\n"
        "Используй пока готовых персонажей.",
        parse_mode="HTML",
        reply_markup=back_to_main_menu()
    )
    await c.answer()

@dp.callback_query(F.data == "select_character")
async def select_character(c: CallbackQuery, state: FSMContext):
    """Начать процесс выбора персонажа - сначала выбор пола"""
    await c.message.edit_text(
        "👤 <b>Выбор персонажа</b>\n\n"
        "Сначала выбери пол персонажа:",
        parse_mode="HTML",
        reply_markup=gender_selection_menu()
    )
    await state.set_state(UGCCreation.waiting_gender_selection)
    await c.answer()

# --- Новые обработчики для выбора персонажа ---

@dp.callback_query(F.data == "gender_male")
async def gender_male_selected(c: CallbackQuery, state: FSMContext):
    """Пользователь выбрал мужской пол"""
    set_character_gender(c.from_user.id, "male")
    print(f"User {c.from_user.id} выбрал пол: мужской")
    
    await c.message.edit_text(
        "👨 <b>Мужской пол выбран</b>\n\n"
        "Теперь выбери возраст персонажа:",
        parse_mode="HTML",
        reply_markup=age_selection_menu()
    )
    await state.set_state(UGCCreation.waiting_age_selection)
    await c.answer()

@dp.callback_query(F.data == "gender_female")
async def gender_female_selected(c: CallbackQuery, state: FSMContext):
    """Пользователь выбрал женский пол"""
    set_character_gender(c.from_user.id, "female")
    print(f"User {c.from_user.id} выбрал пол: женский")
    
    await c.message.edit_text(
        "👩 <b>Женский пол выбран</b>\n\n"
        "Теперь выбери возраст персонажа:",
        parse_mode="HTML",
        reply_markup=age_selection_menu()
    )
    await state.set_state(UGCCreation.waiting_age_selection)
    await c.answer()

@dp.callback_query(F.data == "age_young")
async def age_young_selected(c: CallbackQuery, state: FSMContext):
    """Пользователь выбрал молодой возраст"""
    set_character_age(c.from_user.id, "young")
    set_character_page(c.from_user.id, 0)  # Сбрасываем страницу
    print(f"User {c.from_user.id} выбрал возраст: молодой")
    
    await show_character_gallery(c, state)

@dp.callback_query(F.data == "age_adult")
async def age_adult_selected(c: CallbackQuery, state: FSMContext):
    """Пользователь выбрал взрослый возраст"""
    set_character_age(c.from_user.id, "adult")
    set_character_page(c.from_user.id, 0)  # Сбрасываем страницу
    print(f"User {c.from_user.id} выбрал возраст: взрослый")
    
    await show_character_gallery(c, state)

@dp.callback_query(F.data == "age_elderly")
async def age_elderly_selected(c: CallbackQuery, state: FSMContext):
    """Пользователь выбрал пожилой возраст"""
    set_character_age(c.from_user.id, "elderly")
    set_character_page(c.from_user.id, 0)  # Сбрасываем страницу
    print(f"User {c.from_user.id} выбрал возраст: пожилой")
    
    await show_character_gallery(c, state)

async def show_character_gallery(c: CallbackQuery, state: FSMContext):
    """Показать галерею персонажей"""
    gender = get_character_gender(c.from_user.id)
    age = get_character_age(c.from_user.id)
    page = get_character_page(c.from_user.id)
    
    if not gender or not age:
        await c.message.answer(
            "❌ Ошибка: не выбраны параметры персонажа. Начните сначала.",
            reply_markup=back_to_main_menu()
        )
        return await c.answer()
    
    # Получаем изображения для текущей страницы
    images, has_next = list_character_images(gender, age, page, limit=5)
    
    if not images:
        await c.message.edit_text(
            f"❌ <b>Нет доступных персонажей</b>\n\n"
            f"Для выбранных параметров (пол: {gender}, возраст: {age}) "
            f"персонажи не найдены.\n\n"
            f"Попробуйте изменить параметры:",
            parse_mode="HTML",
            reply_markup=character_gallery_menu(page, has_next, len(images))
        )
        return await c.answer()
    
    # Отправляем изображения персонажей
    for idx, image_path in enumerate(images):
        global_index = page * 5 + idx
        await c.message.answer_photo(
            FSInputFile(image_path),
            caption=f"👤 Персонаж #{global_index+1}"
        )
    
    # Отправляем меню с навигацией
    await c.message.answer(
        f"👤 <b>Персонажи ({gender}, {age})</b>\n\n"
        f"Страница {page + 1}. Выбери персонажа:",
        parse_mode="HTML",
        reply_markup=character_gallery_menu(page, has_next, len(images))
    )
    
    await state.set_state(UGCCreation.waiting_character_gallery)
    await c.answer()

@dp.callback_query(F.data.startswith("char_page:"))
async def character_page_changed(c: CallbackQuery, state: FSMContext):
    """Пользователь переключил страницу персонажей"""
    page = int(c.data.split(":", 1)[1])
    set_character_page(c.from_user.id, page)
    print(f"User {c.from_user.id} переключил на страницу {page}")
    
    await show_character_gallery(c, state)

@dp.callback_query(F.data == "change_character_params")
async def change_character_params(c: CallbackQuery, state: FSMContext):
    """Пользователь хочет изменить параметры персонажа"""
    await c.message.edit_text(
        "🔄 <b>Изменение параметров персонажа</b>\n\n"
        "Выбери пол персонажа:",
        parse_mode="HTML",
        reply_markup=gender_selection_menu()
    )
    await state.set_state(UGCCreation.waiting_gender_selection)
    await c.answer()

@dp.callback_query(F.data == "back_to_gender")
async def back_to_gender(c: CallbackQuery, state: FSMContext):
    """Возврат к выбору пола"""
    await c.message.edit_text(
        "👤 <b>Выбор персонажа</b>\n\n"
        "Выбери пол персонажа:",
        parse_mode="HTML",
        reply_markup=gender_selection_menu()
    )
    await state.set_state(UGCCreation.waiting_gender_selection)
    await c.answer()

@dp.callback_query(F.data == "back_to_age")
async def back_to_age(c: CallbackQuery, state: FSMContext):
    """Возврат к выбору возраста"""
    gender = get_character_gender(c.from_user.id)
    gender_text = "👨 Мужской" if gender == "male" else "👩 Женский"
    
    await c.message.edit_text(
        f"👤 <b>Выбор персонажа</b>\n\n"
        f"Пол: {gender_text}\n"
        f"Выбери возраст персонажа:",
        parse_mode="HTML",
        reply_markup=age_selection_menu()
    )
    await state.set_state(UGCCreation.waiting_age_selection)
    await c.answer()

@dp.callback_query(F.data.startswith("char_pick:"))
async def character_picked(c: CallbackQuery, state: FSMContext):
    """Пользователь выбрал конкретного персонажа"""
    idx = int(c.data.split(":", 1)[1])
    gender = get_character_gender(c.from_user.id)
    age = get_character_age(c.from_user.id)
    
    # Получаем изображение персонажа
    character_image = get_character_image(gender, age, idx)
    
    if not character_image:
        await c.message.answer("❌ Персонаж не найден. Попробуйте выбрать другого.")
        return await c.answer()
    
    # Сохраняем выбор персонажа (используем глобальный индекс)
    set_selected_character(c.from_user.id, idx)
    print(f"User {c.from_user.id} выбрал персонажа #{idx+1} ({gender}, {age})")
    
    # Переходим к выбору голоса
    voices = list_voice_samples()
    
    if not voices:
        await c.message.answer(
            "❌ Нет доступных голосов. Свяжитесь с администратором.",
            reply_markup=back_to_main_menu()
        )
        return await c.answer()
    
    # Отправляем сэмплы голосов
    for idx_voice, (name, voice_id, sample_path) in enumerate(voices):
        await c.message.answer_audio(
            FSInputFile(sample_path),
            caption=f"🎤 Голос #{idx_voice+1}: {name}"
        )
    
    await c.message.answer(
        f"✅ Отлично! Ты выбрал персонажа #{idx+1}\n\n"
        "🎤 Теперь выбери голос для озвучки:",
        reply_markup=voice_choice_menu(len(voices))
    )
    
    await state.set_state(UGCCreation.waiting_voice_selection)
    await c.answer()

@dp.callback_query(F.data.startswith("voice_pick:"))
async def voice_picked(c: CallbackQuery, state: FSMContext):
    idx = int(c.data.split(":", 1)[1])
    voices = list_voice_samples()
    
    if idx < 0 or idx >= len(voices):
        await c.message.answer("❌ Некорректный выбор голоса.")
        return await c.answer()
    
    # Сохраняем выбор голоса
    name, voice_id, sample_path = voices[idx]
    set_selected_voice(c.from_user.id, voice_id)
    print(f"User {c.from_user.id} выбрал голос: {name} ({voice_id})")
    
    # Переходим к запросу текста
    await c.message.answer(
        f"✅ Отлично! Выбран голос: {name}\n\n"
        "📝 Теперь напиши текст, который должен сказать персонаж.\n\n"
        "⚠️ <b>Важно:</b> Текст должен быть таким, чтобы озвучка заняла не более 15 секунд!\n\n"
        "Например: 'Привет! Попробуй наш новый продукт со скидкой 20%!'",
        parse_mode="HTML",
        reply_markup=back_to_main_menu()
    )
    
    await state.set_state(UGCCreation.waiting_character_text)
    await c.answer()

@dp.callback_query(F.data == "audio_confirmed")
async def audio_confirmed(c: CallbackQuery, state: FSMContext):
    """Пользователь подтвердил аудио, переходим к запросу промпта для видео"""
    await c.message.answer(
        "🎬 Отлично! Теперь опиши ситуацию для видео.\n\n"
        "Например: 'яркий солнечный день, улыбается и машет рукой'\n\n"
        "Это описание поможет сделать видео более живым.",
        reply_markup=back_to_main_menu()
    )
    await state.set_state(UGCCreation.waiting_situation_prompt)
    await c.answer()

@dp.callback_query(F.data == "audio_redo")
async def audio_redo(c: CallbackQuery, state: FSMContext):
    """Пользователь хочет переделать аудио"""
    await c.message.answer(
        "🔄 Хочешь изменить текст или просто перегенерировать аудио с тем же текстом?",
        reply_markup=text_change_decision_menu()
    )
    await state.set_state(UGCCreation.waiting_text_change_decision)
    await c.answer()

@dp.callback_query(F.data == "change_text_yes")
async def change_text_yes(c: CallbackQuery, state: FSMContext):
    """Пользователь хочет изменить текст"""
    await c.message.answer(
        "✏️ Отлично! Напиши новый текст для персонажа.\n\n"
        "⚠️ <b>Важно:</b> Текст должен быть таким, чтобы озвучка заняла не более 15 секунд!",
        parse_mode="HTML",
        reply_markup=back_to_main_menu()
    )
    await state.set_state(UGCCreation.waiting_new_character_text)
    await c.answer()

@dp.callback_query(F.data == "change_text_no")
async def change_text_no(c: CallbackQuery, state: FSMContext):
    """Пользователь хочет перегенерировать с тем же текстом"""
    # Получаем сохраненный текст
    character_text = get_character_text(c.from_user.id)
    
    if not character_text:
        await c.message.answer(
            "❌ Не найден предыдущий текст. Попробуй начать сначала.",
            reply_markup=main_menu()
        )
        await state.clear()
        return await c.answer()
    
    voice_id = get_selected_voice(c.from_user.id)
    
    if not voice_id:
        await c.message.answer(
            "❌ Голос не выбран. Попробуй начать сначала.",
            reply_markup=main_menu()
        )
        await state.clear()
        return await c.answer()
    
    try:
        await c.message.answer("🎤 Перегенерирую озвучку с тем же текстом...")
        print(f"[UGC] Перегенерация TTS для пользователя {c.from_user.id}, voice_id={voice_id}")
        
        # Удаляем старое аудио если есть
        old_audio_path = get_last_audio(c.from_user.id)
        if old_audio_path and os.path.exists(old_audio_path):
            try:
                os.remove(old_audio_path)
            except:
                pass
        
        audio_path = await tts_to_file(character_text, voice_id)
        
        if not audio_path:
            raise Exception("Не удалось сгенерировать аудио")
        
        print(f"[UGC] Аудио перегенерировано: {audio_path}")
        
        # Сохраняем путь к новому аудио
        set_last_audio(c.from_user.id, audio_path)
        
        # Проверяем длительность
        is_valid, duration = check_audio_duration_limit(audio_path, max_seconds=15.0)
        
        print(f"[UGC] Длительность аудио: {duration:.2f} сек, валидно: {is_valid}")
        
        if not is_valid:
            await c.message.answer(
                f"❌ <b>Аудио слишком длинное!</b>\n\n"
                f"Длительность твоей озвучки: <b>{duration:.1f} секунд</b>\n"
                f"Максимум: <b>15 секунд</b>\n\n"
                f"Пожалуйста, сократи текст и попробуй снова.",
                parse_mode="HTML",
                reply_markup=back_to_main_menu()
            )
            # Очистка аудио
            try:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            except:
                pass
            await state.clear()
            return await c.answer()
        
        # Отправляем новое аудио
        await c.message.answer_audio(
            FSInputFile(audio_path),
            caption=f"🎤 Новая версия озвучки ({duration:.1f} сек)"
        )
        
        # Снова даем возможность подтвердить или переделать
        await c.message.answer(
            "✅ Озвучка готова! Что будем делать?",
            reply_markup=audio_confirmation_menu()
        )
        
        await state.set_state(UGCCreation.waiting_audio_confirmation)
        
    except Exception as e:
        print(f"[UGC] Ошибка при перегенерации аудио: {e}")
        import traceback
        traceback.print_exc()
        
        await c.message.answer(
            f"❌ Ошибка при перегенерации озвучки: {str(e)}\n\n"
            "Попробуй еще раз или свяжись с поддержкой.",
            reply_markup=main_menu()
        )
        await state.clear()
    
    await c.answer()

@dp.callback_query(F.data == "change_voice")
async def change_voice(c: CallbackQuery, state: FSMContext):
    """Пользователь хочет выбрать другой голос"""
    # Получаем сохраненный текст персонажа
    character_text = get_character_text(c.from_user.id)
    
    if not character_text:
        await c.message.answer(
            "❌ Не найден текст персонажа. Попробуй начать сначала.",
            reply_markup=main_menu()
        )
        await state.clear()
        return await c.answer()
    
    # Получаем доступные голоса
    voices = list_voice_samples()
    
    if not voices:
        await c.message.answer(
            "❌ Нет доступных голосов. Свяжитесь с администратором.",
            reply_markup=back_to_main_menu()
        )
        return await c.answer()
    
    # Отправляем сэмплы голосов
    for idx_voice, (name, voice_id, sample_path) in enumerate(voices):
        await c.message.answer_audio(
            FSInputFile(sample_path),
            caption=f"🎤 Голос #{idx_voice+1}: {name}"
        )
    
    await c.message.answer(
        f"🎤 <b>Выбор голоса</b>\n\n"
        f"Текст: <i>\"{character_text[:50]}{'...' if len(character_text) > 50 else ''}\"</i>\n\n"
        f"Выбери новый голос для озвучки:",
        parse_mode="HTML",
        reply_markup=voice_choice_menu(len(voices))
    )
    
    await state.set_state(UGCCreation.waiting_voice_selection)
    await c.answer()

@dp.message(UGCCreation.waiting_new_character_text)
async def new_character_text_received(m: Message, state: FSMContext):
    """Получен новый текст для переделки аудио"""
    # Сохраняем новый текст
    set_character_text(m.from_user.id, m.text)
    print(f"User {m.from_user.id} ввел новый текст персонажа: {m.text[:50]}...")
    
    # Получаем выбранный голос
    voice_id = get_selected_voice(m.from_user.id)
    
    if not voice_id:
        await m.answer(
            "❌ Голос не выбран. Попробуй начать сначала.",
            reply_markup=main_menu()
        )
        await state.clear()
        return
    
    try:
        await m.answer("🎤 Генерирую новую озвучку...")
        print(f"[UGC] Генерация нового TTS для пользователя {m.from_user.id}, voice_id={voice_id}")
        
        # Удаляем старое аудио если есть
        old_audio_path = get_last_audio(m.from_user.id)
        if old_audio_path and os.path.exists(old_audio_path):
            try:
                os.remove(old_audio_path)
            except:
                pass
        
        audio_path = await tts_to_file(m.text, voice_id)
        
        if not audio_path:
            raise Exception("Не удалось сгенерировать аудио")
        
        print(f"[UGC] Новое аудио сгенерировано: {audio_path}")
        
        # Сохраняем путь к аудио
        set_last_audio(m.from_user.id, audio_path)
        
        # Проверяем длительность
        is_valid, duration = check_audio_duration_limit(audio_path, max_seconds=15.0)
        
        print(f"[UGC] Длительность аудио: {duration:.2f} сек, валидно: {is_valid}")
        
        if not is_valid:
            await m.answer(
                f"❌ <b>Аудио слишком длинное!</b>\n\n"
                f"Длительность твоей озвучки: <b>{duration:.1f} секунд</b>\n"
                f"Максимум: <b>15 секунд</b>\n\n"
                f"Пожалуйста, сократи текст и попробуй снова.",
                parse_mode="HTML",
                reply_markup=back_to_main_menu()
            )
            # Очистка аудио
            try:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            except:
                pass
            return
        
        # Отправляем сгенерированное аудио для прослушивания
        await m.answer_audio(
            FSInputFile(audio_path),
            caption=f"🎤 Вот как это будет звучать ({duration:.1f} сек)"
        )
        
        # Даем возможность подтвердить или переделать аудио
        await m.answer(
            "✅ Озвучка готова! Что будем делать?",
            reply_markup=audio_confirmation_menu()
        )
        
        await state.set_state(UGCCreation.waiting_audio_confirmation)
        
    except Exception as e:
        print(f"[UGC] Ошибка при генерации нового аудио: {e}")
        import traceback
        traceback.print_exc()
        
        await m.answer(
            f"❌ Ошибка при генерации озвучки: {str(e)}\n\n"
            "Попробуй еще раз или свяжись с поддержкой.",
            reply_markup=main_menu()
        )
        await state.clear()

@dp.message(UGCCreation.waiting_character_text)
async def character_text_received(m: Message, state: FSMContext):
    # Сохраняем текст
    set_character_text(m.from_user.id, m.text)
    print(f"User {m.from_user.id} ввел текст персонажа: {m.text[:50]}...")
    
    # Получаем выбранный голос
    voice_id = get_selected_voice(m.from_user.id)
    
    if not voice_id:
        await m.answer(
            "❌ Голос не выбран. Попробуй начать сначала.",
            reply_markup=main_menu()
        )
        await state.clear()
        return
    
    try:
        # Генерируем аудио напрямую из текста пользователя
        await m.answer("🎤 Генерирую озвучку...")
        print(f"[UGC] Генерация TTS для пользователя {m.from_user.id}, voice_id={voice_id}")
        
        audio_path = await tts_to_file(m.text, voice_id)
        
        if not audio_path:
            raise Exception("Не удалось сгенерировать аудио")
        
        print(f"[UGC] Аудио сгенерировано: {audio_path}")
        
        # Сохраняем путь к аудио
        set_last_audio(m.from_user.id, audio_path)
        
        # Проверяем длительность
        is_valid, duration = check_audio_duration_limit(audio_path, max_seconds=15.0)
        
        print(f"[UGC] Длительность аудио: {duration:.2f} сек, валидно: {is_valid}")
        
        if not is_valid:
            await m.answer(
                f"❌ <b>Аудио слишком длинное!</b>\n\n"
                f"Длительность твоей озвучки: <b>{duration:.1f} секунд</b>\n"
                f"Максимум: <b>15 секунд</b>\n\n"
                f"Пожалуйста, сократи текст и попробуй снова.",
                parse_mode="HTML",
                reply_markup=back_to_main_menu()
            )
            # Очистка аудио
            try:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            except:
                pass
            return
        
        # Отправляем сгенерированное аудио для прослушивания
        await m.answer_audio(
            FSInputFile(audio_path),
            caption=f"🎤 Вот как это будет звучать ({duration:.1f} сек)"
        )
        
        # Даем возможность подтвердить или переделать аудио
        await m.answer(
            "✅ Озвучка готова! Что будем делать?",
            reply_markup=audio_confirmation_menu()
        )
        
        await state.set_state(UGCCreation.waiting_audio_confirmation)
        
    except Exception as e:
        print(f"[UGC] Ошибка при генерации аудио: {e}")
        import traceback
        traceback.print_exc()
        
        await m.answer(
            f"❌ Ошибка при генерации озвучки: {str(e)}\n\n"
            "Попробуй еще раз или свяжись с поддержкой.",
            reply_markup=main_menu()
        )
        await state.clear()

@dp.message(UGCCreation.waiting_situation_prompt)
async def situation_prompt_received(m: Message, state: FSMContext):
    import sys
    
    def log(msg):
        """Логирование с принудительным flush"""
        print(msg, flush=True)
        sys.stdout.flush()
    
    log(f"[UGC] User {m.from_user.id} начал создание UGC рекламы")
    
    # Улучшаем промпт для видео: переводим и добавляем детали
    await m.answer("✨ Улучшаю описание ситуации для видео...")
    log(f"[UGC] Улучшение видео промпта для пользователя {m.from_user.id}")
    
    enhanced_prompt = await enhance_video_prompt(m.text)
    
    # Показываем пользователю улучшенный промпт
    if enhanced_prompt != m.text:
        await m.answer(
            f"✅ <b>Описание улучшено!</b>\n\n"
            f"<b>Ваше описание:</b>\n{m.text}\n\n"
            f"<b>Улучшенное:</b>\n{enhanced_prompt}",
            parse_mode="HTML"
        )
    
    # Сохраняем УЛУЧШЕННЫЙ промпт
    set_situation_prompt(m.from_user.id, enhanced_prompt)
    log(f"[UGC] Улучшенный промпт сохранен: {enhanced_prompt[:50]}...")
    
    # Списываем кредит
    ok = spend_credits(m.from_user.id, 1, "ugc_video_creation")
    if not ok:
        log(f"[UGC] Недостаточно кредитов у user {m.from_user.id}")
        await m.answer(
            "❌ Недостаточно кредитов (нужен 1 кредит).\n\n"
            "Свяжись с администратором для пополнения.",
            reply_markup=main_menu()
        )
        await state.clear()
        return
    
    log(f"[UGC] Кредит списан успешно")
    
    try:
        await m.answer("⏳ Начинаю создание UGC рекламы...\n\nЭто займет несколько минут.")
        log(f"[UGC] Стартовое сообщение отправлено")
        
        # Получаем сохраненные данные
        log(f"[UGC] Получаем сохраненные данные...")
        character_idx = get_selected_character(m.from_user.id)
        character_text = get_character_text(m.from_user.id)
        situation_prompt = get_situation_prompt(m.from_user.id)
        audio_path = get_last_audio(m.from_user.id)
        
        # Получаем параметры персонажа
        gender = get_character_gender(m.from_user.id)
        age = get_character_age(m.from_user.id)
        
        log(f"[UGC] Данные получены: character_idx={character_idx}, gender={gender}, age={age}")
        log(f"[UGC] Текст: {character_text[:30] if character_text else 'None'}...")
        log(f"[UGC] Аудио: {audio_path}")
        
        # Получаем изображение персонажа из новой системы
        if gender and age and character_idx is not None:
            selected_frame = get_character_image(gender, age, character_idx)
            log(f"[UGC] Используем новую систему персонажей: {gender}/{age}, индекс {character_idx}")
        else:
            # Fallback к старой системе для обратной совместимости
            frames = list_start_frames()[:5]
            selected_frame = frames[character_idx] if character_idx is not None and character_idx < len(frames) else None
            log(f"[UGC] Используем старую систему персонажей, найдено {len(frames)} кадров")
        
        if not selected_frame:
            log(f"[UGC] ❌ Кадр не найден!")
            if gender and age:
                raise Exception(f"Не удалось найти персонажа с параметрами: пол={gender}, возраст={age}, индекс={character_idx}")
            else:
                raise Exception("Не удалось найти выбранный кадр")
        
        if not audio_path or not os.path.exists(audio_path):
            log(f"[UGC] ❌ Аудио не найдено!")
            raise Exception("Не удалось найти аудио файл")
        
        log(f"[UGC] Выбран кадр: {selected_frame}")
        
        # Генерируем видео с помощью fal.ai OmniHuman
        # Передаем стартовый кадр персонажа и аудио
        await m.answer("🎬 Создаю видео с синхронизацией губ... (это может занять 2-3 минуты)")
        log(f"[UGC] Начинаем генерацию talking head видео через fal.ai...")
        log(f"[UGC] Стартовый кадр: {selected_frame}")
        log(f"[UGC] Аудио файл: {audio_path}")
        
        try:
            video_path = await generate_talking_head_video(
                audio_path=audio_path,
                image_path=selected_frame
            )
            log(f"[UGC] Видео сгенерировано: {video_path}")
        except Exception as video_error:
            log(f"[UGC] ❌ Ошибка при генерации видео: {video_error}")
            import traceback
            traceback.print_exc()
            raise Exception(f"Ошибка генерации видео: {str(video_error)}")
        
        if video_path:
            await m.answer("✅ Отправляю готовое видео...")
            log(f"[UGC] Отправляем видео пользователю...")
            
            await m.answer_video(
                FSInputFile(video_path), 
                caption="🎉 Твоя UGC реклама готова!\n\n(-1 кредит списан)"
            )
            log(f"[UGC] ✅ Видео отправлено успешно")
            
            # Очистка временных файлов
            try:
                if os.path.exists(video_path):
                    os.remove(video_path)
                log(f"[UGC] Видео файл очищен: {video_path}")
            except Exception as cleanup_error:
                log(f"[UGC] ⚠️ Не удалось очистить видео файл: {cleanup_error}")
            
            # Очистка аудио файла
            try:
                if audio_path and os.path.exists(audio_path):
                    os.remove(audio_path)
                    log(f"[UGC] Аудио файл очищен: {audio_path}")
            except Exception as cleanup_error:
                log(f"[UGC] ⚠️ Не удалось очистить аудио файл: {cleanup_error}")
        else:
            log(f"[UGC] ❌ Генерация вернула None")
            raise Exception("Не удалось сгенерировать видео. Попробуйте позже.")
            
        await m.answer(
            "Хочешь создать еще одну рекламу?",
            reply_markup=main_menu()
        )
        log(f"[UGC] ✅ UGC реклама завершена успешно для user {m.from_user.id}")
        
    except Exception as e:
        # Возвращаем кредит при ошибке
        log(f"[UGC] ❌ ОШИБКА для user {m.from_user.id}: {str(e)}")
        import traceback
        log(f"[UGC] Traceback:\n{traceback.format_exc()}")
        
        from tg_bot.utils.credits import add_credits
        add_credits(m.from_user.id, 1, "refund_ugc_fail")
        log(f"[UGC] Кредит возвращен")
        
        error_msg = str(e)
        await m.answer(
            f"❌ Что-то пошло не так при создании рекламы.\n\n"
            f"Ошибка: {error_msg[:100]}\n\n"
            f"Кредит возвращен. Попробуй позже или свяжись с поддержкой.",
            reply_markup=main_menu()
        )
    finally:
        await state.clear()
        log(f"[UGC] Состояние очищено для user {m.from_user.id}")

# --- Settings Menu ---
@dp.callback_query(F.data == "settings")
async def show_settings(c: CallbackQuery):
    await c.message.edit_text(
        "⚙️ <b>Настройки</b>\n\n"
        "Выберите раздел для настройки:",
        parse_mode="HTML",
        reply_markup=settings_menu()
    )
    await c.answer()

@dp.callback_query(F.data == "voice_settings")
async def show_voice_settings(c: CallbackQuery):
    await c.message.edit_text(
        "🎤 <b>Настройки голосов</b>\n\n"
        "Управление голосами для озвучки:",
        parse_mode="HTML",
        reply_markup=voice_settings_menu()
    )
    await c.answer()

@dp.callback_query(F.data == "listen_voices")
async def listen_voices(c: CallbackQuery):
    """Показать доступные голоса для прослушивания"""
    voices = list_voice_samples()
    
    if not voices:
        await c.message.answer(
            "❌ Нет доступных голосов. Свяжитесь с администратором.",
            reply_markup=voice_settings_menu()
        )
        return await c.answer()
    
    # Отправляем сэмплы голосов
    for idx, (name, voice_id, sample_path) in enumerate(voices):
        await c.message.answer_audio(
            FSInputFile(sample_path),
            caption=f"🎤 Голос #{idx+1}: {name}"
        )
    
    await c.message.answer(
        "🎵 Вот все доступные голоса для озвучки:",
        reply_markup=voice_settings_menu()
    )
    await c.answer()

@dp.callback_query(F.data == "stats")
async def show_stats(c: CallbackQuery):
    credits = get_credits(c.from_user.id)
    await c.message.edit_text(
        f"📊 <b>Ваша статистика</b>\n\n"
        f"💰 Кредиты: {credits}\n"
        f"🎬 Создано видео: 0\n"
        f"📅 Регистрация: недавно\n\n"
        f"Статистика обновляется в реальном времени.",
        parse_mode="HTML",
        reply_markup=settings_menu()
    )
    await c.answer()

@dp.callback_query(F.data == "about")
async def show_about(c: CallbackQuery):
    await c.message.edit_text(
        "ℹ️ <b>О боте</b>\n\n"
        "🤖 <b>GenAI UGC Ads Bot</b>\n\n"
        "Создавайте профессиональные UGC рекламные видео с помощью ИИ!\n\n"
        "✨ <b>Возможности:</b>\n"
        "• Генерация говорящих персонажей\n"
        "• Синхронизация губ с аудио\n"
        "• Различные голоса для озвучки\n"
        "• Профессиональное качество видео\n\n"
        "🚀 <b>Технологии:</b>\n"
        "• Google Veo3 для генерации видео\n"
        "• ElevenLabs для озвучки\n"
        "• fal.ai для синхронизации губ",
        parse_mode="HTML",
        reply_markup=settings_menu()
    )
    await c.answer()

@dp.callback_query(F.data == "support")
async def show_support(c: CallbackQuery):
    await c.message.edit_text(
        "🆘 <b>Поддержка</b>\n\n"
        "Если у вас возникли вопросы или проблемы:\n\n"
        "📧 <b>Свяжитесь с нами:</b>\n"
        "• Telegram: @your_support_username\n"
        "• Email: support@example.com\n\n"
        "⏰ <b>Время ответа:</b> до 24 часов\n\n"
        "🔧 <b>Частые проблемы:</b>\n"
        "• Видео не генерируется → проверьте кредиты\n"
        "• Плохое качество → попробуйте другой персонаж\n"
        "• Ошибки → перезапустите процесс",
        parse_mode="HTML",
        reply_markup=settings_menu()
    )
    await c.answer()

@dp.callback_query(F.data == "model_settings")
async def show_model_settings(c: CallbackQuery):
    await c.message.edit_text(
        "⚙️ <b>Настройки модели</b>\n\n"
        "🔧 <b>Текущие настройки:</b>\n"
        "• Модель видео: Google Veo3\n"
        "• Качество: Высокое\n"
        "• Формат: 9:16 (вертикальное)\n"
        "• Длительность: 6 секунд\n\n"
        "⚡ <b>Производительность:</b>\n"
        "• Время генерации: 2-3 минуты\n"
        "• Размер файла: ~5-10 МБ\n\n"
        "Настройки оптимизированы для лучшего качества.",
        parse_mode="HTML",
        reply_markup=bottom_navigation_menu()
    )
    await c.answer()

@dp.callback_query(F.data == "profile")
async def show_profile(c: CallbackQuery):
    credits = get_credits(c.from_user.id)
    await c.message.edit_text(
        f"👤 <b>Ваш профиль</b>\n\n"
        f"🆔 ID: {c.from_user.id}\n"
        f"👤 Имя: {c.from_user.first_name or 'Не указано'}\n"
        f"💰 Кредиты: {credits}\n"
        f"📅 Статус: Активен\n\n"
        f"🎬 <b>Активность:</b>\n"
        f"• Создано видео: 0\n"
        f"• Последняя активность: сейчас\n\n"
        f"💡 <b>Совет:</b> Регулярно создавайте контент для лучших результатов!",
        parse_mode="HTML",
        reply_markup=bottom_navigation_menu()
    )
    await c.answer()

@dp.callback_query(F.data == "back_previous")
async def back_previous(c: CallbackQuery):
    """Возврат к предыдущему меню"""
    await c.message.edit_text(
        "🤖 Главное меню:",
        reply_markup=main_menu()
    )
    await c.answer()

# --- Navigation ---
@dp.callback_query(F.data == "back_to_main")
async def back_to_main(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text(
        "🤖 Главное меню:",
        reply_markup=main_menu()
    )
    await state.clear()
    await c.answer()

@dp.callback_query(F.data == "back_to_ugc")
async def back_to_ugc(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text(
        "🎬 <b>Создание UGC рекламы</b>\n\n"
        "Выбери один из вариантов:",
        parse_mode="HTML",
        reply_markup=ugc_start_menu()
    )
    await state.clear()
    await c.answer()

async def main():
    # Detect if running in Railway/production (has PORT env var) or locally
    port = os.getenv("PORT")
    railway_public_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    
    if port and railway_public_domain:
        # Railway/Production mode: use webhook
        from aiohttp import web
        
        # Construct webhook URL from Railway public domain
        webhook_url = f"https://{railway_public_domain}/webhook"
        print(f"Setting webhook to: {webhook_url}")
        
        try:
            await bot.set_webhook(webhook_url, drop_pending_updates=True)
            print("Webhook set successfully!")
        except Exception as e:
            print(f"Failed to set webhook: {e}")
        
        # Create aiohttp app
        app = web.Application()
        
        # Register dispatcher webhook handler
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
        
        # Add health check endpoint
        async def health(request):
            return web.Response(text="OK")
        app.router.add_get("/health", health)
        app.router.add_get("/", health)
        
        setup_application(app, dp, bot=bot)
        
        # Run web server
        port_num = int(port)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=port_num)
        print(f"Starting webhook server on port {port_num}")
        await site.start()
        
        # Keep running
        await asyncio.Event().wait()
    else:
        # Local mode: use polling
        print("Starting in polling mode (local development)")
        await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
