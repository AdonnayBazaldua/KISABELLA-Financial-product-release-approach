# backend/tests/services/test_upload_service.py
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import pytest

from services.upload_service import (
    ALLOWED_MIMES,
    MimeNotAllowedError,
    FileTooLargeError,
    UploadedFile,
    save_upload,
)


@pytest.mark.asyncio
async def test_save_upload_pdf_creates_file(tmp_path, monkeypatch):
    monkeypatch.setattr("services.upload_service.UPLOAD_ROOT", tmp_path)
    content = b"%PDF-1.4 fake pdf content here"
    eval_id = uuid.uuid4()
    msg_id = uuid.uuid4()

    result = await save_upload(
        data=content,
        filename="cotizacion.pdf",
        declared_mime="application/pdf",
        eval_id=eval_id,
        message_id=msg_id,
    )

    assert result.mime_type == "application/pdf"
    assert result.size_bytes == len(content)
    assert result.sha256 == hashlib.sha256(content).hexdigest()
    assert Path(result.storage_path).exists()
    assert not result.is_image


@pytest.mark.asyncio
async def test_save_upload_image_detected_as_image(tmp_path, monkeypatch):
    monkeypatch.setattr("services.upload_service.UPLOAD_ROOT", tmp_path)
    # minimal JPEG magic bytes
    jpeg_header = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"\x00" * 100
    result = await save_upload(
        data=jpeg_header,
        filename="foto.jpg",
        declared_mime="image/jpeg",
        eval_id=uuid.uuid4(),
        message_id=uuid.uuid4(),
    )
    assert result.is_image
    assert result.mime_type == "image/jpeg"


@pytest.mark.asyncio
async def test_save_upload_rejects_unknown_mime(tmp_path, monkeypatch):
    monkeypatch.setattr("services.upload_service.UPLOAD_ROOT", tmp_path)
    # zip magic bytes
    zip_content = b"PK\x03\x04" + b"\x00" * 50
    with pytest.raises(MimeNotAllowedError):
        await save_upload(
            data=zip_content,
            filename="malicious.zip",
            declared_mime="application/zip",
            eval_id=uuid.uuid4(),
            message_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_save_upload_rejects_oversized(tmp_path, monkeypatch):
    monkeypatch.setattr("services.upload_service.UPLOAD_ROOT", tmp_path)
    monkeypatch.setattr("services.upload_service.MAX_FILE_BYTES", 10)
    with pytest.raises(FileTooLargeError):
        await save_upload(
            data=b"x" * 11,
            filename="big.txt",
            declared_mime="text/plain",
            eval_id=uuid.uuid4(),
            message_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_save_upload_text_file(tmp_path, monkeypatch):
    monkeypatch.setattr("services.upload_service.UPLOAD_ROOT", tmp_path)
    content = b"col1,col2\n1,2\n3,4"
    result = await save_upload(
        data=content,
        filename="data.csv",
        declared_mime="text/csv",
        eval_id=uuid.uuid4(),
        message_id=uuid.uuid4(),
    )
    assert "text/" in result.mime_type
    assert not result.is_image


@pytest.mark.asyncio
async def test_save_upload_undetectable_binary_with_text_mime(tmp_path, monkeypatch):
    monkeypatch.setattr("services.upload_service.UPLOAD_ROOT", tmp_path)
    # Binary with no recognizable magic bytes — filetype returns None
    data = b"\x00\x01\x02\x03" * 20
    result = await save_upload(
        data=data,
        filename="unknown.bin",
        declared_mime="text/plain",
        eval_id=uuid.uuid4(),
        message_id=uuid.uuid4(),
    )
    assert result.mime_type == "text/plain"
    assert not result.is_image
    assert Path(result.storage_path).exists()
