def frame_choice_menu(count: int):
    # Кнопки 1..count, callback_data=frame_pick:N
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=str(i+1), callback_data=f"frame_pick:{i}")] for i in range(count)
        ]
    )
# keyboards.py — основные клавиатуры для бота
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    """Главное меню с плитками снизу экрана"""
    return InlineKeyboardMarkup(inline_keyboard=[
        # Первый ряд - основные функции
        [
            InlineKeyboardButton(text="🎬 UGC реклама", callback_data="create_ugc"),
            InlineKeyboardButton(text="💰 Кредиты", callback_data="credits")
        ],
        # Второй ряд - дополнительная информация
        [
            InlineKeyboardButton(text="❓ FAQ", callback_data="faq"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")
        ]
    ])

def ugc_start_menu():
    """Меню выбора персонажа с плитками"""
    return InlineKeyboardMarkup(inline_keyboard=[
        # Основные опции в два столбца
        [
            InlineKeyboardButton(text="👤 Выбрать персонажа", callback_data="select_character"),
            InlineKeyboardButton(text="✨ Создать персонажа", callback_data="create_character")
        ],
        # Навигация
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])

def character_choice_menu(count: int):
    """Меню выбора конкретного персонажа из предзагруженных"""
    buttons = [[InlineKeyboardButton(text=f"Персонаж #{i+1}", callback_data=f"char_pick:{i}")] for i in range(count)]
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_ugc")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def video_duration_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏱️ 4 секунды (быстро)", callback_data="video_dur_4")],
        [InlineKeyboardButton(text="⏱️ 6 секунд (средне)", callback_data="video_dur_6")],
        [InlineKeyboardButton(text="⏱️ 8 секунд (длинно)", callback_data="video_dur_8")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")],
    ])

def voices_menu(voices: list[str]):
    kb = [
        [InlineKeyboardButton(text=v, callback_data=f"voice:{v}")] for v in voices
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def voice_choice_menu(count: int):
    # Кнопки 1..count, callback_data=voice_pick:N
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=str(i+1), callback_data=f"voice_pick:{i}")] for i in range(count)
        ]
    )

def back_to_main_menu():
    """Кнопка возврата в главное меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Вернуться в главное меню", callback_data="back_to_main")]
    ])

def audio_confirmation_menu():
    """Меню подтверждения аудио после прослушивания"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Начать генерацию видео", callback_data="audio_confirmed")],
        [InlineKeyboardButton(text="🔄 Переделать аудио", callback_data="audio_redo")],
    ])

def text_change_decision_menu():
    """Меню выбора: менять текст или нет"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Да, изменить текст", callback_data="change_text_yes")],
        [InlineKeyboardButton(text="🔄 Нет, просто перегенерировать", callback_data="change_text_no")],
    ])

def settings_menu():
    """Меню настроек с плитками"""
    return InlineKeyboardMarkup(inline_keyboard=[
        # Основные настройки в два столбца
        [
            InlineKeyboardButton(text="🎤 Голоса", callback_data="voice_settings"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="stats")
        ],
        [
            InlineKeyboardButton(text="ℹ️ О боте", callback_data="about"),
            InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")
        ],
        # Навигация
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")]
    ])

def voice_settings_menu():
    """Меню настроек голосов"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎵 Прослушать голоса", callback_data="listen_voices"),
            InlineKeyboardButton(text="⚙️ Настройки TTS", callback_data="tts_settings")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="settings")]
    ])

def bottom_navigation_menu():
    """Нижнее меню навигации как на картинке"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚙️ Настройки модели", callback_data="model_settings"),
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile")
        ],
        [
            InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_main"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_previous")
        ]
    ])
