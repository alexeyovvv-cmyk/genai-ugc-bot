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
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💡 Сгенерировать видео-хук", callback_data="hooks")],
        [InlineKeyboardButton(text="🖼️ Выбрать стартовый кадр", callback_data="pick_frame")],
        [InlineKeyboardButton(text="✏️ Редактировать кадр (пока не доступно)", callback_data="edit_frame")],
        [InlineKeyboardButton(text="🎤 Сгенерировать аудио", callback_data="gen_audio")],
        [InlineKeyboardButton(text="🎬 Сгенерировать видео", callback_data="video_duration")],
        [InlineKeyboardButton(text="💰 Кредиты", callback_data="credits")],
    ])

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
