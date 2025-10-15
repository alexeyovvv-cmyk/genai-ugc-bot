"""Video generation service using fal.ai OmniHuman model."""
import os
import asyncio
import pathlib
import time
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Configuration
# Support both FALAI_API_TOKEN and FAL_KEY
FAL_API_KEY = os.getenv("FALAI_API_TOKEN") or os.getenv("FAL_KEY", "")
VIDEO_DIR = pathlib.Path(os.getenv("BASE_DIR", ".")) / "data" / "video"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)


async def generate_talking_head_video(
    audio_path: str,
    image_path: str,
) -> Optional[str]:
    """
    Generate talking head video using fal.ai OmniHuman model.
    
    Args:
        audio_path: Path to audio file (speech/voice)
        image_path: Path to starting image/frame (character face)
    
    Returns:
        Path to generated video file, or None if generation failed
    """
    try:
        import sys
        print(f"[FALAI] Generating talking head video with OmniHuman...", flush=True)
        print(f"[FALAI] Audio: {audio_path}", flush=True)
        print(f"[FALAI] Image: {image_path}", flush=True)
        sys.stderr.write(f"[FALAI] Starting video generation...\n")
        sys.stderr.flush()
        
        if not FAL_API_KEY:
            print("[FALAI] ❌ FAL API KEY not found in environment", flush=True)
            print("[FALAI] Please set FALAI_API_TOKEN or FAL_KEY", flush=True)
            return None
        
        # Use synchronous function in thread to avoid blocking
        video_path = await asyncio.to_thread(
            _sync_generate_talking_head, audio_path, image_path
        )
        
        if video_path:
            print(f"[FALAI] ✅ Video generated successfully: {video_path}", flush=True)
            return video_path
        else:
            print("[FALAI] ❌ Video generation failed", flush=True)
            return None
        
    except Exception as e:
        print(f"[FALAI] ❌ Talking head video generation failed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return None


def _sync_generate_talking_head(audio_path: str, image_path: str) -> Optional[str]:
    """
    Generate talking head video using fal.ai OmniHuman API.
    
    This model takes an image and audio file and generates a video where
    the person in the image appears to speak the audio with lip sync.
    """
    import sys
    try:
        import fal_client
        
        sys.stderr.write("[FALAI] Initializing fal.ai client...\n")
        sys.stderr.flush()
        
        # Configure fal_client with API key
        os.environ["FAL_KEY"] = FAL_API_KEY
        
        print("[FALAI] Starting OmniHuman generation via fal.ai...", flush=True)
        sys.stderr.write(f"[FALAI] Audio path: {audio_path}\n")
        sys.stderr.write(f"[FALAI] Image path: {image_path}\n")
        sys.stderr.flush()
        
        # OmniHuman model path
        model = "fal-ai/bytedance/omnihuman"
        
        print(f"[FALAI] Using model: {model}", flush=True)
        sys.stderr.write(f"[FALAI] Model: {model}\n")
        sys.stderr.flush()
        
        # Upload files to fal.ai
        print(f"[FALAI] Uploading image...", flush=True)
        image_url = fal_client.upload_file(image_path)
        print(f"[FALAI] Image uploaded: {image_url}", flush=True)
        
        print(f"[FALAI] Uploading audio...", flush=True)
        audio_url = fal_client.upload_file(audio_path)
        print(f"[FALAI] Audio uploaded: {audio_url}", flush=True)
        
        # Prepare input parameters
        input_params = {
            "image_url": image_url,
            "audio_url": audio_url,
        }
        
        print(f"[FALAI] Input params prepared", flush=True)
        sys.stderr.write(f"[FALAI] Calling fal.ai API...\n")
        sys.stderr.flush()
        
        # Submit request and wait for result
        result = fal_client.subscribe(
            model,
            arguments=input_params,
            with_logs=True,
        )
        
        print(f"[FALAI] ✅ Success with model: {model}", flush=True)
        sys.stderr.write(f"[FALAI] ✅ Model succeeded\n")
        sys.stderr.flush()
        
        print(f"fal.ai result: {result}")
        
        # Extract video URL from result
        video_url = None
        
        if isinstance(result, dict):
            # Try different possible keys
            if 'video' in result:
                video_data = result['video']
                if isinstance(video_data, dict) and 'url' in video_data:
                    video_url = video_data['url']
                elif isinstance(video_data, str):
                    video_url = video_data
            elif 'video_url' in result:
                video_url = result['video_url']
            elif 'url' in result:
                video_url = result['url']
            elif 'output' in result:
                output = result['output']
                if isinstance(output, dict) and 'url' in output:
                    video_url = output['url']
                elif isinstance(output, str):
                    video_url = output
        
        if not video_url:
            print(f"[FALAI] ❌ Could not find video URL in result: {result}")
            return None
        
        print(f"[FALAI] Downloading video from: {video_url}")
        
        # Download video from URL
        response = requests.get(video_url, timeout=120)
        response.raise_for_status()
        video_data = response.content
        
        if not video_data:
            print("[FALAI] No video data received")
            return None
        
        # Save video
        video_filename = f"datanauts_ugcad_{int(time.time())}.mp4"
        video_path = VIDEO_DIR / video_filename
        
        with open(video_path, "wb") as f:
            f.write(video_data)
        
        print(f"[FALAI] Video saved: {video_path}")
        return str(video_path)
        
    except ImportError:
        print("[FALAI] fal-client package not installed. Run: pip install fal-client")
        return None
    except Exception as e:
        print(f"[FALAI] Error in OmniHuman generation: {e}")
        import traceback
        traceback.print_exc()
        return None

