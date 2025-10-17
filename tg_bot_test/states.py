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
    waiting_gender_selection = State()  # ждем выбор пола персонажа
    waiting_age_selection = State()  # ждем выбор возраста персонажа
    waiting_character_gallery = State()  # ждем выбор персонажа из галереи
    waiting_voice_gallery = State()  # ждем выбор голоса из галереи с пагинацией
    waiting_voice_selection = State()  # ждем выбор голоса (старое состояние, для совместимости)
    waiting_character_text = State()  # ждем текст, что должен сказать персонаж
    waiting_audio_confirmation = State()  # ждем подтверждение аудио или переделку
    waiting_text_change_decision = State()  # ждем решение, менять ли текст
    waiting_new_character_text = State()  # ждем новый текст для переделки аудио

class Feedback(StatesGroup):
    """Состояния для обратной связи"""
    waiting_message = State()
