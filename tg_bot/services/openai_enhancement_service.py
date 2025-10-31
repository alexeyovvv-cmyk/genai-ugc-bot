"""OpenAI prompt enhancement service for emotion segmentation."""
import os
import re
import asyncio
from typing import List, Dict, Optional
from openai import OpenAI
from tg_bot.utils.logger import setup_logger

logger = setup_logger(__name__)

# Fine-tuned model ID for emotion segmentation
ENHANCEMENT_MODEL_ID = "pmpt_68ee1528be408197aad9ecd5e1cce8180d820f61f9156d64"

# Get OpenAI API key from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def _enhance_prompt_sync(text: str) -> str:
    """
    Synchronous call to OpenAI fine-tuned model for prompt enhancement.
    
    Args:
        text: User input text to enhance
        
    Returns:
        Enhanced text with emotion tags like "[happy] Text..."
    """
    if not OPENAI_API_KEY:
        logger.error("[ENHANCEMENT] OPENAI_API_KEY not found in environment")
        raise ValueError("OPENAI_API_KEY not set in environment")
    
    logger.info(f"[ENHANCEMENT] Starting prompt enhancement for text: {text[:50]}...")
    logger.info(f"[ENHANCEMENT] OpenAI model ID: {ENHANCEMENT_MODEL_ID[:20]}...")
    
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Call prompt API with user text
        response = client.responses.create(
            prompt={
                "id": ENHANCEMENT_MODEL_ID,
                "version": "4"
            },
            input=text
        )
        
        # Extract enhanced text from response
        logger.info(f"[ENHANCEMENT] Raw response type: {type(response)}")
        logger.info(f"[ENHANCEMENT] Raw response: {response}")
        
        # Try different ways to extract text
        if hasattr(response, 'text'):
            enhanced_text = response.text
        elif hasattr(response, 'output'):
            enhanced_text = response.output
        elif hasattr(response, 'content'):
            enhanced_text = response.content
        elif isinstance(response, dict):
            enhanced_text = response.get('text') or response.get('output') or response.get('content') or str(response)
        else:
            enhanced_text = str(response)
        
        logger.info(f"[ENHANCEMENT] Enhanced result: {enhanced_text}")
        
        return enhanced_text
        
    except Exception as e:
        logger.error(f"[ENHANCEMENT] OpenAI API error: {e}")
        raise


async def enhance_prompt(text: str) -> str:
    """
    Enhance user prompt using OpenAI fine-tuned model.
    
    Args:
        text: User input text
        
    Returns:
        Enhanced text with emotion tags
    """
    return await asyncio.to_thread(_enhance_prompt_sync, text)


def parse_emotion_segments(enhanced_text: str) -> List[Dict[str, str]]:
    """
    Parse enhanced text into emotion segments.
    
    Expected format: "[emotion] text\n[emotion] text"
    
    Args:
        enhanced_text: Text with emotion tags from OpenAI
        
    Returns:
        List of segments with emotion and text:
        [
            {"emotion": "happy", "text": "Some text"},
            {"emotion": "sad", "text": "Another text"}
        ]
    """
    logger.info(f"[ENHANCEMENT] Parsing emotion segments from enhanced text")
    
    # Regex pattern: [emotion] text до следующего [emotion] или конца
    pattern = r'\[(\w+)\]\s*(.+?)(?=\n\[|\Z)'
    matches = re.findall(pattern, enhanced_text, re.DOTALL)
    
    segments = []
    for emotion, text in matches:
        # Clean up text (remove extra whitespace, newlines)
        text_clean = text.strip()
        if text_clean:
            segments.append({
                "emotion": emotion.strip(),
                "text": text_clean
            })
    
    logger.info(f"[ENHANCEMENT] Parsed {len(segments)} emotion segments")
    for i, seg in enumerate(segments):
        logger.info(f"[ENHANCEMENT] Segment {i+1}: emotion={seg['emotion']}, text={seg['text'][:30]}...")
    
    return segments


