# states.py — FSM состояния
from aiogram.fsm.state import StatesGroup, State

class HookGen(StatesGroup):
    waiting_description = State()

class AudioGen(StatesGroup):
    waiting_text = State()

class FrameEdit(StatesGroup):
    waiting_prompt = State()

class VideoGen(StatesGroup):
    waiting_script = State()   # текст для озвучки/промт
    waiting_prompt = State()   # промт для видео после выбора длительности

class UGCCreation(StatesGroup):
    """Состояния для создания UGC рекламы"""
    waiting_voice_selection = State()  # ждем выбор голоса
    waiting_character_text = State()  # ждем текст, что должен сказать персонаж
    waiting_situation_prompt = State()  # ждем описание ситуации (промпт для видео)
