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
from tg_bot.keyboards import main_menu, voices_menu, frame_choice_menu, voice_choice_menu
from tg_bot.states import HookGen, AudioGen, FrameEdit, VideoGen
from tg_bot.services.openai_service import generate_hooks
from tg_bot.services.elevenlabs_service import tts_to_file, DEFAULT_VOICES
from tg_bot.services.higgsfield_service import edit_image, create_talking_video
from tg_bot.services.vertex_service import generate_video_veo3
from tg_bot.utils.files import list_start_frames
from tg_bot.utils.user_state import (
    get_selected_frame,
    set_selected_frame,
    get_selected_voice,
    set_selected_voice,
    get_last_audio,
    set_last_audio,
)
from tg_bot.utils.voices import list_voice_samples

load_dotenv()
print("DEBUG TELEGRAM_BOT_TOKEN:", os.environ.get("TELEGRAM_BOT_TOKEN"))
base_dir_env = os.getenv("BASE_DIR")
if base_dir_env is None:
    print("Warning: BASE_DIR is not set in the environment. Using current directory as BASE_DIR.")
    BASE_DIR = pathlib.Path(".")
else:
    BASE_DIR = pathlib.Path(base_dir_env)

bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
dp = Dispatcher()

# Выборы пользователя и путь к последнему аудио теперь сохраняются в БД

@dp.startup()
async def on_startup():
    # создаём таблицы
    Base.metadata.create_all(bind=engine)

@dp.message(CommandStart())
async def cmd_start(m: Message):
    ensure_user(m.from_user.id)
    await m.answer(
        "Привет! Это GenAI UGC Ads бот.\nУ тебя 10 стартовых кредитов. Что делаем?",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "credits")
async def show_credits(c: CallbackQuery):
    cts = get_credits(c.from_user.id)
    await c.message.answer(f"У тебя сейчас {cts} кредитов.", reply_markup=main_menu())
    await c.answer()

# --- Генерация хуков ---
@dp.callback_query(F.data == "hooks")
async def ask_desc(c: CallbackQuery, state: FSMContext):
    await state.set_state(HookGen.waiting_description)
    await c.message.answer("Опиши продукт и акцию одной строкой. Пример: «Новые протеиновые батончики, -20% до пятницы».")
    await c.answer()

@dp.message(HookGen.waiting_description)
async def do_hooks(m: Message, state: FSMContext):
    await m.answer("Думаю над 3–4 хук-фразами…")
    hooks = await generate_hooks(m.text, n=4)
    txt = "Готово:\n" + "\n".join([f"{i+1}) {h}" for i,h in enumerate(hooks)])
    await m.answer(txt, reply_markup=main_menu())
    await state.clear()

# --- Выбор стартового кадра ---
@dp.callback_query(F.data == "pick_frame")
async def pick_frame(c: CallbackQuery):
    frames = list_start_frames()[:5]
    if not frames:
        await c.message.answer("Пока нет стартовых кадров. Свяжитесь с администратором.")
        return await c.answer()
    for idx, frame in enumerate(frames):
        await c.message.answer_photo(
            FSInputFile(frame),
            caption=f"Кадр #{idx+1}"
        )
    await c.message.answer(
        "Выбери номер стартового кадра:",
        reply_markup=frame_choice_menu(len(frames))
    )
    await c.answer()

# --- Обработка выбора стартового кадра ---
@dp.callback_query(F.data.startswith("frame_pick:"))
async def pick_frame_choice(c: CallbackQuery):
    idx = int(c.data.split(":",1)[1])
    frames = list_start_frames()[:5]
    if idx < 0 or idx >= len(frames):
        await c.message.answer("Некорректный выбор кадра.")
        return await c.answer()
    set_selected_frame(c.from_user.id, frames[idx])
    print(f"User {c.from_user.id} выбрал кадр {frames[idx]}")
    await c.message.answer(f"Выбран стартовый кадр #{idx+1}.", reply_markup=main_menu())
    await c.answer()

# --- Редактирование кадра ---
@dp.callback_query(F.data == "edit_frame")
async def ask_edit(c: CallbackQuery, state: FSMContext):
    if not get_selected_frame(c.from_user.id):
        await c.message.answer("Сначала выбери стартовый кадр.")
        return await c.answer()
    await state.set_state(FrameEdit.waiting_prompt)
    await c.message.answer("Напиши промт для редактирования кадра (например: «добавь логотип в углу, фон — супермаркет»).")
    await c.answer()

@dp.message(FrameEdit.waiting_prompt)
async def do_edit(m: Message, state: FSMContext):
    try:
        src = get_selected_frame(m.from_user.id)
        await m.answer("Редактирую кадр…")
        edited_path = await edit_image(src, m.text)
        set_selected_frame(m.from_user.id, edited_path)
        await m.answer_photo(FSInputFile(edited_path), caption="Новая версия кадра сохранена.")
    except Exception as e:
        await m.answer(f"Не удалось отредактировать: {e}")
    finally:
        await state.clear()

# --- Генерация аудио (TTS) ---
@dp.callback_query(F.data == "gen_audio")
async def ask_audio_text(c: CallbackQuery, state: FSMContext):
    samples = list_voice_samples()[:5]
    if not samples:
        await c.message.answer("Пока нет доступных голосов. Свяжитесь с администратором.")
        return await c.answer()
    # Отправляем по одному аудио с подписью
    for idx, (name, voice_id, path) in enumerate(samples):
        await c.message.answer_audio(
            FSInputFile(path),
            caption=f"Голос #{idx+1}: {name}"
        )
    await c.message.answer(
        "Выбери номер голоса:",
        reply_markup=voice_choice_menu(len(samples))
    )
    await c.answer()

@dp.callback_query(F.data.startswith("voice_pick:"))
async def set_voice(c: CallbackQuery, state: FSMContext):
    idx = int(c.data.split(":",1)[1])
    samples = list_voice_samples()[:5]
    if idx < 0 or idx >= len(samples):
        await c.message.answer("Некорректный выбор голоса.")
        return await c.answer()
    name, voice_id, _ = samples[idx]
    set_selected_voice(c.from_user.id, voice_id)
    await c.message.answer(f"Голос выбран: {name}. Теперь пришли текст для озвучки (до 1000 символов).")
    await state.set_state(AudioGen.waiting_text)
    await c.answer()

@dp.message(AudioGen.waiting_text)
async def do_audio(m: Message, state: FSMContext):
    try:
        voice_id = get_selected_voice(m.from_user.id)
        await m.answer("Генерирую аудио…")
        path = await tts_to_file(m.text, voice_id)
        set_last_audio(m.from_user.id, path)
        await m.answer_audio(FSInputFile(path), caption="Готово. Аудио сохранено.")
        
        # Clean up audio file after sending
        import os
        try:
            os.remove(path)
            print(f"Cleaned up audio file: {path}")
        except Exception as cleanup_error:
            print(f"Failed to cleanup audio file {path}: {cleanup_error}")
    except Exception as e:
        print(f"TTS Error for user {m.from_user.id}: {e}")  # Логируем для дебага
        await m.answer("Что-то пошло не так при генерации аудио. Мы уже чиним проблему, попробуй позже.")
    finally:
        await state.clear()

# --- Генерация видео с помощью Veo3 (-1 кредит) ---
@dp.callback_query(F.data == "video_duration")
async def ask_video_duration(c: CallbackQuery):
    from tg_bot.keyboards import video_duration_menu
    await c.message.edit_text(
        "🎬 Выбери продолжительность видео:",
        reply_markup=video_duration_menu()
    )
    await c.answer()

@dp.callback_query(F.data.startswith("video_dur_"))
async def ask_video_prompt(c: CallbackQuery, state: FSMContext):
    duration = int(c.data.split("_")[-1])  # Извлекаем 4, 6 или 8
    await state.update_data(video_duration=duration)
    
    duration_text = {
        4: "4 секунды (быстро)",
        6: "6 секунд (средне)", 
        8: "8 секунд (длинно)"
    }
    
    await state.set_state(VideoGen.waiting_prompt)
    await c.message.edit_text(
        f"🎬 Отлично! Продолжительность: {duration_text[duration]}\n\n"
        "Теперь напиши промт для видео.\n\n"
        "Например: 'Девушка танцует на пляже, закат, красивые движения'\n\n"
        "Видео будет в формате 9:16 (вертикальное)."
    )
    await c.answer()

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(c: CallbackQuery, state: FSMContext):
    from tg_bot.keyboards import main_menu
    await c.message.edit_text(
        "🤖 Главное меню:",
        reply_markup=main_menu()
    )
    await state.clear()
    await c.answer()

@dp.message(VideoGen.waiting_prompt)
async def do_video(m: Message, state: FSMContext):
    # Списываем кредит заранее (fail-fast)
    ok = spend_credits(m.from_user.id, 1, "veo3_video")
    if not ok:
        await m.answer("Недостаточно кредитов (нужен 1). Пополни у админа.")
        return await state.clear()

    try:
        # Получаем выбранную длительность
        data = await state.get_data()
        duration = data.get("video_duration", 6)  # По умолчанию 6 секунд
        
        await m.answer(f"Генерирую видео с помощью Veo3 ({duration} сек)… это может занять 2-3 минуты.")
        
        # Генерируем видео через Vertex AI Veo3
        video_path = await generate_video_veo3(
            prompt=m.text.strip(),
            duration_seconds=duration,
            aspect_ratio="9:16"
        )
        
        if video_path:
            await m.answer_video(FSInputFile(video_path), caption="Готово! (-1 кредит списан)")
            
            # Clean up video file after sending
            import os
            try:
                os.remove(video_path)
                print(f"Cleaned up video file: {video_path}")
            except Exception as cleanup_error:
                print(f"Failed to cleanup video file {video_path}: {cleanup_error}")
        else:
            raise Exception("Video generation failed")
            
    except Exception as e:
        # Возвращаем кредит при фейле
        from tg_bot.utils.credits import add_credits
        add_credits(m.from_user.id, 1, "refund_video_fail")
        print(f"Veo3 Error for user {m.from_user.id}: {e}")  # Логируем для дебага
        await m.answer("Что-то пошло не так при генерации видео. Мы уже чиним проблему, попробуй позже.")
    finally:
        await state.clear()

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
