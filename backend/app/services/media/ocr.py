"""Optical Character Recognition (OCR) provider abstraction."""

import shutil
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from app.core.logging import logger
from app.services.media.processor import ToolUnavailableError


class OCRProvider(ABC):
    """Abstract interface for local on-screen text extraction."""

    IS_MOCK: bool = False

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    async def extract_text(self, image_path: str) -> List[Dict[str, Any]]:
        pass


class LocalOCRProvider(OCRProvider):
    """Production local OCR engine checking for Tesseract installation.

    STRICT INVARIANT:
    If Tesseract is not installed, operations raise ToolUnavailableError.
    Never fabricates synthetic on-screen text in production.
    """

    IS_MOCK: bool = False

    def is_available(self) -> bool:
        return shutil.which("tesseract") is not None

    async def extract_text(self, image_path: str) -> List[Dict[str, Any]]:
        if not self.is_available():
            raise ToolUnavailableError(
                "Tesseract OCR binary is not installed in the host runtime environment."
            )

        logger.info(f"Running production OCR on {image_path}")
        raise NotImplementedError("Tesseract OCR integration pending system binary installation.")


class MockOCRProvider(OCRProvider):
    """Test fixture mock OCR provider."""

    IS_MOCK: bool = True

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail

    def is_available(self) -> bool:
        return True

    async def extract_text(self, image_path: str) -> List[Dict[str, Any]]:
        if self.should_fail:
            raise RuntimeError("Mock OCR extraction failed")

        return [
            {
                "timestamp": 2.5,
                "extracted_text": "BREAKING NEWS: METRO PHASE 2 TIMELINE",
                "confidence": 0.95,
                "bounding_box": {"x": 50, "y": 900, "w": 800, "h": 60},
            },
            {
                "timestamp": 12.0,
                "extracted_text": "OFFICIAL STATEMENT - CITY TRANSPORT AUTHORITY",
                "confidence": 0.91,
                "bounding_box": {"x": 100, "y": 200, "w": 600, "h": 40},
            },
        ]
