from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type


def read_transcript(
    transcript_arg: Optional[str],
    transcript_file_arg: Optional[str],
    *,
    error_cls: Type[Exception] = RuntimeError,
) -> Optional[str]:
    """Read transcript from argument or file."""
    if transcript_file_arg:
        try:
            return Path(transcript_file_arg).read_text(encoding="utf-8")
        except OSError as exc:
            raise error_cls(f"Не удалось прочитать файл транскрипта {transcript_file_arg}: {exc}") from exc
    if transcript_arg:
        return transcript_arg
    return None


def load_subtitles(
    path: str,
    *,
    error_cls: Type[Exception] = RuntimeError,
) -> List[Dict[str, object]]:
    """Load subtitles from JSON file."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise error_cls(f"Не удалось прочитать субтитры из {path}: {exc}") from exc

    if isinstance(data, dict):
        if "subtitles" in data:
            data = data["subtitles"]
        elif "cues" in data:
            data = data["cues"]

    if not isinstance(data, list):
        raise error_cls("Файл субтитров должен содержать массив объектов.")

    subtitles: List[Dict[str, object]] = []
    for index, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise error_cls(f"Субтитр #{index} должен быть объектом.")

        text = str(entry.get("text", "")).strip()
        if not text:
            continue

        try:
            start = float(entry.get("start", 0.0))
        except (TypeError, ValueError) as exc:
            raise error_cls(f"Субтитр #{index} имеет некорректное поле start.") from exc

        if "length" in entry:
            try:
                length = float(entry["length"])
            except (TypeError, ValueError) as exc:
                raise error_cls(f"Субтитр #{index} имеет некорректное поле length.") from exc
        elif "end" in entry:
            try:
                end = float(entry["end"])
            except (TypeError, ValueError) as exc:
                raise error_cls(f"Субтитр #{index} имеет некорректное поле end.") from exc
            length = max(end - start, 0.0)
        else:
            raise error_cls(f"Субтитр #{index} должен содержать length или end.")

        if length <= 0:
            continue

        subtitle: Dict[str, object] = {
            "text": text,
            "start": start,
            "length": length,
        }

        if entry.get("position"):
            subtitle["position"] = entry["position"]
        if entry.get("offset"):
            subtitle["offset"] = entry["offset"]
        if entry.get("width"):
            subtitle["width"] = entry["width"]

        subtitles.append(subtitle)

    return subtitles


def detect_speech_segments(
    media_path: Path,
    duration: float,
    *,
    error_cls: Type[Exception] = RuntimeError,
    silence_db: float = -35.0,
    min_silence_duration: float = 0.35,
    min_segment_duration: float = 0.3,
) -> List[Tuple[float, float]]:
    """Detect speech segments using ffmpeg silencedetect."""
    command = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(media_path),
        "-af",
        f"silencedetect=noise={silence_db}dB:d={min_silence_duration}",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise error_cls(f"ffmpeg silencedetect failed: {result.stderr.strip()}")

    current_start = 0.0
    speech_segments: List[Tuple[float, float]] = []

    for line in result.stderr.splitlines():
        line = line.strip()
        if "silence_start" in line:
            try:
                silence_start = float(line.split("silence_start:")[1].split()[0])
            except (IndexError, ValueError):
                continue
            segment_duration = silence_start - current_start
            if segment_duration >= min_segment_duration:
                speech_segments.append((current_start, segment_duration))
            current_start = silence_start
        elif "silence_end" in line:
            try:
                silence_end = float(line.split("silence_end:")[1].split()[0])
            except (IndexError, ValueError):
                continue
            current_start = silence_end

    if duration > current_start:
        tail_duration = duration - current_start
        if tail_duration >= min_segment_duration:
            speech_segments.append((current_start, tail_duration))

    if not speech_segments and duration > 0:
        speech_segments = [(0.0, duration)]

    return speech_segments


def sentence_tokenize(text: str) -> List[str]:
    """Tokenize text into sentences."""
    stripped = text.strip()
    if not stripped:
        return []
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", stripped) if part.strip()]
    if parts:
        return parts
    words = stripped.split()
    chunk_size = 10
    return [" ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size)]


def align_transcript_to_segments(
    transcript: str,
    segments: List[Tuple[float, float]],
    total_duration: float,
) -> List[Dict[str, object]]:
    """Align transcript text to detected speech segments."""
    sentences = sentence_tokenize(transcript)
    if not sentences:
        return []

    if not segments:
        segments = [(0.0, total_duration)]

    total_segments_duration = sum(duration for _, duration in segments)
    if total_segments_duration <= 0:
        total_segments_duration = total_duration or 1.0

    allocations: List[List[str]] = []
    sentence_index = 0
    cumulative = 0.0
    num_sentences = len(sentences)

    for seg_index, (_, duration) in enumerate(segments):
        if seg_index == len(segments) - 1:
            next_index = num_sentences
        else:
            portion = duration / total_segments_duration
            cumulative += portion * num_sentences
            next_index = max(sentence_index + 1, int(round(cumulative)))
            next_index = min(next_index, num_sentences)
        allocations.append(sentences[sentence_index:next_index])
        sentence_index = next_index

    subtitles: List[Dict[str, object]] = []
    for (seg_start, seg_duration), texts in zip(segments, allocations):
        if not texts:
            continue
        text = " ".join(texts).strip()
        if not text:
            continue
        length = max(seg_duration - min(0.15, seg_duration * 0.1), 0.4)
        length = min(length, max(seg_duration - 0.05, 0.2))
        start = max(seg_start + 0.05, 0.0)
        subtitles.append(
            {
                "start": round(start, 3),
                "length": round(length, 3),
                "text": text,
            }
        )

    return subtitles

