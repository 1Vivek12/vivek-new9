"""Local transcription provider abstraction."""

import shutil
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.logging import logger
from app.services.media.processor import ToolUnavailableError


class TranscriptionProvider(ABC):
    """Abstract interface for speech-to-text transcription."""

    IS_MOCK: bool = False

    @abstractmethod
    def is_available(self) -> bool:
        """Check if transcription engine/model is installed on host."""
        pass

    @abstractmethod
    async def transcribe(self, audio_path: str, language: Optional[str] = None) -> Dict[str, Any]:
        """Transcribe audio into full text and timestamped segments."""
        pass


class LocalWhisperProvider(TranscriptionProvider):
    """Production transcription provider utilizing local Whisper inference.

    STRICT INVARIANT:
    If Whisper is not installed on the system, operations raise ToolUnavailableError.
    Never fabricates a synthetic transcript in production.
    """

    IS_MOCK: bool = False

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.WHISPER_MODEL_NAME

    def is_available(self) -> bool:
        """Check if whisper executable or python package is available."""
        has_cli = shutil.which("whisper") is not None
        try:
            import whisper  # noqa: F401

            has_module = True
        except ImportError:
            has_module = False
        return has_cli or has_module

    async def transcribe(self, audio_path: str, language: Optional[str] = None) -> Dict[str, Any]:
        if not self.is_available():
            raise ToolUnavailableError(
                "Local Whisper transcription engine is not installed in the host "
                "runtime environment."
            )

        logger.info(f"Running production Whisper transcription on {audio_path}")
        # Note: Actual whisper execution would run here when installed
        raise NotImplementedError(
            "Whisper runtime integration pending local model weight provisioning."
        )


class MockTranscriptionProvider(TranscriptionProvider):
    """Test-only transcription provider fixture.

    STRICT GUARANTEE: Never used in production dependency graph.
    Uses honest generic speaker labels: 'Speaker 1', 'Speaker 2'.
    """

    IS_MOCK: bool = True

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail

    def is_available(self) -> bool:
        return True

    async def transcribe(self, audio_path: str, language: Optional[str] = None) -> Dict[str, Any]:
        if self.should_fail:
            raise RuntimeError("Mock transcription failed")

        return {
            "language": language or "en",
            "model_provider": "whisper_mock",
            "model_version": "v1-test",
            "duration": 45.0,
            "full_text": (
                "Welcome to News 9 Special Report. Today city officials announced "
                "the new metro line expansion, aimed at reducing urban transit congestion "
                "by thirty percent over the next two years. Community leaders have welcomed "
                "the announcement while urging strict environmental oversight."
            ),
            "confidence_score": 0.94,
            "segments": [
                {
                    "sequence": 1,
                    "start_time": 0.0,
                    "end_time": 5.2,
                    "text": "Welcome to News 9 Special Report.",
                    "speaker_label": "Speaker 1",
                    "confidence": 0.96,
                },
                {
                    "sequence": 2,
                    "start_time": 5.2,
                    "end_time": 18.5,
                    "text": (
                        "Today city officials announced the new metro line expansion, "
                        "aimed at reducing urban transit congestion by thirty percent "
                        "over the next two years."
                    ),
                    "speaker_label": "Speaker 1",
                    "confidence": 0.94,
                },
                {
                    "sequence": 3,
                    "start_time": 18.5,
                    "end_time": 30.0,
                    "text": (
                        "Community leaders have welcomed the announcement while urging strict "
                        "environmental oversight."
                    ),
                    "speaker_label": "Speaker 2",
                    "confidence": 0.92,
                },
            ],
        }
