from __future__ import annotations

import base64
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from shopos.services.proof_storage import (
    ImageTooLargeError,
    InvalidImageError,
    ProofNotFoundError,
    ProofStorage,
)


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)
JPEG = (
    b"\xff\xd8\xff\xe0\x00\x04\x00\x00"
    b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
    b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00\x00\xff\xd9"
)


def test_stage_validates_content_and_ignores_filename(tmp_path) -> None:
    storage = ProofStorage(tmp_path / "data")
    draft_id = "12345678-1234-5678-1234-567812345678"

    staged = storage.stage_bytes(draft_id, PNG, original_filename="../../evil")

    assert staged.extension == "png"
    assert staged.relative_path == f"staging/{draft_id}.png"
    assert (tmp_path / "data" / staged.relative_path).read_bytes() == PNG
    assert not (tmp_path / "data" / "evil.exe").exists()


def test_empty_and_oversized_proofs_are_rejected(tmp_path) -> None:
    storage = ProofStorage(tmp_path / "data", max_image_mb=1)
    draft_id = "12345678-1234-5678-1234-567812345678"

    with pytest.raises(InvalidImageError):
        storage.stage_bytes(draft_id, b"")
    with pytest.raises(ImageTooLargeError):
        storage.stage_bytes(draft_id, b"x" * (1024 * 1024 + 1))
    assert not (tmp_path / "data" / "staging").exists()


def test_any_file_type_is_saved_with_a_safe_extension(tmp_path) -> None:
    storage = ProofStorage(tmp_path / "data")
    draft_id = "12345678-1234-5678-1234-567812345678"

    staged = storage.stage_bytes(draft_id, b"%PDF-proof", original_filename="../../proof.pdf")

    assert staged.extension == "pdf"
    assert (tmp_path / "data" / staged.relative_path).read_bytes() == b"%PDF-proof"


def test_replacing_image_removes_old_staged_format(tmp_path) -> None:
    storage = ProofStorage(tmp_path / "data")
    draft_id = "12345678-1234-5678-1234-567812345678"

    first = storage.stage_bytes(draft_id, PNG)
    second = storage.stage_bytes(draft_id, JPEG)

    assert first.extension == "png"
    assert second.extension == "jpg"
    assert not (tmp_path / "data" / first.relative_path).exists()
    assert (tmp_path / "data" / second.relative_path).exists()


def test_telegram_download_is_limited_and_staged(tmp_path) -> None:
    storage = ProofStorage(tmp_path / "data")

    class FakeBot:
        async def get_file(self, file_id):
            assert file_id == "telegram-file-id"
            return SimpleNamespace(file_path="photos/proof", file_size=len(JPEG))

        async def download_file(self, file_path, *, destination):
            assert file_path == "photos/proof"
            destination.write(JPEG)

    staged = __import__("asyncio").run(
        storage.stage_telegram_file(
            FakeBot(), "12345678-1234-5678-1234-567812345678", "telegram-file-id"
        )
    )

    assert staged.extension == "jpg"


def test_finalize_moves_to_date_directory_and_remove_staged_never_touches_final(
    tmp_path,
) -> None:
    storage = ProofStorage(tmp_path / "data")
    draft_id = "12345678-1234-5678-1234-567812345678"
    storage.stage_bytes(draft_id, JPEG)
    now = datetime(2026, 10, 28, 17, 30, 45, tzinfo=ZoneInfo("Asia/Kolkata"))

    relative_path = storage.finalize(draft_id, now=now)

    final_path = tmp_path / "data" / relative_path
    assert relative_path.startswith("parchi/2026-10-28/173045_")
    assert final_path.suffix == ".jpg"
    assert final_path.read_bytes() == JPEG
    assert not (tmp_path / "data" / "staging" / f"{draft_id}.jpg").exists()
    assert storage.remove_staged(draft_id) == 0
    assert final_path.exists()


def test_finalize_without_staged_image_fails(tmp_path) -> None:
    storage = ProofStorage(tmp_path / "data")

    with pytest.raises(ProofNotFoundError):
        storage.finalize("12345678-1234-5678-1234-567812345678")

