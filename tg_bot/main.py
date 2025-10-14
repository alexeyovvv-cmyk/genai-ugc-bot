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
    voice_choice_menu
)
from tg_bot.states import UGCCreation
from tg_bot.services.falai_service import generate_talking_head_video
# from tg_bot.services.lipsync_service import generate_lipsync_video  # Заменено на falai_service
# from tg_bot.services.vertex_service import generate_video_veo3  # Временно отключено
from tg_bot.services.elevenlabs_service import tts_to_file
from tg_bot.services.prompt_enhancer_service import enhance_video_prompt
from tg_bot.utils.files import list_start_frames
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
                ADD COLUMN IF NOT EXISTS situation_prompt VARCHAR;
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
    except Exception as e:
        print(f"❌ Error creating database tables: {e}")
        raise

@dp.message(CommandStart())
async def cmd_start(m: Message):
    ensure_user(m.from_user.id)
    await m.answer(
        "Привет! Это GenAI UGC Ads бот.\nУ тебя 100 стартовых кредитов. Что делаем?",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "credits")
async def show_credits(c: CallbackQuery):
    cts = get_credits(c.from_user.id)
    await c.message.answer(f"У тебя сейчас {cts} кредитов.", reply_markup=main_menu())
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
async def select_character(c: CallbackQuery):
    frames = list_start_frames()[:5]
    if not frames:
        await c.message.answer(
            "❌ Пока нет доступных персонажей. Свяжитесь с администратором.",
            reply_markup=back_to_main_menu()
        )
        return await c.answer()
    
    # Отправляем фотки персонажей
    for idx, frame in enumerate(frames):
        await c.message.answer_photo(
            FSInputFile(frame),
            caption=f"👤 Персонаж #{idx+1}"
        )
    
    await c.message.answer(
        "Выбери персонажа, который будет в твоей рекламе:",
        reply_markup=character_choice_menu(len(frames))
    )
    await c.answer()

@dp.callback_query(F.data.startswith("char_pick:"))
async def character_picked(c: CallbackQuery, state: FSMContext):
    idx = int(c.data.split(":", 1)[1])
    frames = list_start_frames()[:5]
    
    if idx < 0 or idx >= len(frames):
        await c.message.answer("❌ Некорректный выбор персонажа.")
        return await c.answer()
    
    # Сохраняем выбор персонажа
    set_selected_character(c.from_user.id, idx)
    print(f"User {c.from_user.id} выбрал персонажа #{idx+1}")
    
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
        
        # Переходим к запросу описания ситуации
        await m.answer(
            "✅ Озвучка готова!\n\n"
            "🎬 Теперь опиши ситуацию для видео.\n\n"
            "Например: 'яркий солнечный день, улыбается и машет рукой'\n\n"
            "Это описание поможет сделать видео более живым.",
            reply_markup=back_to_main_menu()
        )
        
        await state.set_state(UGCCreation.waiting_situation_prompt)
        
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
        
        log(f"[UGC] Данные получены: character_idx={character_idx}, text={character_text[:30] if character_text else 'None'}...")
        log(f"[UGC] Аудио: {audio_path}")
        
        frames = list_start_frames()[:5]
        log(f"[UGC] Найдено {len(frames)} кадров")
        
        selected_frame = frames[character_idx] if character_idx is not None and character_idx < len(frames) else None
        
        if not selected_frame:
            log(f"[UGC] ❌ Кадр не найден!")
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
