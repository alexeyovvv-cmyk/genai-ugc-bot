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
        
        # Response structure: response.output[1].content[0].text
        # output[0] = reasoning, output[1] = assistant message
        try:
            # Navigate through the response structure
            if hasattr(response, 'output') and response.output:
                # Find the assistant message (skip reasoning items)
                for output_item in response.output:
                    if hasattr(output_item, 'role') and output_item.role == 'assistant':
                        if hasattr(output_item, 'content') and output_item.content:
                            # Get the text from first content item
                            first_content = output_item.content[0]
                            if hasattr(first_content, 'text'):
                                enhanced_text = first_content.text
                                break
                else:
                    # Fallback: try last output item
                    last_output = response.output[-1]
                    if hasattr(last_output, 'content') and last_output.content:
                        enhanced_text = last_output.content[0].text
                    else:
                        raise ValueError("Could not find text in response.output")
            else:
                raise ValueError("Response has no output field")
                
        except Exception as extract_error:
            logger.error(f"[ENHANCEMENT] Failed to extract text: {extract_error}")
            logger.error(f"[ENHANCEMENT] Full response: {response}")
            raise ValueError(f"Failed to extract enhanced text from OpenAI response: {extract_error}")
        
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
    
    Expected format: "[emotion] text\n[emotion] text" or "[emotion] text [emotion] text"
    
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
    logger.info(f"[ENHANCEMENT] Raw enhanced text: {enhanced_text}")
    
    # Regex pattern: [emotion] text до следующего [emotion] (с переносом или без) или конца
    # Changed from \n\[ to just \[ to catch emotions on the same line
    pattern = r'\[(\w+)\]\s*(.+?)(?=\s*\[|\Z)'
    matches = re.findall(pattern, enhanced_text, re.DOTALL)
    
    logger.info(f"[ENHANCEMENT] Regex found {len(matches)} matches")
    
    segments = []
    for i, (emotion, text) in enumerate(matches):
        # Clean up text (remove extra whitespace, newlines)
        text_clean = text.strip()
        logger.info(f"[ENHANCEMENT] Match {i+1}: emotion='{emotion}', text_raw='{text[:50]}...', text_clean='{text_clean[:50]}...'")
        if text_clean:
            segments.append({
                "emotion": emotion.strip(),
                "text": text_clean
            })
    
    logger.info(f"[ENHANCEMENT] Parsed {len(segments)} emotion segments")
    for i, seg in enumerate(segments):
        logger.info(f"[ENHANCEMENT] Segment {i+1}: emotion={seg['emotion']}, text={seg['text'][:50]}...")
    
    return segments


