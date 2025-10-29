"""
Modal GPU service client for video overlay processing.
Handles async job submission and polling for Railway integration.
"""
import time
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class ModalOverlayClient:
    """Client for Modal GPU overlay processing service with async polling."""
    
    def __init__(self, base_url: str, poll_interval: int = 5, timeout: int = 600):
        """
        Initialize Modal client.
        
        Args:
            base_url: Base URL of Modal endpoints (e.g., https://user--app-submit.modal.run)
            poll_interval: How often to poll for status (seconds)
            timeout: Max time to wait for job completion (seconds)
        """
        self.base_url = base_url.rstrip('/')
        self.poll_interval = poll_interval
        self.timeout = timeout
        
        # Derive status and result URLs from submit URL
        # https://user--app-submit.modal.run -> https://user--app-status.modal.run
        if '--' in self.base_url and '-submit' in self.base_url:
            base = self.base_url.rsplit('-submit', 1)[0]
            self.status_url = f"{base}-status.modal.run"
            self.result_url = f"{base}-result.modal.run"
        else:
            # Fallback: assume same domain
            self.status_url = self.base_url.replace('submit', 'status')
            self.result_url = self.base_url.replace('submit', 'result')
    
    def submit_overlay_job(
        self,
        video_url: str,
        container: str = "mov",
        engine: str = "mediapipe",
        shape: str = "circle",
        **kwargs
    ) -> str:
        """
        Submit overlay processing job to Modal.
        
        Args:
            video_url: URL of source video
            container: "mov" or "webm"
            engine: "mediapipe" or "rembg"
            shape: "rect" or "circle"
            **kwargs: Additional parameters for prepare_overlay
            
        Returns:
            str: Job ID for polling
            
        Raises:
            Exception: If submission fails
        """
        payload = {
            "video_url": video_url,
            "container": container,
            "engine": engine,
            "shape": shape,
            **kwargs
        }
        
        logger.info(f"[MODAL] 🚀 Submitting job to GPU: engine={engine}, shape={shape}")
        
        try:
            response = requests.post(
                self.base_url,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            
            job_id = result.get("job_id")
            if not job_id:
                raise Exception(f"No job_id in response: {result}")
            
            logger.info(f"[MODAL] ✅ Job submitted: {job_id}")
            return job_id
            
        except requests.RequestException as exc:
            logger.error(f"[MODAL] ❌ Submission failed: {exc}")
            raise Exception(f"Failed to submit Modal job: {exc}")
    
    def poll_job_status(self, job_id: str) -> dict:
        """
        Check job status.
        
        Args:
            job_id: Job ID from submit
            
        Returns:
            dict: {"status": "processing|completed|failed", "job_id": "...", ...}
        """
        try:
            response = requests.get(
                self.status_url,
                params={"job_id": job_id},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as exc:
            logger.error(f"[MODAL] ❌ Status check failed: {exc}")
            return {"status": "error", "error": str(exc)}
    
    def get_job_result(self, job_id: str) -> dict:
        """
        Get job result.
        
        Args:
            job_id: Job ID from submit
            
        Returns:
            dict: Full result with overlay_url, processing_time, etc.
        """
        try:
            response = requests.get(
                self.result_url,
                params={"job_id": job_id},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as exc:
            logger.error(f"[MODAL] ❌ Result fetch failed: {exc}")
            raise Exception(f"Failed to get Modal result: {exc}")
    
    def process_overlay_async(
        self,
        video_url: str,
        container: str = "mov",
        engine: str = "mediapipe",
        shape: str = "circle",
        **kwargs
    ) -> str:
        """
        Full async cycle: submit -> poll until completed -> get result.
        
        Args:
            video_url: URL of source video
            container: "mov" or "webm"
            engine: "mediapipe" or "rembg"
            shape: "rect" or "circle"
            **kwargs: Additional parameters
            
        Returns:
            str: URL of ready overlay on Shotstack
            
        Raises:
            Exception: If processing fails or timeout
        """
        # Submit job
        job_id = self.submit_overlay_job(video_url, container, engine, shape, **kwargs)
        
        # Poll until completed
        start_time = time.time()
        last_log_time = start_time
        
        while True:
            elapsed = time.time() - start_time
            
            # Check timeout
            if elapsed > self.timeout:
                logger.error(f"[MODAL] ❌ Timeout after {elapsed:.0f}s")
                raise TimeoutError(f"Modal processing timeout after {self.timeout}s")
            
            # Poll status
            status_response = self.poll_job_status(job_id)
            status = status_response.get("status")
            
            # Log progress every 10 seconds
            if time.time() - last_log_time >= 10:
                logger.info(f"[MODAL] 📊 Status: {status} (elapsed: {elapsed:.0f}s)")
                last_log_time = time.time()
            
            # Handle status
            if status == "completed":
                # Get result
                result = self.get_job_result(job_id)
                
                overlay_url = result.get("overlay_url")
                processing_time = result.get("processing_time", elapsed)
                
                if not overlay_url:
                    raise Exception(f"No overlay_url in result: {result}")
                
                logger.info(f"[MODAL] ✅ Completed in {processing_time:.1f}s")
                logger.info(f"[MODAL] 🔗 Overlay URL: {overlay_url}")
                
                return overlay_url
                
            elif status == "failed":
                error = status_response.get("error", "Unknown error")
                logger.error(f"[MODAL] ❌ Job failed: {error}")
                raise Exception(f"Modal processing failed: {error}")
                
            elif status == "error":
                error = status_response.get("error", "Unknown error")
                logger.error(f"[MODAL] ❌ Status check error: {error}")
                raise Exception(f"Modal status check error: {error}")
            
            # Still processing, wait before next poll
            time.sleep(self.poll_interval)

