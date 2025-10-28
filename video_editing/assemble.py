#!/usr/bin/env python3
"""
Render a Shotstack video from a simple montage specification.

Example:
    SHOTSTACK_API_KEY=... python assemble.py talking_head_overlay.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from html import escape
from typing import Any, Dict, List, Optional
from urllib import error, request


DEFAULT_STAGE = os.getenv("SHOTSTACK_STAGE", "stage")
DEFAULT_HOST = os.getenv("SHOTSTACK_API_HOST", "https://api.shotstack.io")
POLL_SECONDS = int(os.getenv("SHOTSTACK_POLL_SECONDS", "5"))
POLL_TIMEOUT = int(os.getenv("SHOTSTACK_POLL_TIMEOUT", "300"))


class ShotstackError(RuntimeError):
    """Raised when the Shotstack API returns an error response."""


def load_spec(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _is_video_clip(clip: Dict[str, Any]) -> bool:
    asset_type = clip.get("asset_type", clip.get("type", "video"))
    return asset_type == "video"


def _trim_seconds(clip: Dict[str, Any]) -> float:
    trim = clip.get("trim")
    if trim is None:
        return 0.0
    try:
        value = float(trim)
    except (TypeError, ValueError) as exc:
        raise ShotstackError(f"Invalid trim value for clip '{clip.get('src')}': {trim}") from exc
    return max(value, 0.0)


def _probe_duration(src: str) -> float:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        src,
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as exc:  # pragma: no cover - dependency guard
        raise ShotstackError("ffprobe binary is required but was not found on PATH.") from exc
    if result.returncode != 0:
        raise ShotstackError(f"ffprobe failed for {src}: {result.stderr.strip()}")
    output = result.stdout.strip()
    try:
        return float(output)
    except ValueError as exc:  # pragma: no cover - ffprobe guard
        raise ShotstackError(f"Unable to parse duration for {src}: {output}") from exc


def _collect_clips(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    clips: List[Dict[str, Any]] = []
    clips.extend(spec.get("clips", []))
    clips.extend(spec.get("overlays", []))
    return clips


def apply_automation(spec: Dict[str, Any]) -> None:
    clips = _collect_clips(spec)
    if not clips:
        return

    duration_cache: Dict[str, float] = {}
    label_index: Dict[str, Dict[str, Any]] = {}

    def resolve_duration(clip: Dict[str, Any]) -> Optional[float]:
        src = clip.get("src")
        if not src or not _is_video_clip(clip):
            return None
        cached = duration_cache.get(src)
        if cached is not None:
            return cached
        duration = _probe_duration(src)
        duration_cache[src] = duration
        return duration

    for clip in clips:
        label = clip.get("label")
        if label:
            label_index[label] = clip

    for clip in clips:
        duration = resolve_duration(clip)
        trim_seconds = _trim_seconds(clip)
        playable_duration = None
        if duration is not None:
            playable_duration = max(duration - trim_seconds, 0.0)
        clip["_source_duration"] = playable_duration
        if clip.get("auto_length") or clip.get("length") is None:
            if playable_duration is not None:
                clip["length"] = playable_duration

    for clip in clips:
        match_label = clip.get("match_length_to")
        if not match_label:
            continue
        target_clip = label_index.get(match_label)
        if not target_clip:
            raise ShotstackError(f"match_length_to references unknown label '{match_label}'")

        target_length = target_clip.get("length")
        if target_length is None:
            target_duration = target_clip.get("_source_duration")
            if target_duration is None:
                target_duration = resolve_duration(target_clip)
            if target_duration is None:
                raise ShotstackError(f"Unable to determine target length for label '{match_label}'")
            target_length = target_duration
            target_clip["length"] = target_length

        source_duration = clip.get("_source_duration")
        if source_duration is None:
            source_duration = resolve_duration(clip)
            if source_duration is not None:
                trim_seconds = _trim_seconds(clip)
                source_duration = max(source_duration - trim_seconds, 0.0)
        if source_duration is None or target_length is None or target_length <= 0:
            raise ShotstackError(f"Unable to compute speed for clip with src '{clip.get('src')}'")

        clip["speed"] = source_duration / target_length
        clip["length"] = target_length

    for clip in clips:
        clip.pop("_source_duration", None)


def build_video_clip(clip: Dict[str, Any]) -> Dict[str, Any]:
    asset_type = clip.get("asset_type", clip.get("type", "video"))
    asset: Dict[str, Any] = {"type": asset_type}

    if asset_type == "video":
        asset["src"] = clip["src"]
        if clip.get("trim") is not None:
            asset["trim"] = clip["trim"]
        if clip.get("volume") is not None:
            asset["volume"] = clip["volume"]
        if clip.get("speed") is not None:
            asset["speed"] = clip["speed"]
    elif asset_type == "image":
        asset["src"] = clip["src"]
    elif asset_type == "html":
        asset["html"] = clip["html"]
    elif asset_type == "title":
        asset["text"] = clip["text"]
        if clip.get("style"):
            asset["style"] = clip["style"]
        if clip.get("size"):
            asset["size"] = clip["size"]
    else:
        raise ValueError(f"Unsupported asset type: {asset_type}")

    shotstack_clip: Dict[str, Any] = {"asset": asset}

    if clip.get("start") is not None:
        shotstack_clip["start"] = clip["start"]
    if clip.get("length") is not None:
        shotstack_clip["length"] = clip["length"]

    optional_fields = ("fit", "position", "offset", "scale", "width", "height", "opacity")
    for field in optional_fields:
        if clip.get(field) is not None:
            shotstack_clip[field] = clip[field]

    transition = clip.get("transition")
    if transition:
        if isinstance(transition, dict):
            shotstack_clip["transition"] = transition
        else:
            shotstack_clip["transition"] = {"in": transition}
    if asset_type == "audio" and clip.get("volume") is not None:
        asset["volume"] = clip["volume"]

    return shotstack_clip


def build_overlay_clip(overlay: Dict[str, Any]) -> Dict[str, Any]:
    overlay_clip = build_video_clip(overlay)
    if overlay.get("opacity") is not None:
        overlay_clip["opacity"] = overlay["opacity"]
    return overlay_clip


def build_subtitle_clips(subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    clips: List[Dict[str, Any]] = []
    for index, entry in enumerate(subtitles):
        if not isinstance(entry, dict):
            raise ShotstackError(f"Subtitle entry at index {index} must be an object.")

        raw_text = entry.get("text")
        if not raw_text:
            continue

        try:
            start = float(entry.get("start", 0.0))
        except (TypeError, ValueError) as exc:
            raise ShotstackError(f"Subtitle entry {index} has invalid start value.") from exc

        if "length" in entry:
            try:
                length = float(entry["length"])
            except (TypeError, ValueError) as exc:
                raise ShotstackError(f"Subtitle entry {index} has invalid length.") from exc
        elif "end" in entry:
            try:
                end = float(entry["end"])
            except (TypeError, ValueError) as exc:
                raise ShotstackError(f"Subtitle entry {index} has invalid end value.") from exc
            length = max(end - start, 0.0)
        else:
            raise ShotstackError(f"Subtitle entry {index} must include 'length' or 'end'.")

        if length <= 0:
            continue

        sanitized = escape(str(raw_text)).replace("\n", "<br>")
        html_markup = (
            "<div style=\"font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-weight: 600; "
            "font-size: 48px; line-height: 1.3; color: #FFFFFF; background: rgba(0,0,0,0.75); "
            "padding: 18px 28px; border-radius: 24px; display: inline-block; "
            "max-width: 80vw; word-break: break-word; box-shadow: 0 16px 32px rgba(0,0,0,0.35);\">"
            f"{sanitized}</div>"
        )

        clip: Dict[str, Any] = {
            "type": "html",
            "start": start,
            "length": length,
            "html": html_markup,
            "position": entry.get("position", "bottom"),
            "offset": entry.get("offset", {"x": 0.0, "y": -0.26}),
        }

        clips.append(build_video_clip(clip))
    return clips


def build_timeline(spec: Dict[str, Any]) -> Dict[str, Any]:
    clips = [build_video_clip(clip) for clip in spec.get("clips", [])]
    primary_track = {"clips": clips} if clips else {}

    overlays = spec.get("overlays", [])
    overlay_track: Optional[Dict[str, Any]] = None
    if overlays:
        overlay_clips = [build_overlay_clip(overlay) for overlay in overlays]
        if overlay_clips:
            overlay_track = {"clips": overlay_clips}

    subtitle_entries = spec.get("subtitles", [])
    subtitle_track: Optional[Dict[str, Any]] = None
    if subtitle_entries:
        subtitle_clips = build_subtitle_clips(subtitle_entries)
        if subtitle_clips:
            subtitle_track = {"clips": subtitle_clips}

    tracks: List[Dict[str, Any]] = []
    if subtitle_track:
        tracks.append(subtitle_track)
    if overlay_track:
        tracks.append(overlay_track)
    if primary_track:
        tracks.append(primary_track)

    timeline: Dict[str, Any] = {"tracks": tracks}

    if spec.get("soundtrack"):
        soundtrack = spec["soundtrack"]
        timeline["soundtrack"] = {
            "src": soundtrack["src"],
            "effect": soundtrack.get("effect", "fadeInFadeOut"),
            "volume": soundtrack.get("volume", 1.0),
        }

    if spec.get("background"):
        timeline["background"] = spec["background"]

    return timeline


def build_output(spec: Dict[str, Any]) -> Dict[str, Any]:
    output_defaults = {
        "format": "mp4",
        "resolution": "1080",
        "aspectRatio": "16:9",
        "fps": 25,
    }
    output = spec.get("output", {})
    return {
        "format": output.get("format", output_defaults["format"]),
        "resolution": output.get("resolution", output_defaults["resolution"]),
        "aspectRatio": output.get("aspect_ratio", output_defaults["aspectRatio"]),
        "fps": output.get("fps", output_defaults["fps"]),
    }


def build_render_payload(spec: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "timeline": build_timeline(spec),
        "output": build_output(spec),
    }
    if spec.get("callback_url"):
        payload["callback"] = spec["callback_url"]
    return payload


def api_request(method: str, url: str, api_key: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    headers = {
        "x-api-key": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    data: Optional[bytes] = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = request.Request(url, data=data, headers=headers, method=method.upper())

    try:
        with request.urlopen(req) as response:
            payload = response.read().decode("utf-8")
            if not payload:
                return {}
            return json.loads(payload)
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise ShotstackError(f"Request failed {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise ShotstackError(f"Network error: {exc.reason}") from exc


def submit_render(payload: Dict[str, Any], api_key: str, host: str, stage: str) -> str:
    url = f"{host.rstrip('/')}/{stage}/render"
    response = api_request("POST", url, api_key, payload)
    try:
        return response["response"]["id"]
    except KeyError as exc:
        raise ShotstackError(f"Unexpected Shotstack response: {response}") from exc


def poll_render(render_id: str, api_key: str, host: str, stage: str, wait: bool = True) -> Dict[str, Any]:
    url = f"{host.rstrip('/')}/{stage}/render/{render_id}"
    started = time.time()

    while True:
        response = api_request("GET", url, api_key)
        status = response.get("response", {}).get("status")

        if status in {"done", "failed", "cancelled"} or not wait:
            return response

        if time.time() - started > POLL_TIMEOUT:
            raise ShotstackError("Timed out waiting for render to finish")

        time.sleep(POLL_SECONDS)


def extract_result(poll_response: Dict[str, Any]) -> Dict[str, Any]:
    response = poll_response.get("response", {})
    status = response.get("status")
    if status != "done":
        raise ShotstackError(f"Render did not complete successfully: {status}")
    return {
        "status": status,
        "id": response.get("id"),
        "url": response.get("url"),
        "poster": response.get("poster"),
        "thumbnail": response.get("thumbnail"),
        "duration": response.get("duration"),
        "render_time": response.get("renderTime"),
        "billable_seconds": response.get("billable"),
    }


def render_from_spec(path: str, wait: bool = True) -> Dict[str, Any]:
    api_key = os.getenv("SHOTSTACK_API_KEY")
    if not api_key:
        raise ShotstackError("Environment variable SHOTSTACK_API_KEY must be set.")

    host = os.getenv("SHOTSTACK_API_HOST", DEFAULT_HOST)
    stage = os.getenv("SHOTSTACK_STAGE", DEFAULT_STAGE)

    spec = load_spec(path)
    apply_automation(spec)
    payload = build_render_payload(spec)
    render_id = submit_render(payload, api_key, host, stage)

    poll_response = poll_render(render_id, api_key, host, stage, wait=wait)
    if wait:
        return extract_result(poll_response)
    return {
        "status": poll_response.get("response", {}).get("status"),
        "id": render_id,
        "poll_url": f"{host.rstrip('/')}/{stage}/render/{render_id}",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a montage using Shotstack.")
    parser.add_argument(
        "spec",
        help="Path to the montage JSON specification.",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Submit and return immediately without polling render status.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        result = render_from_spec(args.spec, wait=not args.no_wait)
    except ShotstackError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
