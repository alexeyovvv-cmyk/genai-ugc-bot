"""
Modal GPU service for video overlay processing.
Handles background removal and alpha-matted video generation on A10G GPU.

Endpoints:
- /submit - POST: Submit overlay processing job
- /status/{job_id} - GET: Check job status
- /result/{job_id} - GET: Get job result
"""
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

import modal

# Define Modal app
app = modal.App("datanauts-overlay")

# GPU-enabled image with all dependencies
# Add video_editing directory into the image
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "ffmpeg",
        "libgl1",
        "libglib2.0-0",
        "libsm6",
        "libxext6",
        "libxrender1",
        "libgomp1",
    )
    .pip_install(
        "fastapi[standard]",  # Required for web endpoints
        "opencv-python==4.8.1.78",
        "mediapipe==0.10.8",
        "rembg==2.0.50",
        "onnxruntime-gpu==1.16.3",
        "numpy==1.24.3",
        "requests==2.31.0",
        "pillow==10.1.0",
    )
    .add_local_dir("../video_editing", remote_path="/root/video_editing")
)


@app.function(
    gpu="A10G",  # A10G GPU for optimal performance
    image=image,
    timeout=600,  # 10 minutes max
    secrets=[modal.Secret.from_name("shotstuck")],
    cpu=2.0,
    memory=4096,  # 4GB RAM
)
def process_overlay(
    video_url: str,
    container: str = "mov",
    threshold: float = 0.6,
    feather: int = 7,
    engine: str = "mediapipe",
    rembg_model: str = "u2net_human_seg",
    rembg_alpha_matting: bool = False,
    rembg_fg_threshold: int = 240,
    rembg_bg_threshold: int = 10,
    rembg_erode_size: int = 10,
    rembg_base_size: int = 1000,
    shape: str = "circle",
    circle_radius: float = 0.35,
    circle_center_x: float = 0.5,
    circle_center_y: float = 0.5,
    circle_auto_center: bool = True,
) -> dict:
    """
    Process video overlay on GPU: remove background and create transparent overlay.
    
    Args:
        video_url: URL of source video
        container: "mov" or "webm"
        threshold: segmentation threshold (0.0-1.0)
        feather: edge blur size
        engine: "mediapipe" (faster) or "rembg" (better quality)
        rembg_model: rembg model name (if engine="rembg")
        shape: "rect" or "circle"
        circle_*: circle mask parameters
        circle_auto_center: auto-detect circle center and radius from mask (default: True)
        
    Returns:
        dict with:
            - overlay_url: URL of ready overlay on Shotstack
            - duration: video duration
            - processing_time: processing time in seconds
            - status: "success" or "failed"
    """
    start_time = time.time()
    
    # Add video_editing to path
    sys.path.insert(0, "/root/video_editing")
    
    try:
        import prepare_overlay
        
        # Get Shotstack credentials from secrets
        shotstack_api_key = os.environ["SHOTSTACK_API_KEY"]
        shotstack_stage = os.environ.get("SHOTSTACK_STAGE", "stage")
        
        print(f"[MODAL] Starting overlay processing: engine={engine}, shape={shape}")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / f"overlay_{shape}.{container}"
            
            # Call existing prepare_overlay function
            overlay_url = prepare_overlay.prepare_overlay(
                video_url,
                output_path,
                shotstack_stage,
                shotstack_api_key,
                container,
                threshold=threshold,
                feather=feather,
                debug=False,
                engine=engine,
                rembg_model=rembg_model,
                rembg_alpha_matting=rembg_alpha_matting,
                rembg_fg_threshold=rembg_fg_threshold,
                rembg_bg_threshold=rembg_bg_threshold,
                rembg_erode_size=rembg_erode_size,
                rembg_base_size=rembg_base_size,
                shape=shape,
                circle_radius=circle_radius,
                circle_center_x=circle_center_x,
                circle_center_y=circle_center_y,
                circle_auto_center=circle_auto_center,
            )
            
            processing_time = time.time() - start_time
            
            print(f"[MODAL] Overlay processing completed in {processing_time:.1f}s")
            
            return {
                "overlay_url": overlay_url,
                "processing_time": processing_time,
                "status": "success",
            }
            
    except Exception as exc:
        processing_time = time.time() - start_time
        error_msg = str(exc)
        print(f"[MODAL] ERROR: {error_msg}")
        
        return {
            "status": "failed",
            "error": error_msg,
            "processing_time": processing_time,
        }


# Web endpoint for job submission
@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def submit(data: dict):
    """
    Submit overlay processing job.
    
    POST /submit
    Body: {
        "video_url": "https://...",
        "container": "mov",
        "engine": "mediapipe",
        "shape": "circle",
        ...
    }
    
    Returns:
        {"job_id": "call_xyz123...", "status": "submitted"}
    """
    print(f"[MODAL] Received job submission: engine={data.get('engine')}, shape={data.get('shape')}")
    
    # Start async processing
    call = process_overlay.spawn(**data)
    
    return {
        "job_id": call.object_id,
        "status": "submitted",
    }


@app.function(image=image)
@modal.fastapi_endpoint(method="GET")
def status(job_id: str):
    """
    Check job status.
    
    GET /status?job_id=call_xyz123
    
    Returns:
        {"status": "processing|completed|failed", "job_id": "..."}
    """
    from modal.functions import FunctionCall
    
    try:
        call = FunctionCall.from_id(job_id)
        
        try:
            # Try to get result without waiting
            result = call.get(timeout=0)
            
            if result.get("status") == "failed":
                return {
                    "status": "failed",
                    "job_id": job_id,
                    "error": result.get("error"),
                }
            else:
                return {
                    "status": "completed",
                    "job_id": job_id,
                }
                
        except TimeoutError:
            # Still processing
            return {
                "status": "processing",
                "job_id": job_id,
            }
            
    except Exception as exc:
        return {
            "status": "error",
            "job_id": job_id,
            "error": str(exc),
        }


@app.function(image=image)
@modal.fastapi_endpoint(method="GET")
def result(job_id: str):
    """
    Get job result.
    
    GET /result?job_id=call_xyz123
    
    Returns:
        {
            "status": "completed|failed|processing",
            "job_id": "...",
            "overlay_url": "...",  # if completed
            "processing_time": 45.2,  # if completed
            "error": "..."  # if failed
        }
    """
    from modal.functions import FunctionCall
    
    try:
        call = FunctionCall.from_id(job_id)
        
        try:
            # Try to get result without waiting
            result = call.get(timeout=0)
            
            return {
                "status": result.get("status", "completed"),
                "job_id": job_id,
                **result,
            }
            
        except TimeoutError:
            # Still processing
            return {
                "status": "processing",
                "job_id": job_id,
            }
            
    except Exception as exc:
        return {
            "status": "error",
            "job_id": job_id,
            "error": str(exc),
        }

