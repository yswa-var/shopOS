"""Safe local staging and finalization of Telegram proof images."""

from __future__ import annotations

import io
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo


class ProofStorageError(RuntimeError):
    """Base error for proof validation and filesystem failures."""


class InvalidImageError(ProofStorageError):
    """Raised when bytes are not a supported JPEG or PNG image."""


class ImageTooLargeError(ProofStorageError):
    """Raised when an image exceeds the configured byte limit."""


class ProofNotFoundError(ProofStorageError):
    """Raised when a draft has no staged proof to finalize."""


@dataclass(frozen=True, slots=True)
class StagedProof:
    """Metadata for a staged image."""

    draft_id: str
    extension: str
    size_bytes: int
    relative_path: str


def _safe_draft_id(draft_id: str) -> str:
    try:
        return str(UUID(str(draft_id)))
    except (ValueError, AttributeError, TypeError) as error:
        raise ProofStorageError("draft_id must be a UUID") from error


def detect_image_extension(content: bytes) -> str:
    """Detect JPEG or PNG from content bytes, never from a filename."""

    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        offset = 8
        has_ihdr = False
        has_iend = False
        width = height = 0
        while offset + 12 <= len(content):
            chunk_length = int.from_bytes(content[offset : offset + 4], "big")
            chunk_end = offset + 12 + chunk_length
            if chunk_end > len(content):
                raise InvalidImageError("truncated PNG chunk")
            chunk_type = content[offset + 4 : offset + 8]
            chunk_data = content[offset + 8 : offset + 8 + chunk_length]
            if chunk_type == b"IHDR":
                if has_ihdr or chunk_length != 13:
                    raise InvalidImageError("invalid PNG IHDR")
                width = int.from_bytes(chunk_data[:4], "big")
                height = int.from_bytes(chunk_data[4:8], "big")
                has_ihdr = True
            elif chunk_type == b"IEND":
                if chunk_length != 0:
                    raise InvalidImageError("invalid PNG IEND")
                has_iend = True
                break
            offset = chunk_end
        if not has_ihdr or not has_iend or width <= 0 or height <= 0:
            raise InvalidImageError("invalid PNG structure")
        return "png"

    if content.startswith(b"\xff\xd8\xff") and content.endswith(b"\xff\xd9"):
        offset = 2
        has_frame = False
        while offset < len(content) - 2:
            if content[offset] != 0xFF:
                offset += 1
                continue
            while offset < len(content) and content[offset] == 0xFF:
                offset += 1
            if offset >= len(content):
                break
            marker = content[offset]
            offset += 1
            if marker == 0xD9:
                break
            if marker in {0xD8, 0x01} or 0xD0 <= marker <= 0xD7:
                continue
            if offset + 2 > len(content):
                raise InvalidImageError("truncated JPEG segment")
            segment_length = int.from_bytes(content[offset : offset + 2], "big")
            if segment_length < 2 or offset + segment_length > len(content):
                raise InvalidImageError("invalid JPEG segment")
            if 0xC0 <= marker <= 0xCF and marker not in {0xC4, 0xC8, 0xCC}:
                has_frame = True
            offset += segment_length
        if not has_frame:
            raise InvalidImageError("JPEG has no image frame")
        return "jpg"

    raise InvalidImageError("only JPEG and PNG images are supported")


class ProofStorage:
    """Manage draft staging and permanent proof paths under one data root."""

    def __init__(
        self,
        data_dir: str | Path,
        *,
        max_image_mb: int = 10,
        business_timezone: str = "Asia/Kolkata",
    ) -> None:
        if max_image_mb < 1:
            raise ValueError("max_image_mb must be at least 1")
        self.data_dir = Path(data_dir)
        self.staging_dir = self.data_dir / "staging"
        self.parchi_dir = self.data_dir / "parchi"
        self.max_bytes = max_image_mb * 1024 * 1024
        self._timezone = ZoneInfo(business_timezone)

    def _validate_content(self, content: bytes) -> str:
        if len(content) > self.max_bytes:
            raise ImageTooLargeError(
                f"image is {len(content)} bytes; maximum is {self.max_bytes} bytes"
            )
        if not content:
            raise InvalidImageError("image is empty")
        return detect_image_extension(content)

    def _staged_files(self, draft_id: str) -> list[Path]:
        return [
            self.staging_dir / f"{draft_id}.jpg",
            self.staging_dir / f"{draft_id}.png",
        ]

    def stage_bytes(
        self,
        draft_id: str,
        content: bytes,
        *,
        original_filename: str | None = None,
    ) -> StagedProof:
        """Validate and atomically replace the draft's staged proof."""

        del original_filename
        safe_id = _safe_draft_id(draft_id)
        extension = self._validate_content(content)
        self.staging_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = self.staging_dir / f"{safe_id}.{extension}"
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.staging_dir,
                prefix=f".{safe_id}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                os.chmod(temporary_path, 0o600)
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, target)
            os.chmod(target, 0o600)
            for old_path in self._staged_files(safe_id):
                if old_path != target:
                    old_path.unlink(missing_ok=True)
        except Exception:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise

        return StagedProof(
            draft_id=safe_id,
            extension=extension,
            size_bytes=len(content),
            relative_path=Path("staging", target.name).as_posix(),
        )

    async def stage_telegram_file(self, bot: Any, draft_id: str, file_id: str) -> StagedProof:
        """Download one Telegram file and stage its verified image bytes."""

        telegram_file = await bot.get_file(file_id)
        declared_size = getattr(telegram_file, "file_size", None)
        if declared_size is not None and declared_size > self.max_bytes:
            raise ImageTooLargeError(
                f"Telegram file is {declared_size} bytes; maximum is {self.max_bytes} bytes"
            )
        file_path = getattr(telegram_file, "file_path", None)
        if not file_path:
            raise ProofStorageError("Telegram did not return a downloadable file path")

        content = io.BytesIO()
        try:
            await bot.download_file(file_path, destination=content)
        except Exception as error:
            raise ProofStorageError("Telegram image download failed") from error
        return self.stage_bytes(draft_id, content.getvalue())

    def remove_staged(self, draft_id: str) -> int:
        """Remove only temporary files for a draft; finalized files are untouched."""

        safe_id = _safe_draft_id(draft_id)
        removed = 0
        for path in self._staged_files(safe_id):
            if path.exists():
                path.unlink()
                removed += 1
        return removed

    def finalize(
        self,
        draft_id: str,
        *,
        now: datetime | None = None,
    ) -> str:
        """Move a staged proof into its unique permanent relative path."""

        safe_id = _safe_draft_id(draft_id)
        staged = next((path for path in self._staged_files(safe_id) if path.is_file()), None)
        if staged is None:
            raise ProofNotFoundError(f"no staged proof for draft {safe_id}")

        current = now.astimezone(self._timezone) if now else datetime.now(self._timezone)
        date_dir = self.parchi_dir / current.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = date_dir / f"{current:%H%M%S}_{uuid4().hex[:8]}{staged.suffix.lower()}"
        os.replace(staged, target)
        os.chmod(target, 0o600)
        return Path("parchi", date_dir.name, target.name).as_posix()

