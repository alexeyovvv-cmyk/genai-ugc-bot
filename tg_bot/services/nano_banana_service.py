"""Character image editing service using fal.ai nano-banana model."""
import os
import asyncio
import pathlib
import time
import requests
from typing import Optional
from dotenv import load_dotenv
from tg_bot.utils.logger import setup_logger

load_dotenv()
logger = setup_logger(__name__)

# Configuration
FAL_API_KEY = os.getenv("FALAI_API_TOKEN") or os.getenv("FAL_KEY", "")
TEMP_EDIT_DIR = pathlib.Path(os.getenv("BASE_DIR", ".")) / "data" / "temp_edits"
TEMP_EDIT_DIR.mkdir(parents=True, exist_ok=True)


async def edit_character_image(image_path: str, prompt: str) -> Optional[str]:
    """
    Edit character image using fal.ai nano-banana model.
    
    Args:
        image_path: Path to original character image
        prompt: User's edit description (e.g., "add sunglasses", "change background to beach")
    
    Returns:
        Path to edited image file, or None if editing failed
    """
    try:
        logger.info(f"[NANO-BANANA] Starting character edit with prompt: '{prompt}'")
        logger.info(f"[NANO-BANANA] Original image: {image_path}")
        
        if not FAL_API_KEY:
            logger.error("[NANO-BANANA] ❌ FAL API KEY not found in environment")
            logger.error("[NANO-BANANA] Please set FALAI_API_TOKEN or FAL_KEY")
            return None
        
        # Use synchronous function in thread to avoid blocking
        edited_path = await asyncio.to_thread(
            _sync_edit_character_image, image_path, prompt
        )
        
        if edited_path:
            logger.info(f"[NANO-BANANA] ✅ Character edit successful: {edited_path}")
            return edited_path
        else:
            logger.error("[NANO-BANANA] ❌ Character edit failed")
            return None
        
    except Exception as e:
        logger.error(f"[NANO-BANANA] ❌ Character editing failed: {e}", exc_info=True)
        return None


def _sync_edit_character_image(image_path: str, prompt: str) -> Optional[str]:
    """
    Edit character image using fal.ai nano-banana API.
    
    This model takes an image and text prompt to generate an edited version
    of the image with the requested changes.
    """
    try:
        import fal_client
        
        logger.info("[NANO-BANANA] Initializing fal.ai client...")
        
        # Configure fal_client with API key
        os.environ["FAL_KEY"] = FAL_API_KEY
        
        logger.info("[NANO-BANANA] Starting nano-banana edit via fal.ai...")
        
        # Nano-banana model path
        model = "fal-ai/nano-banana/edit"
        
        logger.info(f"[NANO-BANANA] Using model: {model}")
        
        # Upload image to fal.ai
        logger.info("[NANO-BANANA] Uploading image...")
        image_url = fal_client.upload_file(image_path)
        logger.info(f"[NANO-BANANA] Image uploaded: {image_url}")
        
        # Prepare input parameters for nano-banana
        input_params = {
            "prompt": prompt,
            "image_urls": [image_url],
            "num_images": 1,
            "output_format": "jpeg"
        }
        
        logger.info(f"[NANO-BANANA] Input params prepared")
        logger.info(f"[NANO-BANANA] Calling fal.ai API...")
        
        # Submit request and wait for result
        result = fal_client.subscribe(
            model,
            arguments=input_params,
            with_logs=True,
        )
        
        logger.info(f"[NANO-BANANA] ✅ Success with model: {model}")
        logger.info(f"fal.ai result: {result}")
        
        # Extract edited image URL from result
        edited_image_url = None
        
        if isinstance(result, dict):
            # Try different possible keys for the edited image
            if 'images' in result:
                images = result['images']
                if isinstance(images, list) and len(images) > 0:
                    first_image = images[0]
                    if isinstance(first_image, dict) and 'url' in first_image:
                        edited_image_url = first_image['url']
                    elif isinstance(first_image, str):
                        edited_image_url = first_image
            elif 'image' in result:
                image_data = result['image']
                if isinstance(image_data, dict) and 'url' in image_data:
                    edited_image_url = image_data['url']
                elif isinstance(image_data, str):
                    edited_image_url = image_data
            elif 'url' in result:
                edited_image_url = result['url']
        
        if not edited_image_url:
            logger.error(f"[NANO-BANANA] ❌ Could not find edited image URL in result: {result}")
            return None
        
        logger.info(f"[NANO-BANANA] Downloading edited image from: {edited_image_url}")
        
        # Download edited image from URL
        response = requests.get(edited_image_url, timeout=120)
        response.raise_for_status()
        image_data = response.content
        
        if not image_data:
            logger.error("[NANO-BANANA] No edited image data received")
            return None
        
        # Save edited image to R2
        timestamp = int(time.time())
        edited_filename = f"edited_character_{timestamp}.jpg"
        
        # First save locally as temp
        temp_path = TEMP_EDIT_DIR / edited_filename
        with open(temp_path, "wb") as f:
            f.write(image_data)
        
        logger.info(f"[NANO-BANANA] Edited image saved locally: {temp_path}")
        
        # Upload to R2
        from tg_bot.services.r2_service import upload_file
        r2_key = f"users/temp_edits/{edited_filename}"
        
        if upload_file(str(temp_path), r2_key):
            logger.info(f"[NANO-BANANA] ✅ Uploaded to R2: {r2_key}")
            # Delete local temp file
            os.remove(str(temp_path))
            # Return R2 key instead of local path
            return r2_key
        else:
            logger.warning(f"[NANO-BANANA] ⚠️ R2 upload failed, using local: {temp_path}")
            return str(temp_path)  # Fallback to local
        
    except ImportError:
        logger.error("[NANO-BANANA] fal-client package not installed. Run: pip install fal-client")
        return None
    except Exception as e:
        logger.error(f"[NANO-BANANA] Error in nano-banana edit: {e}", exc_info=True)
        return None
