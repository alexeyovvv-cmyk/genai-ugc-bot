#!/usr/bin/env python3
"""
Generate an alpha-matted talking head video and upload it to Shotstack ingest.

Requires:
    - mediapipe
    - opencv-python
    - numpy
    - requests
    - ffmpeg binary on PATH

Usage:
    SHOTSTACK_API_KEY=... python prepare_overlay.py \
        --input-url https://drive.usercontent.google.com/... \
        --stage stage \
        --output talking_head_alpha.webm

The script will:
    1. Download the source clip.
    2. Run Mediapipe selfie segmentation to remove the background.
    3. Export a WebM (VP9 + alpha) preserving audio.
    4. Upload the file using Shotstack ingest signed URLs.
    5. Wait until the processed asset is publicly reachable and print the URL.
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

import cv2  # type: ignore
import mediapipe as mp  # type: ignore
import numpy as np
import requests
from PIL import Image  # type: ignore

try:
    from rembg import new_session, remove  # type: ignore
except ImportError:  # pragma: no cover - optional dependency for rembg engine
    new_session = None  # type: ignore
    remove = None  # type: ignore

# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(["ffmpeg", "-y", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.strip()}")


def download_file(url: str, dest: Path) -> None:
    start_time = time.time()
    downloaded_bytes = 0
    
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with open(dest, "wb") as handle:
            for chunk in response.iter_content(chunk_size=8192):
                handle.write(chunk)
                downloaded_bytes += len(chunk)
    
    duration = time.time() - start_time
    size_mb = downloaded_bytes / (1024 * 1024)
    logger.info(f"[PREPARE_OVERLAY] ⏱️ Downloaded {size_mb:.1f}MB in {duration:.2f}s")


def build_alpha_clip(
    source_path: Path,
    frames_dir: Path,
    audio_path: Path,
    alpha_video_path: Path,
    container: str,
    threshold: float,
    feather: int,
    debug: bool,
    engine: str,
    rembg_model: str,
    rembg_alpha_matting: bool,
    rembg_fg_threshold: int,
    rembg_bg_threshold: int,
    rembg_erode_size: int,
    rembg_base_size: int,
    shape: str,
    circle_radius: float,
    circle_center_x: float,
    circle_center_y: float,
    circle_auto_center: bool,
) -> float:
    cap = cv2.VideoCapture(str(source_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

    segmentation: Optional[mp.solutions.selfie_segmentation.SelfieSegmentation] = None
    rembg_session = None
    face_detection: Optional[mp.solutions.face_detection.FaceDetection] = None
    if engine == "mediapipe":
        segmentation = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=1)
    elif engine == "rembg":
        if new_session is None or remove is None:
            raise RuntimeError("rembg is not installed. Run `pip install rembg onnxruntime Pillow` to enable this engine.")
        rembg_session = new_session(model_name=rembg_model)
    else:
        raise ValueError(f"Unsupported engine: {engine}")

    if shape == "circle" and circle_auto_center:
        face_detection = mp.solutions.face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.5)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    feather = max(0, feather)
    if feather % 2 == 0 and feather != 0:
        feather += 1

    # Подсчет общего количества кадров
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    logger.info(f"[PREPARE_OVERLAY] 📊 Processing {total_frames} frames with {engine}")
    logger.info(f"[PREPARE_OVERLAY] 📊 Shape: {shape}, FPS: {fps:.1f}")
    if shape == "circle" and circle_auto_center:
        logger.info(f"[PREPARE_OVERLAY] 📊 Circle auto-centering: ENABLED")
    
    index = 0
    running_cx: Optional[float] = None
    running_cy: Optional[float] = None
    running_radius: Optional[float] = None
    coord_cache: Optional[Tuple[np.ndarray, np.ndarray]] = None
    last_progress_time = time.time()
    last_logged_percent = 0
    frame_start_time = time.time()
    
    while True:
        success, frame = cap.read()
        if not success:
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if engine == "mediapipe":
            assert segmentation is not None
            mask = segmentation.process(rgb).segmentation_mask.astype(np.float32)
        else:
            assert rembg_session is not None
            mask_image = remove(
                Image.fromarray(rgb),
                session=rembg_session,
                only_mask=True,
                alpha_matting=rembg_alpha_matting,
                alpha_matting_foreground_threshold=rembg_fg_threshold,
                alpha_matting_background_threshold=rembg_bg_threshold,
                alpha_matting_erode_structure_size=rembg_erode_size,
                alpha_matting_base_size=rembg_base_size,
            )
            mask = np.asarray(mask_image, dtype=np.float32) / 255.0

        mask = np.clip(mask, 0.0, 1.0)
        
        face_params: Optional[Tuple[float, float, float]] = None
        if face_detection is not None:
            detection_result = face_detection.process(rgb)
            if detection_result and detection_result.detections:
                bbox = detection_result.detections[0].location_data.relative_bounding_box
                x_min = max(0.0, bbox.xmin)
                y_min = max(0.0, bbox.ymin)
                box_width = max(0.0, bbox.width)
                box_height = max(0.0, bbox.height)
                if box_width > 0 and box_height > 0:
                    cx_face = (x_min + box_width * 0.5) * (w := mask.shape[1])
                    cy_face = (y_min + box_height * 0.5) * (h := mask.shape[0])
                    radius_face = max(box_width, box_height) * min(h, w) * (0.55 * 2.5)
                    face_params = (cx_face, cy_face, radius_face)

        weights = mask
        binary = (mask >= threshold).astype(np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

        refined_mask = mask * binary
        alpha_float = np.clip(refined_mask, 0.0, 1.0)
        if feather:
            alpha_float = cv2.GaussianBlur(alpha_float, (feather, feather), 0)
        if shape == "circle":
            h, w = alpha_float.shape
            min_dim = float(min(w, h))
            if circle_auto_center:
                if face_params is not None:
                    cx_frame, cy_frame, radius_px_frame = face_params
                else:
                    if coord_cache is None or coord_cache[0].shape != alpha_float.shape:
                        ys_coords, xs_coords = np.indices(alpha_float.shape, dtype=np.float32)
                        coord_cache = (ys_coords, xs_coords)
                    else:
                        ys_coords, xs_coords = coord_cache

                    total_weight = float(weights.sum())
                    if total_weight > 0.0:
                        cx_frame = float((weights * xs_coords).sum() / total_weight)
                        cy_frame = float((weights * ys_coords).sum() / total_weight)

                        mask_binary = weights > 0.25
                        if mask_binary.any():
                            cols = np.where(np.any(mask_binary, axis=0))[0]
                            rows = np.where(np.any(mask_binary, axis=1))[0]
                            if cols.size and rows.size:
                                width_span = float(cols[-1] - cols[0])
                                height_span = float(rows[-1] - rows[0])
                                radius_px_frame = min(width_span, height_span) * 0.5
                            else:
                                radius_px_frame = min_dim * max(circle_radius, 0.25)
                        else:
                            radius_px_frame = min_dim * max(circle_radius, 0.25)
                    else:
                        cx_frame = np.clip(circle_center_x, 0.0, 1.0) * (w - 1)
                        cy_frame = np.clip(circle_center_y, 0.0, 1.0) * (h - 1)
                        radius_px_frame = min_dim * max(circle_radius, 0.25)

                if running_cx is None:
                    running_cx = cx_frame
                    running_cy = cy_frame
                    running_radius = radius_px_frame
                else:
                    smooth = 0.2
                    running_cx = running_cx * (1 - smooth) + cx_frame * smooth
                    running_cy = running_cy * (1 - smooth) + cy_frame * smooth
                    running_radius = running_radius * (1 - smooth) + radius_px_frame * smooth

                cx = float(np.clip(running_cx, 0.0, w - 1))
                cy = float(np.clip(running_cy, 0.0, h - 1))
                radius = float(np.clip(running_radius, min_dim * 0.18, min_dim * 0.65))
            else:
                radius = max(0.0, min(1.0, circle_radius)) * min_dim
            cx = np.clip(circle_center_x, 0.0, 1.0) * (w - 1)
            cy = np.clip(circle_center_y, 0.0, 1.0) * (h - 1)

            yy, xx = np.ogrid[:h, :w]
            circle_mask = ((xx - cx) ** 2 + (yy - cy) ** 2) <= radius ** 2
            alpha_float = alpha_float * circle_mask.astype(np.float32)

        alpha = np.clip(alpha_float * 255.0, 0, 255).astype(np.uint8)

        if debug and index == 0:
            print("Mask stats min/max/mean:", float(mask.min()), float(mask.max()), float(mask.mean()))
            print("Foreground coverage:", float((alpha > 0).mean()))

        foreground = (frame.astype(np.float32) * alpha_float[..., None]).astype(np.uint8)
        foreground_bgra = cv2.cvtColor(foreground, cv2.COLOR_BGR2BGRA)
        foreground_bgra[:, :, 3] = alpha

        out_path = frames_dir / f"frame_{index:04d}.png"
        cv2.imwrite(str(out_path), foreground_bgra)
        index += 1
        
        # Логирование прогресса каждые 10%
        if total_frames > 0:
            progress_percent = int((index / total_frames) * 100)
            # Логируем каждые 10% или раз в 5 секунд
            current_time = time.time()
            if (progress_percent >= last_logged_percent + 10 or 
                current_time - last_progress_time >= 5):
                elapsed = current_time - frame_start_time
                fps_actual = index / elapsed if elapsed > 0 else 0
                eta_seconds = (total_frames - index) / fps_actual if fps_actual > 0 else 0
                logger.info(f"[PREPARE_OVERLAY] 📊 Progress: {progress_percent}% ({index}/{total_frames} frames, {fps_actual:.1f} fps, ETA: {eta_seconds:.0f}s)")
                last_logged_percent = progress_percent
                last_progress_time = current_time

    if segmentation is not None:
        segmentation.close()
    if face_detection is not None:
        face_detection.close()
    cap.release()

    if index == 0:
        raise RuntimeError("No frames extracted from source video.")
    
    frames_duration = time.time() - frame_start_time
    logger.info(f"[PREPARE_OVERLAY] ⏱️ Processed {index} frames in {frames_duration:.2f}s ({index/frames_duration:.1f} fps)")

    # Extract audio using ffmpeg (copy codec if possible)
    logger.info(f"[PREPARE_OVERLAY] ▶️ Extracting audio")
    audio_start = time.time()
    run_ffmpeg(["-i", str(source_path), "-vn", "-acodec", "copy", str(audio_path)])
    logger.info(f"[PREPARE_OVERLAY] ⏱️ Audio extracted in {time.time() - audio_start:.2f}s")

    frame_pattern = str(frames_dir / "frame_%04d.png")
    logger.info(f"[PREPARE_OVERLAY] ▶️ Encoding alpha video ({container})")
    encode_start = time.time()
    
    if container == "webm":
        encode_args = [
            "-framerate",
            f"{fps}",
            "-i",
            frame_pattern,
            "-i",
            str(audio_path),
            "-c:v",
            "libvpx-vp9",
            "-pix_fmt",
            "yuva420p",
            "-auto-alt-ref",
            "0",
            "-c:a",
            "libopus",
            "-b:a",
            "128k",
            str(alpha_video_path),
        ]
    else:
        encode_args = [
            "-framerate",
            f"{fps}",
            "-i",
            frame_pattern,
            "-i",
            str(audio_path),
            "-c:v",
            "prores_ks",
            "-profile:v",
            "4444",
            "-pix_fmt",
            "yuva444p10le",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(alpha_video_path),
        ]

    run_ffmpeg(encode_args)
    
    encode_duration = time.time() - encode_start
    logger.info(f"[PREPARE_OVERLAY] ⏱️ Video encoded in {encode_duration:.2f}s")
    
    output_size = alpha_video_path.stat().st_size
    size_mb = output_size / (1024 * 1024)
    logger.info(f"[PREPARE_OVERLAY] 📊 Output size: {size_mb:.1f}MB")

    duration = index / fps
    return duration


def request_signed_upload(api_key: str, stage: str) -> Tuple[str, str]:
    start_time = time.time()
    logger.info(f"[PREPARE_OVERLAY] ▶️ Requesting Shotstack signed upload URL")
    
    url = f"https://api.shotstack.io/ingest/{stage}/upload"
    response = requests.post(url, headers={"x-api-key": api_key}, timeout=30)
    response.raise_for_status()
    data = response.json()["data"]
    
    logger.info(f"[PREPARE_OVERLAY] ⏱️ Got signed URL in {time.time() - start_time:.2f}s")
    return data["id"], data["attributes"]["url"]


def upload_to_signed_url(file_path: Path, signed_url: str) -> None:
    start_time = time.time()
    file_size = file_path.stat().st_size
    size_mb = file_size / (1024 * 1024)
    
    logger.info(f"[PREPARE_OVERLAY] ▶️ Uploading {size_mb:.1f}MB to Shotstack")
    
    with open(file_path, "rb") as handle:
        resp = requests.put(signed_url, data=handle, timeout=300)
    resp.raise_for_status()
    
    duration = time.time() - start_time
    logger.info(f"[PREPARE_OVERLAY] ⏱️ Uploaded in {duration:.2f}s ({size_mb/duration:.1f}MB/s)")


def derive_public_url(signed_url: str, extension: str) -> Tuple[str, str]:
    parsed = urlparse(signed_url)
    segments = parsed.path.strip("/").split("/")
    if len(segments) < 3:
        raise ValueError(f"Unexpected signed URL structure: {signed_url}")
    owner_id, upload_id = segments[0], segments[1]
    base = f"{parsed.scheme}://{parsed.netloc}/{owner_id}/{upload_id}"
    return owner_id, f"{base}/source{extension}"


def wait_for_asset(url: str, timeout: int = 300, delay: float = 5.0) -> None:
    logger.info(f"[PREPARE_OVERLAY] ▶️ Waiting for Shotstack to process asset")
    start_time = time.time()
    elapsed = 0.0
    check_count = 0
    
    while elapsed < timeout:
        try:
            response = requests.head(url, timeout=10)
            if response.status_code == 200:
                logger.info(f"[PREPARE_OVERLAY] ⏱️ Asset ready in {elapsed:.2f}s (after {check_count} checks)")
                return
        except requests.RequestException:
            pass
        time.sleep(delay)
        elapsed += delay
        check_count += 1
        
        # Логируем каждые 30 секунд
        if int(elapsed) % 30 == 0 and elapsed > 0:
            logger.info(f"[PREPARE_OVERLAY] 📊 Still waiting... ({elapsed:.0f}s elapsed)")
    
    raise TimeoutError(f"Asset was not accessible within {timeout} seconds: {url}")


def prepare_overlay(
    input_url: str,
    output_path: Path,
    stage: str,
    api_key: str,
    container: str,
    threshold: float,
    feather: int,
    debug: bool,
    engine: str,
    rembg_model: str,
    rembg_alpha_matting: bool,
    rembg_fg_threshold: int,
    rembg_bg_threshold: int,
    rembg_erode_size: int,
    rembg_base_size: int,
    shape: str,
    circle_radius: float,
    circle_center_x: float,
    circle_center_y: float,
    circle_auto_center: bool = True,
) -> str:
    overall_start = time.time()
    logger.info(f"[PREPARE_OVERLAY] ▶️ Starting overlay preparation")
    logger.info(f"[PREPARE_OVERLAY] 📊 Engine: {engine}, Shape: {shape}, Container: {container}")
    
    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        source_path = tmpdir / "input.mp4"
        frames_dir = tmpdir / "frames"
        frames_dir.mkdir()
        audio_path = tmpdir / "audio.m4a"

        logger.info(f"[PREPARE_OVERLAY] ▶️ Downloading source clip")
        download_start = time.time()
        download_file(input_url, source_path)
        logger.info(f"[PREPARE_OVERLAY] ⏱️ Download completed in {time.time() - download_start:.2f}s")

        logger.info(f"[PREPARE_OVERLAY] ▶️ Building alpha-matted clip")
        alpha_start = time.time()
        duration = build_alpha_clip(
            source_path,
            frames_dir,
            audio_path,
            output_path,
            container,
            threshold,
            feather,
            debug,
            engine,
            rembg_model,
            rembg_alpha_matting,
            rembg_fg_threshold,
            rembg_bg_threshold,
            rembg_erode_size,
            rembg_base_size,
            shape,
            circle_radius,
            circle_center_x,
            circle_center_y,
            circle_auto_center,
        )
        alpha_duration = time.time() - alpha_start
        logger.info(f"[PREPARE_OVERLAY] ⏱️ Alpha clip built in {alpha_duration:.2f}s")
        
        extension = output_path.suffix or (".webm" if container == "webm" else ".mov")

        upload_id, signed_url = request_signed_upload(api_key, stage)
        logger.info(f"[PREPARE_OVERLAY] 📊 Upload ID: {upload_id}")

        upload_to_signed_url(output_path, signed_url)

        logger.info(f"[PREPARE_OVERLAY] ▶️ Deriving public asset URL")
        _, public_url = derive_public_url(signed_url, extension)

        wait_for_asset(public_url)

        overall_duration = time.time() - overall_start
        minutes = int(overall_duration // 60)
        seconds = overall_duration % 60
        
        if overall_duration > 60:
            logger.info(f"[PREPARE_OVERLAY] ⏱️ Total overlay generation: {overall_duration:.2f}s ({minutes}m {seconds:.1f}s) ⚠️")
        else:
            logger.info(f"[PREPARE_OVERLAY] ⏱️ Total overlay generation: {overall_duration:.2f}s")
        
        logger.info(f"[PREPARE_OVERLAY] ✅ Overlay ready at {public_url} (duration {duration:.2f}s)")
        return public_url


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a talking-head overlay with alpha and upload to Shotstack.")
    parser.add_argument("--input-url", required=True, help="Public URL to the source talking-head video.")
    parser.add_argument(
        "--output",
        default="talking_head_alpha.webm",
        help="Path to save the alpha clip (extension determines container).",
    )
    parser.add_argument(
        "--container",
        choices=["webm", "mov"],
        default=os.getenv("OVERLAY_CONTAINER", "mov"),
        help="Output container/codec for the alpha clip (default: mov/prores).",
    )
    parser.add_argument(
        "--engine",
        choices=["mediapipe", "rembg"],
        default=os.getenv("OVERLAY_ENGINE", "mediapipe"),
        help="Background removal engine to use (default: mediapipe).",
    )
    parser.add_argument(
        "--stage",
        choices=["stage", "production"],
        default=os.getenv("SHOTSTACK_STAGE", "stage"),
        help="Shotstack environment stage (default: stage).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=float(os.getenv("OVERLAY_THRESHOLD", "0.6")),
        help="Segmentation threshold between 0 and 1 (higher removes more background, default: 0.6).",
    )
    parser.add_argument(
        "--feather",
        type=int,
        default=int(os.getenv("OVERLAY_FEATHER", "7")),
        help="Gaussian blur kernel size for alpha edges (odd number, default: 7, 0 disables).",
    )
    parser.add_argument(
        "--debug-mask",
        action="store_true",
        help="Print debug statistics for the first frame mask.",
    )
    parser.add_argument(
        "--rembg-model",
        default=os.getenv("REMBG_MODEL", "u2netp"),
        help="Rembg model name (default: u2netp).",
    )
    parser.add_argument(
        "--rembg-alpha-matting",
        action="store_true",
        help="Enable rembg alpha matting refinement.",
    )
    parser.add_argument(
        "--rembg-fg-threshold",
        type=int,
        default=int(os.getenv("REMBG_FG_THRESHOLD", "240")),
        help="Rembg alpha matting foreground threshold (default: 240).",
    )
    parser.add_argument(
        "--rembg-bg-threshold",
        type=int,
        default=int(os.getenv("REMBG_BG_THRESHOLD", "10")),
        help="Rembg alpha matting background threshold (default: 10).",
    )
    parser.add_argument(
        "--rembg-erode-size",
        type=int,
        default=int(os.getenv("REMBG_ERODE_SIZE", "10")),
        help="Rembg alpha matting erode structure size (default: 10).",
    )
    parser.add_argument(
        "--rembg-base-size",
        type=int,
        default=int(os.getenv("REMBG_BASE_SIZE", "1000")),
        help="Rembg alpha matting base size (default: 1000).",
    )
    parser.add_argument(
        "--shape",
        choices=["rect", "circle"],
        default=os.getenv("OVERLAY_SHAPE", "rect"),
        help="Final overlay shape: rectangle (по умолчанию) или круг (circle).",
    )
    parser.add_argument(
        "--circle-radius",
        type=float,
        default=float(os.getenv("OVERLAY_CIRCLE_RADIUS", "0.35")),
        help="Относительный радиус круга (0-1) при shape=circle (default: 0.35).",
    )
    parser.add_argument(
        "--circle-center-x",
        type=float,
        default=float(os.getenv("OVERLAY_CIRCLE_CENTER_X", "0.5")),
        help="Горизонтальный центр круга (0-1, доля ширины, default: 0.5).",
    )
    parser.add_argument(
        "--circle-center-y",
        type=float,
        default=float(os.getenv("OVERLAY_CIRCLE_CENTER_Y", "0.5")),
        help="Вертикальный центр круга (0-1, доля высоты, default: 0.5).",
    )
    parser.add_argument(
        "--no-circle-auto-center",
        action="store_false",
        dest="circle_auto_center",
        help="Отключить автоматическое определение центра круга по маске (по умолчанию включено).",
    )
    parser.set_defaults(circle_auto_center=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    api_key = os.getenv("SHOTSTACK_API_KEY")
    if not api_key:
        print("Environment variable SHOTSTACK_API_KEY is required.", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output).resolve()

    container = args.container
    if output_path.suffix.lower() in {".mov", ".qt"}:
        container = "mov"
    elif output_path.suffix.lower() == ".webm":
        container = "webm"

    try:
        public_url = prepare_overlay(
            args.input_url,
            output_path,
            args.stage,
            api_key,
            container,
            threshold=max(0.0, min(1.0, args.threshold)),
            feather=args.feather,
            debug=args.debug_mask,
            engine=args.engine,
            rembg_model=args.rembg_model,
            rembg_alpha_matting=args.rembg_alpha_matting,
            rembg_fg_threshold=args.rembg_fg_threshold,
            rembg_bg_threshold=args.rembg_bg_threshold,
            rembg_erode_size=args.rembg_erode_size,
            rembg_base_size=args.rembg_base_size,
            shape=args.shape,
            circle_radius=args.circle_radius,
            circle_center_x=args.circle_center_x,
            circle_center_y=args.circle_center_y,
            circle_auto_center=args.circle_auto_center,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print("\nUse this URL in your Shotstack JSON spec:")
    print(public_url)


if __name__ == "__main__":
    main()
