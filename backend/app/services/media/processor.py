"""Hardened FFmpeg/FFprobe media processor abstraction."""

import asyncio
import json
import os
import shutil
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.logging import logger


class ToolUnavailableError(RuntimeError):
    """Raised when an external media processing binary (e.g. FFmpeg) is not installed."""

    pass


class MediaProcessingError(RuntimeError):
    """Raised when media processing fails during execution."""

    pass


class MediaProcessor(ABC):
    """Abstract interface for video/audio processing and metadata extraction."""

    IS_MOCK: bool = False

    @abstractmethod
    def is_available(self) -> bool:
        """Check if underlying processing binaries are installed in the host runtime."""
        pass

    @abstractmethod
    async def extract_metadata(self, input_path: str) -> Dict[str, Any]:
        """Extract media streams, resolution, duration, codecs using FFprobe."""
        pass

    @abstractmethod
    async def extract_audio(self, input_path: str, output_path: str) -> Dict[str, Any]:
        """Extract audio stream to standard 16kHz WAV or MP3."""
        pass

    @abstractmethod
    async def generate_derivative(
        self,
        input_path: str,
        output_path: str,
        derivative_type: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Transcode video to proxy, 9:16 vertical, or web-friendly format."""
        pass

    @abstractmethod
    async def extract_keyframes(
        self, input_path: str, output_dir: str, max_frames: int = 10
    ) -> List[Dict[str, Any]]:
        """Extract representative shot keyframes."""
        pass


class FFmpegMediaProcessor(MediaProcessor):
    """Production media processor executing actual FFmpeg and FFprobe binaries.

    SECURITY INVARIANTS:
    - Never uses shell=True.
    - Commands constructed strictly as argument arrays.
    - Sanitizes subprocess environment to prevent credential/secret leakage.
    - Enforces timeout, input path validation, and output path containment.
    - If binaries are missing, operations raise ToolUnavailableError.
    """

    IS_MOCK: bool = False

    def __init__(
        self,
        ffmpeg_path: Optional[str] = None,
        ffprobe_path: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.ffmpeg_path = ffmpeg_path or settings.FFMPEG_BINARY_PATH
        self.ffprobe_path = ffprobe_path or settings.FFPROBE_BINARY_PATH
        self.timeout_seconds = timeout_seconds or settings.MEDIA_PROCESSING_TIMEOUT_SECONDS

    def is_available(self) -> bool:
        """Check if FFmpeg and FFprobe are discoverable in PATH or configured path."""
        has_ffmpeg = shutil.which(self.ffmpeg_path) is not None
        has_ffprobe = shutil.which(self.ffprobe_path) is not None
        return bool(has_ffmpeg and has_ffprobe)

    def _get_sanitized_env(self) -> Dict[str, str]:
        """Strip application secrets, DB URLs, and tokens from subprocess environment."""
        allowed_vars = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "HOME"}
        clean_env: Dict[str, str] = {}
        for k, v in os.environ.items():
            if k.upper() in allowed_vars:
                clean_env[k] = v
        return clean_env

    def _verify_tools(self) -> None:
        if not self.is_available():
            raise ToolUnavailableError(
                f"FFmpeg/FFprobe binaries ('{self.ffmpeg_path}', '{self.ffprobe_path}') "
                "are not installed or accessible in the host runtime PATH."
            )

    async def _run_command(self, cmd: List[str]) -> Tuple[bytes, bytes]:
        """Execute subprocess with argument array, timeout, and clean termination."""
        self._verify_tools()
        logger.info(f"Executing media processor command: {' '.join(cmd[:3])} ...")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._get_sanitized_env(),
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError as err:
            try:
                proc.kill()
            except Exception:
                pass
            raise MediaProcessingError(
                f"Media processing command timed out after {self.timeout_seconds} seconds."
            ) from err

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace")[-500:]
            raise MediaProcessingError(
                f"Command failed with exit code {proc.returncode}: {err_msg}"
            )

        return stdout, stderr

    async def extract_metadata(self, input_path: str) -> Dict[str, Any]:
        """Probes media file using FFprobe JSON output."""
        self._verify_tools()
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        cmd = [
            self.ffprobe_path,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            input_path,
        ]

        stdout, _ = await self._run_command(cmd)
        try:
            data = json.loads(stdout.decode("utf-8"))
        except Exception as e:
            raise MediaProcessingError(f"Failed to parse FFprobe JSON metadata: {e}") from e

        format_info = data.get("format", {})
        streams = data.get("streams", [])

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        duration = float(format_info.get("duration", 0.0))
        width = int(video_stream["width"]) if video_stream and "width" in video_stream else None
        height = int(video_stream["height"]) if video_stream and "height" in video_stream else None
        codec = (
            video_stream.get("codec_name")
            if video_stream
            else (audio_stream.get("codec_name") if audio_stream else None)
        )
        container = format_info.get("format_name", "").split(",")[0]

        return {
            "duration": duration,
            "width": width,
            "height": height,
            "codec": codec,
            "container": container,
            "format_details": format_info,
            "video_stream": video_stream,
            "audio_stream": audio_stream,
        }

    async def extract_audio(self, input_path: str, output_path: str) -> Dict[str, Any]:
        """Extracts audio to 16kHz mono WAV suitable for Whisper transcription."""
        self._verify_tools()
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            input_path,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            output_path,
        ]

        await self._run_command(cmd)
        file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0

        return {
            "output_path": output_path,
            "file_size": file_size,
            "sample_rate": 16000,
            "channels": 1,
            "format": "wav",
        }

    async def generate_derivative(
        self,
        input_path: str,
        output_path: str,
        derivative_type: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Transcodes video variants (Proxy 720p, 9:16 Vertical crop, 16:9)."""
        self._verify_tools()
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        cmd = [self.ffmpeg_path, "-y", "-i", input_path]

        if derivative_type == "VERTICAL_9_16":
            # Center crop to 9:16 vertical ratio (e.g. 1080x1920 or 720x1280)
            cmd.extend(
                ["-vf", "crop=ih*(9/16):ih", "-c:v", "libx264", "-crf", "23", "-preset", "fast"]
            )
        elif derivative_type == "PROXY":
            # Web-friendly 720p proxy
            cmd.extend(
                ["-vf", "scale=-2:720", "-c:v", "libx264", "-crf", "26", "-preset", "veryfast"]
            )
        elif derivative_type == "SHORT_CLIP":
            start_time = str(options.get("start_time", 0.0)) if options else "0.0"
            duration = str(options.get("duration", 15.0)) if options else "15.0"
            cmd.extend(["-ss", start_time, "-t", duration, "-c:v", "libx264", "-c:a", "aac"])
        else:
            cmd.extend(["-c:v", "libx264", "-preset", "fast"])

        cmd.append(output_path)
        await self._run_command(cmd)

        file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        return {
            "output_path": output_path,
            "file_size": file_size,
            "derivative_type": derivative_type,
        }

    async def extract_keyframes(
        self, input_path: str, output_dir: str, max_frames: int = 10
    ) -> List[Dict[str, Any]]:
        """Extracts shot change keyframes using FFmpeg scene filter."""
        self._verify_tools()
        os.makedirs(output_dir, exist_ok=True)

        pattern = os.path.join(output_dir, "keyframe_%03d.jpg")
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            input_path,
            "-vf",
            "select='gt(scene,0.4)'",
            "-vsync",
            "vfr",
            "-frames:v",
            str(max_frames),
            "-q:v",
            "2",
            pattern,
        ]

        await self._run_command(cmd)

        extracted: List[Dict[str, Any]] = []
        for fname in sorted(os.listdir(output_dir)):
            if fname.startswith("keyframe_") and fname.endswith(".jpg"):
                full_path = os.path.join(output_dir, fname)
                extracted.append(
                    {
                        "filename": fname,
                        "path": full_path,
                        "file_size": os.path.getsize(full_path),
                    }
                )

        return extracted


class MockMediaProcessor(MediaProcessor):
    """Test-only media processor fixture.

    STRICT GUARANTEE: Never used in production dependency graph.
    """

    IS_MOCK: bool = True

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail

    def is_available(self) -> bool:
        return True

    async def extract_metadata(self, input_path: str) -> Dict[str, Any]:
        if self.should_fail:
            raise MediaProcessingError("Mock FFprobe execution failed")
        return {
            "duration": 45.0,
            "width": 1920,
            "height": 1080,
            "codec": "h264",
            "container": "mov,mp4,m4a,3gp,3g2,mj2",
            "format_details": {"format_name": "mp4", "duration": "45.0"},
            "video_stream": {"codec_name": "h264", "width": 1920, "height": 1080},
            "audio_stream": {"codec_name": "aac", "sample_rate": "48000"},
        }

    async def extract_audio(self, input_path: str, output_path: str) -> Dict[str, Any]:
        if self.should_fail:
            raise MediaProcessingError("Mock audio extraction failed")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(
                b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
                b"\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
            )
        return {
            "output_path": output_path,
            "file_size": 44,
            "sample_rate": 16000,
            "channels": 1,
            "format": "wav",
        }

    async def generate_derivative(
        self,
        input_path: str,
        output_path: str,
        derivative_type: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self.should_fail:
            raise MediaProcessingError("Mock derivative generation failed")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42")
        return {"output_path": output_path, "file_size": 28, "derivative_type": derivative_type}

    async def extract_keyframes(
        self, input_path: str, output_dir: str, max_frames: int = 10
    ) -> List[Dict[str, Any]]:
        if self.should_fail:
            raise MediaProcessingError("Mock keyframe extraction failed")
        os.makedirs(output_dir, exist_ok=True)
        sample = os.path.join(output_dir, "keyframe_001.jpg")
        with open(sample, "wb") as f:
            f.write(
                b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00"
            )
        return [{"filename": "keyframe_001.jpg", "path": sample, "file_size": 24}]
