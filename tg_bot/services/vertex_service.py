"""Video generation service using Replicate Veo 3."""
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


async def generate_video_veo3(
    prompt: str,
    duration_seconds: int = 5,
    aspect_ratio: str = "9:16"  # Portrait format for mobile
) -> Optional[str]:
    """
    Generate video using Replicate Veo 3 model.
    
    Args:
        prompt: Text description for video generation
        duration_seconds: Video duration (default 5 seconds)
        aspect_ratio: Video aspect ratio (default "9:16" for mobile)
    
    Returns:
        Path to generated video file, or None if generation failed
    """
    try:
        print(f"Generating video with Replicate Veo 3...")
        print(f"Prompt: '{prompt}'")
        print(f"Duration: {duration_seconds}s, Aspect ratio: {aspect_ratio}")
        
        if not REPLICATE_API_TOKEN:
            print("REPLICATE_API_TOKEN not found in environment")
            return None
        
        # Use synchronous function in thread to avoid blocking
        video_path = await asyncio.to_thread(
            _sync_generate_video_replicate, prompt, duration_seconds, aspect_ratio
        )
        
        if video_path:
            print(f"Video generated successfully: {video_path}")
            return video_path
        else:
            print("Video generation failed")
            return None
        
    except Exception as e:
        print(f"Replicate Veo 3 video generation failed: {e}")
        return None


def _sync_generate_video_replicate(prompt: str, duration_seconds: int, aspect_ratio: str) -> Optional[str]:
    """
    Generate video using Replicate Veo 3 API.
    
    Replicate provides access to Google's Veo 3 model without quota issues.
    """
    try:
        import replicate
        
        # Initialize Replicate client
        client = replicate.Client(api_token=REPLICATE_API_TOKEN)
        
        print("Starting Veo 3 generation via Replicate...")
        
        # Map aspect ratio to Replicate format
        # Replicate Veo 3 supports: 16:9, 9:16, 1:1
        ratio_mapping = {
            "9:16": "9:16",
            "16:9": "16:9", 
            "1:1": "1:1"
        }
        replicate_ratio = ratio_mapping.get(aspect_ratio, "9:16")
        
        # Map duration to Replicate format (Veo 3 supports 4s, 6s, 8s)
        duration_mapping = {
            4: 4,
            5: 4,  # Map 5s to 4s (closest supported)
            6: 6,
            8: 8
        }
        replicate_duration = duration_mapping.get(duration_seconds, 4)
        
        # Try Veo 3 first, fallback to cheaper models
        models_to_try = [
            "google/veo-3",
            "stability-ai/stable-video-diffusion:76d4f5af2bfdfc908b13e8f4d02b5d1f38cf7c8caf54e8784feb472a4a995be4",
            "anotherjesse/zeroscope-v2-xl:9f747673945c62801b13b84701c783929c0ee784e4748ec062204894dda1a351"
        ]
        
        output = None
        for model in models_to_try:
            try:
                print(f"Trying model: {model}")
                if "veo-3" in model:
                    output = client.run(
                        model,
                        input={
                            "prompt": prompt,
                            "aspect_ratio": replicate_ratio,
                            "duration": replicate_duration
                        }
                    )
                else:
                    # Different input format for other models
                    output = client.run(
                        model,
                        input={
                            "prompt": prompt,
                            "width": 576 if replicate_ratio == "9:16" else 1024,
                            "height": 1024 if replicate_ratio == "9:16" else 576
                        }
                    )
                print(f"✅ Success with model: {model}")
                break
            except Exception as e:
                print(f"❌ Failed with {model}: {str(e)[:100]}...")
                continue
        
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
                response = requests.get(output, timeout=60)
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
                response = requests.get(first_item, timeout=60)
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
        video_filename = f"veo3_{int(time.time())}.mp4"
        video_path = VIDEO_DIR / video_filename
        
        with open(video_path, "wb") as f:
            f.write(video_data)
        
        print(f"Video saved: {video_path}")
        return str(video_path)
        
    except ImportError:
        print("Replicate package not installed. Run: pip install replicate")
        return None
    except Exception as e:
        print(f"Error in Replicate Veo 3 generation: {e}")
        import traceback
        traceback.print_exc()
        return None