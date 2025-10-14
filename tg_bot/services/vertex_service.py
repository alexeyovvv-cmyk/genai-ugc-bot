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
    aspect_ratio: str = "9:16",  # Portrait format for mobile
    image_path: Optional[str] = None  # Стартовый кадр для video generation
) -> Optional[str]:
    """
    Generate video using Replicate Veo 3 model.
    
    Args:
        prompt: Text description for video generation
        duration_seconds: Video duration (default 5 seconds)
        aspect_ratio: Video aspect ratio (default "9:16" for mobile)
        image_path: Path to starting image/frame (optional)
    
    Returns:
        Path to generated video file, or None if generation failed
    """
    try:
        import sys
        print(f"[VEO3] Generating video with Replicate Veo 3...", flush=True)
        print(f"[VEO3] Prompt: '{prompt}'", flush=True)
        print(f"[VEO3] Duration: {duration_seconds}s, Aspect ratio: {aspect_ratio}", flush=True)
        print(f"[VEO3] Image path: {image_path}", flush=True)
        sys.stderr.write(f"[VEO3] Starting generation...\n")
        sys.stderr.flush()
        
        if not REPLICATE_API_TOKEN:
            print("[VEO3] ❌ REPLICATE_API_TOKEN not found in environment", flush=True)
            return None
        
        # Use synchronous function in thread to avoid blocking
        video_path = await asyncio.to_thread(
            _sync_generate_video_replicate, prompt, duration_seconds, aspect_ratio, image_path
        )
        
        if video_path:
            print(f"[VEO3] ✅ Video generated successfully: {video_path}", flush=True)
            return video_path
        else:
            print("[VEO3] ❌ Video generation failed", flush=True)
            return None
        
    except Exception as e:
        print(f"[VEO3] ❌ Replicate Veo 3 video generation failed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return None


def _sync_generate_video_replicate(prompt: str, duration_seconds: int, aspect_ratio: str, image_path: Optional[str] = None) -> Optional[str]:
    """
    Generate video using Replicate Veo 3 API.
    
    Replicate provides access to Google's Veo 3 model without quota issues.
    """
    import sys
    try:
        import replicate
        
        sys.stderr.write("[VEO3] Initializing Replicate client...\n")
        sys.stderr.flush()
        
        # Initialize Replicate client
        client = replicate.Client(api_token=REPLICATE_API_TOKEN)
        
        print("[VEO3] Starting Veo 3 generation via Replicate...", flush=True)
        sys.stderr.write(f"[VEO3] Image path provided: {image_path is not None}\n")
        sys.stderr.flush()
        
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
        
        print(f"[VEO3] Using aspect_ratio={replicate_ratio}, duration={replicate_duration}s", flush=True)
        
        # Try Veo 3 Fast first, fallback to cheaper models
        models_to_try = [
            "google/veo-3-fast",
            "stability-ai/stable-video-diffusion:76d4f5af2bfdfc908b13e8f4d02b5d1f38cf7c8caf54e8784feb472a4a995be4",
            "anotherjesse/zeroscope-v2-xl:9f747673945c62801b13b84701c783929c0ee784e4748ec062204894dda1a351"
        ]
        
        output = None
        for model in models_to_try:
            try:
                print(f"[VEO3] Trying model: {model}", flush=True)
                sys.stderr.write(f"[VEO3] Model: {model}\n")
                sys.stderr.flush()
                
                if "veo-3" in model:
                    # Veo 3 input parameters
                    input_params = {
                        "prompt": prompt,
                        "aspect_ratio": replicate_ratio,
                        "duration": replicate_duration
                    }
                    
                    # Add image if provided
                    if image_path:
                        print(f"[VEO3] Adding image_prompt from: {image_path}", flush=True)
                        sys.stderr.write(f"[VEO3] Reading image file...\n")
                        sys.stderr.flush()
                        
                        # Open and read image file
                        with open(image_path, "rb") as img_file:
                            input_params["image"] = img_file
                            print(f"[VEO3] Image added to input params", flush=True)
                            
                            sys.stderr.write(f"[VEO3] Calling Replicate API...\n")
                            sys.stderr.flush()
                            
                            output = client.run(model, input=input_params)
                    else:
                        sys.stderr.write(f"[VEO3] Calling Replicate API without image...\n")
                        sys.stderr.flush()
                        output = client.run(model, input=input_params)
                else:
                    # Different input format for other models
                    sys.stderr.write(f"[VEO3] Using fallback model format...\n")
                    sys.stderr.flush()
                    
                    output = client.run(
                        model,
                        input={
                            "prompt": prompt,
                            "width": 576 if replicate_ratio == "9:16" else 1024,
                            "height": 1024 if replicate_ratio == "9:16" else 576
                        }
                    )
                
                print(f"[VEO3] ✅ Success with model: {model}", flush=True)
                sys.stderr.write(f"[VEO3] ✅ Model succeeded\n")
                sys.stderr.flush()
                break
            except Exception as e:
                print(f"[VEO3] ❌ Failed with {model}: {str(e)[:200]}...", flush=True)
                sys.stderr.write(f"[VEO3] ❌ Error: {str(e)[:200]}\n")
                sys.stderr.flush()
                import traceback
                traceback.print_exc()
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