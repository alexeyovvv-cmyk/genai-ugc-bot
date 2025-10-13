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
    """Главное меню с двумя основными опциями"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Создать UGC рекламу", callback_data="create_ugc")],
        [InlineKeyboardButton(text="❓ Как пользоваться (FAQ)", callback_data="faq")],
        [InlineKeyboardButton(text="💰 Кредиты", callback_data="credits")],
    ])

def ugc_start_menu():
    """Меню выбора персонажа"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Выбрать персонажа", callback_data="select_character")],
        [InlineKeyboardButton(text="✨ Создать персонажа", callback_data="create_character")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")],
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
