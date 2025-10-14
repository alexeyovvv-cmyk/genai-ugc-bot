"""Prompt Enhancer Service using OpenAI Responses API."""
import os
from openai import OpenAI

# ID предобученной модели для улучшения аудио промптов
AUDIO_PROMPT_ENHANCER_ID = "pmpt_68ee1528be408197aad9ecd5e1cce8180d820f61f9156d64"
AUDIO_PROMPT_ENHANCER_VERSION = "1"

# ID предобученной модели для улучшения видео промптов
VIDEO_PROMPT_ENHANCER_ID = "pmpt_68ee1f8a77a0819580db0b9c501a0d5e0bd2d22201316abf"
VIDEO_PROMPT_ENHANCER_VERSION = "1"


async def enhance_audio_prompt(user_text: str) -> str:
    """
    Улучшает промпт пользователя для генерации аудио через предобученную модель.
    
    Args:
        user_text: Оригинальный текст от пользователя
        
    Returns:
        Улучшенный промпт для генерации
    """
    import asyncio
    import sys
    
    def log(msg):
        """Логирование с принудительным flush"""
        print(msg, flush=True)
        sys.stdout.flush()
    
    log(f"[PromptEnhancer] Начинаем улучшение промпта: '{user_text[:50]}...'")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        log("[PromptEnhancer] ⚠️ OPENAI_API_KEY не установлен, пропускаем улучшение")
        return user_text
    
    try:
        # Создаем клиента OpenAI
        client = OpenAI(api_key=api_key)
        
        log(f"[PromptEnhancer] Вызываем ChatGPT для добавления эмоциональных тегов...")
        
        # Используем Chat Completions API для добавления тегов для ElevenLabs v3
        def _call_openai():
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты эксперт по улучшению текста для ElevenLabs TTS модели v3. "
                            "Твоя задача - добавить эмоциональные теги в квадратных скобках для более живой озвучки. "
                            "Используй ТОЛЬКО эти теги: [excited], [happy], [sad], [angry], [surprised], [calm], [whisper], [shouting]. "
                            "Размещай теги ПЕРЕД словами или фразами, которые нужно озвучить эмоционально. "
                            "Сохрани весь исходный текст, только добавь теги. "
                            "Верни ТОЛЬКО улучшенный текст с тегами, ничего больше."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Добавь эмоциональные теги к этому тексту: {user_text}"
                    }
                ],
                temperature=0.7,
                max_tokens=200
            )
            return response
        
        response = await asyncio.to_thread(_call_openai)
        
        # Извлекаем улучшенный текст
        enhanced_text = response.choices[0].message.content.strip()
        
        log(f"[PromptEnhancer] ✅ Промпт улучшен: '{enhanced_text[:80] if len(enhanced_text) > 80 else enhanced_text}'")
        
        return enhanced_text
        
    except Exception as e:
        log(f"[PromptEnhancer] ❌ Ошибка при улучшении промпта: {e}")
        import traceback
        traceback.print_exc()
        
        # В случае ошибки возвращаем оригинальный текст
        log("[PromptEnhancer] Используем оригинальный текст")
        return user_text


async def enhance_video_prompt(user_text: str) -> str:
    """
    Переводит на английский и улучшает промпт для генерации видео через предобученную модель.
    
    Args:
        user_text: Описание ситуации от пользователя (любой язык)
        
    Returns:
        Улучшенный промпт на английском для AI видео модели
    """
    import asyncio
    import sys
    
    def log(msg):
        """Логирование с принудительным flush"""
        print(msg, flush=True)
        sys.stdout.flush()
    
    log(f"[VideoPromptEnhancer] Начинаем улучшение видео промпта: '{user_text[:50]}...'")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        log("[VideoPromptEnhancer] ⚠️ OPENAI_API_KEY не установлен, пропускаем улучшение")
        return user_text
    
    try:
        # Создаем клиента OpenAI
        client = OpenAI(api_key=api_key)
        
        log(f"[VideoPromptEnhancer] Вызываем предобученную модель (Responses API)...")
        log(f"[VideoPromptEnhancer] Model ID: {VIDEO_PROMPT_ENHANCER_ID}")
        log(f"[VideoPromptEnhancer] Input text: {user_text}")
        
        # Вызываем предобученную модель в отдельном потоке
        def _call_openai():
            response = client.responses.create(
                prompt={
                    "id": VIDEO_PROMPT_ENHANCER_ID,
                    "version": VIDEO_PROMPT_ENHANCER_VERSION
                },
                input=[{
                    "role": "user",
                    "content": user_text
                }],
                reasoning={},
                store=True,
                include=[
                    "reasoning.encrypted_content",
                    "web_search_call.action.sources"
                ]
            )
            return response
        
        response = await asyncio.to_thread(_call_openai)
        
        # Извлекаем улучшенный текст из ответа
        enhanced_text = None
        
        # Responses API возвращает output как список с reasoning и message
        # Нужно найти message (пропустив reasoning)
        if hasattr(response, 'output') and isinstance(response.output, list):
            for item in response.output:
                # Пропускаем reasoning, ищем message
                if hasattr(item, 'type') and item.type == 'message':
                    if hasattr(item, 'content') and item.content:
                        content = item.content
                        # content обычно список с элементами, содержащими text
                        if isinstance(content, list) and len(content) > 0:
                            first_content = content[0]
                            if hasattr(first_content, 'text'):
                                enhanced_text = first_content.text
                            elif isinstance(first_content, dict) and 'text' in first_content:
                                enhanced_text = first_content['text']
                        elif isinstance(content, str):
                            enhanced_text = content
                    break
        
        if not enhanced_text:
            log(f"[VideoPromptEnhancer] ⚠️ Не удалось извлечь текст из ответа, используем оригинал")
            return user_text
        
        log(f"[VideoPromptEnhancer] ✅ Промпт улучшен: '{enhanced_text[:80] if len(enhanced_text) > 80 else enhanced_text}'")
        
        return enhanced_text
        
    except Exception as e:
        log(f"[VideoPromptEnhancer] ❌ Ошибка при улучшении промпта: {e}")
        import traceback
        traceback.print_exc()
        
        # В случае ошибки возвращаем оригинальный текст
        log("[VideoPromptEnhancer] Используем оригинальный текст")
        return user_text

