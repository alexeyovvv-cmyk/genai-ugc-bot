"""Lipsync video generation service using Replicate Sync Labs Lipsync 2.0."""
import os
import asyncio
import pathlib
import time
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Configuration
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
VIDEO_DIR = pathlib.Path(os.getenv("BASE_DIR", ".")) / "data" / "video"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)


async def generate_lipsync_video(
    audio_path: str,
    image_path: str,
) -> Optional[str]:
    """
    Generate lipsync video using Replicate Sync Labs Lipsync 2.0 model.
    
    Args:
        audio_path: Path to audio file (speech/voice)
        image_path: Path to starting image/frame (character face)
    
    Returns:
        Path to generated video file, or None if generation failed
    """
    try:
        import sys
        print(f"[LIPSYNC] Generating lipsync video...", flush=True)
        print(f"[LIPSYNC] Audio: {audio_path}", flush=True)
        print(f"[LIPSYNC] Image: {image_path}", flush=True)
        sys.stderr.write(f"[LIPSYNC] Starting lipsync generation...\n")
        sys.stderr.flush()
        
        if not REPLICATE_API_TOKEN:
            print("[LIPSYNC] ❌ REPLICATE_API_TOKEN not found in environment", flush=True)
            return None
        
        # Use synchronous function in thread to avoid blocking
        video_path = await asyncio.to_thread(
            _sync_generate_lipsync_replicate, audio_path, image_path
        )
        
        if video_path:
            print(f"[LIPSYNC] ✅ Video generated successfully: {video_path}", flush=True)
            return video_path
        else:
            print("[LIPSYNC] ❌ Video generation failed", flush=True)
            return None
        
    except Exception as e:
        print(f"[LIPSYNC] ❌ Lipsync video generation failed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return None


def _sync_generate_lipsync_replicate(audio_path: str, image_path: str) -> Optional[str]:
    """
    Generate lipsync video using Replicate Sync Labs Lipsync 2.0 API.
    
    This model takes an image and audio file and generates a video where
    the person in the image appears to speak the audio with lip sync.
    """
    import sys
    try:
        import replicate
        
        sys.stderr.write("[LIPSYNC] Initializing Replicate client...\n")
        sys.stderr.flush()
        
        # Initialize Replicate client
        client = replicate.Client(api_token=REPLICATE_API_TOKEN)
        
        print("[LIPSYNC] Starting Lipsync 2.0 generation via Replicate...", flush=True)
        sys.stderr.write(f"[LIPSYNC] Audio path: {audio_path}\n")
        sys.stderr.write(f"[LIPSYNC] Image path: {image_path}\n")
        sys.stderr.flush()
        
        # Lipsync 2.0 model
        model = "sync/lipsync-2"
        
        print(f"[LIPSYNC] Using model: {model}", flush=True)
        sys.stderr.write(f"[LIPSYNC] Model: {model}\n")
        sys.stderr.flush()
        
        # Open files and prepare input
        with open(audio_path, "rb") as audio_file, open(image_path, "rb") as img_file:
            input_params = {
                "audio": audio_file,
                "image": img_file,
            }
            
            print(f"[LIPSYNC] Input params prepared", flush=True)
            sys.stderr.write(f"[LIPSYNC] Calling Replicate API...\n")
            sys.stderr.flush()
            
            output = client.run(model, input=input_params)
        
        print(f"[LIPSYNC] ✅ Success with model: {model}", flush=True)
        sys.stderr.write(f"[LIPSYNC] ✅ Model succeeded\n")
        sys.stderr.flush()
        
        print(f"Replicate output: {output}")
        
        # Download video from URL
        if not output:
            print("No output from model")
            return None
            
        # Handle different output formats
        video_data = None
        
        if isinstance(output, str):
            # URL string
            if output.startswith('http'):
                print(f"Downloading video from URL: {output}")
                response = requests.get(output, timeout=120)  # Longer timeout for lipsync
                response.raise_for_status()
                video_data = response.content
            else:
                print(f"Unexpected string output: {output[:100]}...")
                return None
        elif isinstance(output, list) and len(output) > 0:
            # List of URLs or data
            first_item = output[0]
            if isinstance(first_item, str) and first_item.startswith('http'):
                print(f"Downloading video from URL: {first_item}")
                response = requests.get(first_item, timeout=120)
                response.raise_for_status()
                video_data = response.content
            else:
                video_data = first_item
        elif hasattr(output, 'read'):
            # File-like object
            video_data = output.read()
        else:
            # Assume it's binary data
            video_data = output
        
        if not video_data:
            print("No video data received")
            return None
        
        # Save video
        video_filename = f"lipsync_{int(time.time())}.mp4"
        video_path = VIDEO_DIR / video_filename
        
        with open(video_path, "wb") as f:
            f.write(video_data)
        
        print(f"Video saved: {video_path}")
        return str(video_path)
        
    except ImportError:
        print("Replicate package not installed. Run: pip install replicate")
        return None
    except Exception as e:
        print(f"Error in Lipsync 2.0 generation: {e}")
        import traceback
        traceback.print_exc()
        return None

