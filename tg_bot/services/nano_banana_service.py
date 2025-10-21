"""Character image editing service using fal.ai nano-banana model."""
import os
import asyncio
import pathlib
import time
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

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
        print(f"[NANO-BANANA] Starting character edit with prompt: '{prompt}'", flush=True)
        print(f"[NANO-BANANA] Original image: {image_path}", flush=True)
        
        if not FAL_API_KEY:
            print("[NANO-BANANA] ❌ FAL API KEY not found in environment", flush=True)
            print("[NANO-BANANA] Please set FALAI_API_TOKEN or FAL_KEY", flush=True)
            return None
        
        # Use synchronous function in thread to avoid blocking
        edited_path = await asyncio.to_thread(
            _sync_edit_character_image, image_path, prompt
        )
        
        if edited_path:
            print(f"[NANO-BANANA] ✅ Character edit successful: {edited_path}", flush=True)
            return edited_path
        else:
            print("[NANO-BANANA] ❌ Character edit failed", flush=True)
            return None
        
    except Exception as e:
        print(f"[NANO-BANANA] ❌ Character editing failed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return None


def _sync_edit_character_image(image_path: str, prompt: str) -> Optional[str]:
    """
    Edit character image using fal.ai nano-banana API.
    
    This model takes an image and text prompt to generate an edited version
    of the image with the requested changes.
    """
    try:
        import fal_client
        
        print("[NANO-BANANA] Initializing fal.ai client...", flush=True)
        
        # Configure fal_client with API key
        os.environ["FAL_KEY"] = FAL_API_KEY
        
        print("[NANO-BANANA] Starting nano-banana edit via fal.ai...", flush=True)
        
        # Nano-banana model path
        model = "fal-ai/nano-banana/edit"
        
        print(f"[NANO-BANANA] Using model: {model}", flush=True)
        
        # Upload image to fal.ai
        print("[NANO-BANANA] Uploading image...", flush=True)
        image_url = fal_client.upload_file(image_path)
        print(f"[NANO-BANANA] Image uploaded: {image_url}", flush=True)
        
        # Prepare input parameters for nano-banana
        input_params = {
            "prompt": prompt,
            "image_urls": [image_url],
            "num_images": 1,
            "output_format": "jpeg"
        }
        
        print(f"[NANO-BANANA] Input params prepared", flush=True)
        print(f"[NANO-BANANA] Calling fal.ai API...", flush=True)
        
        # Submit request and wait for result
        result = fal_client.subscribe(
            model,
            arguments=input_params,
            with_logs=True,
        )
        
        print(f"[NANO-BANANA] ✅ Success with model: {model}", flush=True)
        print(f"fal.ai result: {result}")
        
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
            print(f"[NANO-BANANA] ❌ Could not find edited image URL in result: {result}")
            return None
        
        print(f"[NANO-BANANA] Downloading edited image from: {edited_image_url}")
        
        # Download edited image from URL
        response = requests.get(edited_image_url, timeout=120)
        response.raise_for_status()
        image_data = response.content
        
        if not image_data:
            print("[NANO-BANANA] No edited image data received")
            return None
        
        # Save edited image
        timestamp = int(time.time())
        edited_filename = f"edited_character_{timestamp}.jpg"
        edited_path = TEMP_EDIT_DIR / edited_filename
        
        with open(edited_path, "wb") as f:
            f.write(image_data)
        
        print(f"[NANO-BANANA] Edited image saved: {edited_path}")
        return str(edited_path)
        
    except ImportError:
        print("[NANO-BANANA] fal-client package not installed. Run: pip install fal-client")
        return None
    except Exception as e:
        print(f"[NANO-BANANA] Error in nano-banana edit: {e}")
        import traceback
        traceback.print_exc()
        return None
