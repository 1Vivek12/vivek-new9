"""Timed text subtitle and caption track generation (SRT & WebVTT)."""

from typing import Any, Dict, List


class SubtitleValidationError(ValueError):
    """Raised when subtitle segments contain invalid or overlapping timestamps."""

    pass


def format_timestamp_srt(seconds: float) -> str:
    """Format seconds into standard SRT timestamp: HH:MM:SS,mmm"""
    total_ms = int(round(seconds * 1000))
    hours = total_ms // (3600 * 1000)
    remainder = total_ms % (3600 * 1000)
    minutes = remainder // (60 * 1000)
    remainder %= 60 * 1000
    secs = remainder // 1000
    millis = remainder % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_timestamp_vtt(seconds: float) -> str:
    """Format seconds into standard WebVTT timestamp: HH:MM:SS.mmm"""
    total_ms = int(round(seconds * 1000))
    hours = total_ms // (3600 * 1000)
    remainder = total_ms % (3600 * 1000)
    minutes = remainder // (60 * 1000)
    remainder %= 60 * 1000
    secs = remainder // 1000
    millis = remainder % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def validate_segments(segments: List[Dict[str, Any]]) -> None:
    """Ensure segments have valid non-negative, non-inverted, monotonic timestamps."""
    last_end = 0.0
    for idx, seg in enumerate(segments, 1):
        raw_start = seg.get("start_time") if "start_time" in seg else seg.get("start", 0.0)
        raw_end = seg.get("end_time") if "end_time" in seg else seg.get("end", 0.0)
        start = float(raw_start or 0.0)
        end = float(raw_end or 0.0)
        text = str(seg.get("text", "")).strip()

        if start < 0 or end < 0:
            raise SubtitleValidationError(f"Segment {idx} has negative timestamp: {start} -> {end}")
        if end <= start:
            raise SubtitleValidationError(
                f"Segment {idx} has invalid duration (end <= start): {start} -> {end}"
            )
        if not text:
            raise SubtitleValidationError(f"Segment {idx} has empty text.")
        last_end = max(last_end, end)


def generate_srt(segments: List[Dict[str, Any]]) -> str:
    """Generate compliant SubRip (.srt) timed text content."""
    validate_segments(segments)
    lines: List[str] = []

    for idx, seg in enumerate(segments, 1):
        raw_start = seg.get("start_time") if "start_time" in seg else seg.get("start", 0.0)
        raw_end = seg.get("end_time") if "end_time" in seg else seg.get("end", 0.0)
        start_val = float(raw_start or 0.0)
        end_val = float(raw_end or 0.0)
        start_ts = format_timestamp_srt(start_val)
        end_ts = format_timestamp_srt(end_val)
        text = str(seg.get("text", "")).strip()
        speaker = seg.get("speaker_label") or seg.get("speaker")

        lines.append(str(idx))
        lines.append(f"{start_ts} --> {end_ts}")
        if speaker:
            lines.append(f"[{speaker}] {text}")
        else:
            lines.append(text)
        lines.append("")

    return "\n".join(lines).strip() + "\n" if lines else ""


def generate_vtt(segments: List[Dict[str, Any]]) -> str:
    """Generate compliant WebVTT (.vtt) timed text content."""
    validate_segments(segments)
    lines: List[str] = ["WEBVTT", ""]

    for idx, seg in enumerate(segments, 1):
        raw_start = seg.get("start_time") if "start_time" in seg else seg.get("start", 0.0)
        raw_end = seg.get("end_time") if "end_time" in seg else seg.get("end", 0.0)
        start_val = float(raw_start or 0.0)
        end_val = float(raw_end or 0.0)
        start_ts = format_timestamp_vtt(start_val)
        end_ts = format_timestamp_vtt(end_val)
        text = str(seg.get("text", "")).strip()
        speaker = seg.get("speaker_label") or seg.get("speaker")

        lines.append(str(idx))
        lines.append(f"{start_ts} --> {end_ts}")
        if speaker:
            lines.append(f"<v {speaker}>{text}")
        else:
            lines.append(text)
        lines.append("")

    return "\n".join(lines).strip() + "\n"
