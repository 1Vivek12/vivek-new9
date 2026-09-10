"""Tests verifying the architectural boundary between Real Media Processing and Mock Fallbacks.

MANDATE:
Production processing must distinguish between:
- REAL_RUNTIME_PROCESSING
- CONTRACT/MOCK_PROCESSING
- TOOL_UNAVAILABLE
- FAILED

If FFmpeg, FFprobe, Whisper, or OCR is unavailable:
- Real production services MUST NOT silently mark the asset/job as COMPLETED with fake data.
- It MUST raise ToolUnavailableError or mark the job as TOOL_UNAVAILABLE / FAILED.
- Test-only mocks (MockMediaProcessor, MockTranscriptionProvider, etc.) are isolated fixtures.
"""

import pytest

from app.services.media.ocr import LocalOCRProvider, MockOCRProvider
from app.services.media.processor import (
    FFmpegMediaProcessor,
    MockMediaProcessor,
    ToolUnavailableError,
)
from app.services.media.scenes import FFmpegSceneDetector, MockSceneDetector
from app.services.media.transcription import (
    LocalWhisperProvider,
    MockTranscriptionProvider,
)


@pytest.mark.asyncio
async def test_real_ffmpeg_processor_raises_tool_unavailable_when_missing():
    """Verify that when ffmpeg/ffprobe binary path is non-existent,
    FFmpegMediaProcessor raises ToolUnavailableError.
    """
    # Pass an explicitly non-existent binary path
    processor = FFmpegMediaProcessor(
        ffmpeg_path="nonexistent_ffmpeg_bin_12345",
        ffprobe_path="nonexistent_ffprobe_bin_12345",
    )

    assert not processor.is_available()

    with pytest.raises(ToolUnavailableError, match="FFmpeg/FFprobe binaries"):
        await processor.extract_metadata("/tmp/fake.mp4")

    with pytest.raises(ToolUnavailableError, match="FFmpeg/FFprobe binaries"):
        await processor.extract_audio("/tmp/fake.mp4", "/tmp/out.wav")

    with pytest.raises(ToolUnavailableError, match="FFmpeg/FFprobe binaries"):
        await processor.generate_derivative("/tmp/fake.mp4", "/tmp/out_v.mp4", "VERTICAL_9_16")


@pytest.mark.asyncio
async def test_real_whisper_provider_raises_tool_unavailable_when_missing(monkeypatch):
    """Verify that when whisper is missing, LocalWhisperProvider raises ToolUnavailableError
    and does NOT fake transcripts.
    """
    provider = LocalWhisperProvider()
    monkeypatch.setattr(provider, "is_available", lambda: False)
    assert not provider.is_available()

    with pytest.raises(ToolUnavailableError, match="Whisper transcription engine is not installed"):
        await provider.transcribe("/tmp/fake.mp4")


@pytest.mark.asyncio
async def test_real_scene_detector_raises_tool_unavailable_when_missing():
    """Verify that when ffmpeg is missing, FFmpegSceneDetector raises ToolUnavailableError."""
    unavailable_processor = FFmpegMediaProcessor(
        ffmpeg_path="nonexistent_ffmpeg_bin_12345",
        ffprobe_path="nonexistent_ffprobe_bin_12345",
    )
    detector = FFmpegSceneDetector(media_processor=unavailable_processor)
    assert not detector.is_available()

    with pytest.raises(ToolUnavailableError, match="FFmpeg is not installed"):
        await detector.detect_scenes("/tmp/fake.mp4", "/tmp/scenes", 10.0)


@pytest.mark.asyncio
async def test_real_ocr_provider_raises_tool_unavailable_when_missing(monkeypatch):
    """Verify that when tesseract is missing, LocalOCRProvider raises ToolUnavailableError."""
    provider = LocalOCRProvider()
    monkeypatch.setattr(provider, "is_available", lambda: False)
    assert not provider.is_available()

    with pytest.raises(ToolUnavailableError, match="Tesseract OCR binary is not installed"):
        await provider.extract_text("/tmp/fake_frame.jpg")


@pytest.mark.asyncio
async def test_mock_providers_operate_in_test_environment():
    """Verify that mock providers operate deterministically when intentionally used in tests."""
    mock_processor = MockMediaProcessor()
    assert mock_processor.is_available()
    meta = await mock_processor.extract_metadata("/fake/path.mp4")
    assert meta["duration"] > 0
    assert meta["codec"] == "h264"

    mock_whisper = MockTranscriptionProvider()
    assert mock_whisper.is_available()
    tx_res = await mock_whisper.transcribe("/fake/path.mp4")
    assert "segments" in tx_res
    segments = tx_res["segments"]
    assert len(segments) > 0
    assert "start_time" in segments[0] and "text" in segments[0]
    assert segments[0]["speaker_label"] == "Speaker 1"

    mock_scenes = MockSceneDetector()
    assert mock_scenes.is_available()
    scenes = await mock_scenes.detect_scenes("/fake/path.mp4", "/tmp/scenes", 30.0)
    assert len(scenes) > 0
    assert scenes[0]["start_time"] == 0.0

    mock_ocr = MockOCRProvider()
    assert mock_ocr.is_available()
    ocr_items = await mock_ocr.extract_text("/fake/frame.jpg")
    assert len(ocr_items) > 0
    assert "extracted_text" in ocr_items[0]
    assert ocr_items[0]["confidence"] > 0
