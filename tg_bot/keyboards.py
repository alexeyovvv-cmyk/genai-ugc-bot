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
            InlineKeyboardButton(text="📁 Мои генерации", callback_data="my_generations"),
            InlineKeyboardButton(text="❓ FAQ", callback_data="faq")
        ],
        # Третий ряд - обратная связь
        [
            InlineKeyboardButton(text="✉️ Обратная связь", callback_data="feedback")
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

def gender_selection_menu():
    """Меню выбора пола персонажа"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👨 Мужской", callback_data="gender_male"),
            InlineKeyboardButton(text="👩 Женский", callback_data="gender_female")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_ugc")]
    ])


def character_gallery_menu(page: int, has_next: bool, total_count: int):
    """Меню галереи персонажей с выбором и пагинацией.
    total_count — кол-во персонажей, показанных на текущей странице (≤5).
    """
    buttons = []

    # Кнопки выбора персонажей (по одному в строке)
    for i in range(total_count):
        global_index = page * 5 + i
        buttons.append([
            InlineKeyboardButton(
                text=f"Выбрать персонажа #{global_index+1}",
                callback_data=f"char_pick:{global_index}"
            )
        ])

    # Кнопки навигации по страницам
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Предыдущая", callback_data=f"char_page:{page-1}"))
    if has_next:
        nav_buttons.append(InlineKeyboardButton(text="Следующая страница ➡️", callback_data=f"char_page:{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    # Кнопка изменения параметров и назад
    buttons.append([InlineKeyboardButton(text="🔄 Изменить пол персонажа", callback_data="change_character_params")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_gender")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def character_selection_menu(character_count: int, page: int):
    """Меню выбора конкретного персонажа с учетом страницы"""
    buttons = []
    
    # Кнопки выбора персонажей (максимум 5 на странице)
    for i in range(character_count):
        global_index = page * 5 + i
        buttons.append([InlineKeyboardButton(text=f"Персонаж #{global_index+1}", callback_data=f"char_pick:{global_index}")])
    
    # Кнопка изменения параметров
    buttons.append([InlineKeyboardButton(text="🔄 Изменить параметры персонажа", callback_data="change_character_params")])
    
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

def voice_gallery_menu(page: int, has_next: bool, total_count: int):
    """Меню галереи голосов с выбором и пагинацией.
    total_count — кол-во голосов, показанных на текущей странице (≤5).
    """
    buttons = []

    # Кнопки выбора голосов (по одному в строке)
    for i in range(total_count):
        global_index = page * 5 + i
        buttons.append([
            InlineKeyboardButton(
                text=f"Выбрать голос #{global_index+1}",
                callback_data=f"voice_pick:{global_index}"
            )
        ])

    # Кнопки навигации по страницам
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Предыдущая", callback_data=f"voice_page:{page-1}"))
    if has_next:
        nav_buttons.append(InlineKeyboardButton(text="Следующая страница ➡️", callback_data=f"voice_page:{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    # Кнопка изменения параметров персонажа и назад
    buttons.append([InlineKeyboardButton(text="🔄 Изменить персонажа", callback_data="change_character_params")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_character_gallery")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def voice_choice_menu(count: int):
    # Кнопки 1..count, callback_data=voice_pick:N (для обратной совместимости)
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


def text_change_decision_menu():
    """Меню выбора: менять текст или нет"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Да, изменить текст", callback_data="change_text_yes")],
        [InlineKeyboardButton(text="🔄 Нет, просто перегенерировать", callback_data="change_text_no")],
        [InlineKeyboardButton(text="🎤 Выбрать другой голос", callback_data="change_voice")],
    ])

def settings_menu():
    """Меню настроек с плитками"""
    return InlineKeyboardMarkup(inline_keyboard=[
        # Основные настройки в два столбца
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
            InlineKeyboardButton(text="ℹ️ О боте", callback_data="about"),
        ],
        [
            InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")
        ],
        # Навигация
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")]
    ])

def credits_menu():
    """Меню раздела кредитов: пополнение и назад"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Пополнить счёт", callback_data="topup_request")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")],
    ])

def feedback_menu():
    """Меню обратной связи"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Написать обратную связь", callback_data="feedback_write")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")],
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

# Character editing keyboards
def character_edit_offer_menu():
    """Меню предложения редактирования персонажа"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Редактировать персонажа", callback_data="edit_character_yes")],
        [InlineKeyboardButton(text="✅ Использовать как есть", callback_data="edit_character_no")]
    ])

def edit_result_menu():
    """Меню выбора после показа отредактированного результата"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Редактировать дальше", callback_data="continue_editing")],
        [InlineKeyboardButton(text="📷 Использовать оригинал", callback_data="use_original_character")],
        [InlineKeyboardButton(text="✨ Использовать эту редакцию", callback_data="use_edited_character")]
    ])

def edit_error_menu():
    """Меню при ошибке редактирования"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Попробовать другой промпт", callback_data="retry_edit_prompt")],
        [InlineKeyboardButton(text="📷 Использовать оригинал", callback_data="use_original_character")]
    ])

def format_selection_menu():
    """Меню выбора формата видео"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Говорящая голова", callback_data="format_talking_head")],
        [InlineKeyboardButton(text="🎬 Персонаж с бекграундом", callback_data="format_character_background")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])

def video_editing_menu(render_settings_available: bool = False):
    """Меню выбора: монтаж или завершить (с настройками при наличии рендера)."""
    rows = [[InlineKeyboardButton(text="🎬 Монтаж", callback_data="start_video_editing")]]
    if render_settings_available:
        rows.append([InlineKeyboardButton(text="⚙️ Настройки рендера", callback_data="render_edit:open")])
    rows.append([InlineKeyboardButton(text="✅ Завершить", callback_data="finish_generation")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def render_settings_menu():
    """Меню настроек для повторного рендера"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Шаблоны", callback_data="render_edit:templates"),
            InlineKeyboardButton(text="💬 Субтитры", callback_data="render_edit:subtitles"),
        ],
        [
            InlineKeyboardButton(text="🎬 Интро", callback_data="render_edit:intro"),
            InlineKeyboardButton(text="🏁 Аутро", callback_data="render_edit:outro"),
        ],
        [
            InlineKeyboardButton(text="⭕ Circle", callback_data="render_edit:circle"),
        ],
        [
            InlineKeyboardButton(text="🚀 Пересобрать", callback_data="render_edit:rerender"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="render_edit:cancel"),
        ],
    ])
