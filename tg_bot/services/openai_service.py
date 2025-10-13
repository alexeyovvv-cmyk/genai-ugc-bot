# openai_service.py — генерация рекламных «хуков» (3-4 варианта)
from openai import OpenAI
from dotenv import load_dotenv
import os
import re

load_dotenv()

client = OpenAI()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

PROMPT_TMPL = """Ты — копирайтер перформанс-рекламы.
На вход: описание продукта и текущей акции: «{description}».
Сгенерируй ровно {n} коротких, цепляющих видео-хуков (1 фраза каждый, 6–12 слов),
без эмодзи и хэштегов, разговорным языком, в стиле UGC TikTok/Reels.
Формат ответа — нумерованный список:
1) ...
2) ...
"""

def _parse_numbered_list(text: str, expected_n: int) -> list[str]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    hooks: list[str] = []
    for line in lines:
        # Поддержка форматов: "1) ...", "1. ...", "1 - ..."
        m = re.match(r"^\d+[)\.-]\s*(.+)$", line)
        if m:
            hooks.append(m.group(1).strip())
        else:
            hooks.append(line)
        if len(hooks) == expected_n:
            break
    return hooks[:expected_n]

async def generate_hooks(description: str, n: int = 4) -> list[str]:
    prompt = PROMPT_TMPL.format(description=description, n=n)
    resp = client.responses.create(
        model=MODEL,
        input=prompt,
    )
    text = resp.output_text.strip()
    hooks = _parse_numbered_list(text, n)
    # Фоллбек: если почему-то меньше — дублируем/обрезаем
    while len(hooks) < n:
        hooks.append(hooks[-1] if hooks else "")
    return hooks[:n]