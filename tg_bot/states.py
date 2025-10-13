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
