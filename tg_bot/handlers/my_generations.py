"""My generations handlers for the Telegram bot.

This module contains handlers for:
- Showing user's generation history
"""

from aiogram import F
from aiogram.types import CallbackQuery

from tg_bot.utils.credits import ensure_user
from tg_bot.utils.user_storage import get_user_generations, get_user_storage_stats
from tg_bot.keyboards import back_to_main_menu
from tg_bot.utils.logger import setup_logger
from tg_bot.dispatcher import dp

logger = setup_logger(__name__)


@dp.callback_query(F.data == "my_generations")
async def show_my_generations(c: CallbackQuery):
    """Показать историю генераций пользователя"""
    try:
        user_id = c.from_user.id
        ensure_user(user_id)
        
        # Получаем историю генераций
        generations = get_user_generations(user_id, limit=10)
        
        if not generations:
            await c.message.answer(
                "📁 <b>Мои генерации</b>\n\n"
                "У вас пока нет созданных видео.\n"
                "Создайте свою первую UGC рекламу!",
                parse_mode="HTML",
                reply_markup=back_to_main_menu()
            )
            return await c.answer()
        
        # Отправляем список с ссылками на видео
        message_text = f"📁 <b>Мои генерации</b>\n\nНайдено: {len(generations)} видео\n\n"
        
        for i, gen in enumerate(generations, 1):
            created_at = gen['created_at'].strftime('%d.%m.%Y %H:%M')
            character_info = f"{gen['character_gender']}/{gen['character_age']}" if gen['character_gender'] else "Неизвестно"
            
            message_text += f"🎥 <b>Видео #{i}</b>\n"
            message_text += f"📅 {created_at}\n"
            message_text += f"👤 Персонаж: {character_info}\n"
            message_text += f"💰 Потрачено: {gen['credits_spent']} кредит(ов)\n"
            
            if gen['text_prompt']:
                message_text += f"💬 Текст: {gen['text_prompt'][:50]}{'...' if len(gen['text_prompt']) > 50 else ''}\n"
            
            if gen['has_video'] and gen['video_url']:
                message_text += f"🔗 <a href='{gen['video_url']}'>Скачать видео</a>\n"
            else:
                message_text += "❌ Видео недоступно\n"
            
            message_text += "\n"
        
        # Добавляем статистику
        stats = get_user_storage_stats(user_id)
        message_text += f"📊 <b>Статистика:</b>\n"
        message_text += f"Всего генераций: {stats['total_generations']}\n"
        message_text += f"Потрачено кредитов: {stats['total_credits_spent']}\n"
        
        # Добавляем инструкцию
        message_text += f"\n💡 <b>Как скачать:</b>\n"
        message_text += f"• Нажмите на ссылку 'Скачать видео'\n"
        message_text += f"• Видео откроется в браузере\n"
        message_text += f"• Нажмите 'Скачать' в браузере\n"
        message_text += f"• Ссылки действительны 24 часа"
        
        await c.message.answer(
            message_text,
            parse_mode="HTML",
            reply_markup=back_to_main_menu()
        )
        
    except Exception as e:
        logger.error(f"[MY_GENERATIONS] Error: {e}")
        await c.message.answer(
            "❌ Произошла ошибка при загрузке истории генераций.\n\n"
            "Попробуйте позже или свяжитесь с поддержкой.",
            reply_markup=back_to_main_menu()
        )
    
    await c.answer()
