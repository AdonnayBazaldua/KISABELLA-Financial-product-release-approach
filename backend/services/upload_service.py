# backend/services/upload_service.py
"""Servicio de almacenamiento de archivos para el chat de seguimiento.

Responsabilidades:
- Validar tamaño del archivo contra max_bytes.
- Detectar MIME real via magic bytes (filetype) — no confiar en el header declarado.
- Aceptar solo tipos en ALLOWED_MIMES; rechazar cualquier otro con MimeNotAllowedError.
- Escribir en upload_root/<eval_id>/<message_id>/<sha256><ext> de forma idempotente.
- Devolver UploadedFile con metadata completa para persistir en DB.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

import filetype

ALLOWED_MIMES: frozenset[str] = frozenset({
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
    "text/plain",
    "image/jpeg",
    "image/png",
    "image/webp",
})

IMAGE_MIMES: frozenset[str] = frozenset({"image/jpeg", "image/png", "image/webp"})

_MIME_TO_EXT: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "text/csv": ".csv",
    "text/plain": ".txt",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

TEXT_MIMES: frozenset[str] = frozenset({"text/csv", "text/plain"})


class MimeNotAllowedError(ValueError):
    """Se lanza cuando el tipo MIME detectado no está en ALLOWED_MIMES."""


class FileTooLargeError(ValueError):
    """Se lanza cuando el archivo supera max_bytes."""


@dataclass
class UploadedFile:
    storage_path: str
    sha256: str
    mime_type: str
    size_bytes: int
    original_name: str
    is_image: bool


async def save_upload(
    *,
    data: bytes,
    filename: str,
    declared_mime: str,
    eval_id: uuid.UUID,
    message_id: uuid.UUID,
    upload_root: Path,
    max_bytes: int,
) -> UploadedFile:
    """Valida y persiste un archivo subido por el usuario.

    Args:
        data: Contenido binario del archivo.
        filename: Nombre original reportado por el cliente.
        declared_mime: Tipo MIME declarado en el Content-Type del request.
        eval_id: UUID de la evaluación asociada (para organizar el path).
        message_id: UUID del mensaje al que pertenece el archivo.
        upload_root: Directorio raíz de almacenamiento (settings.upload_root).
        max_bytes: Tamaño máximo por archivo (settings.max_file_size_bytes).

    Returns:
        UploadedFile con metadata completa para persistir en DB.

    Raises:
        FileTooLargeError: Si len(data) > max_bytes.
        MimeNotAllowedError: Si el MIME detectado no está en ALLOWED_MIMES.
    """
    if len(data) > max_bytes:
        raise FileTooLargeError(
            f"Archivo excede {max_bytes // 1024 // 1024}MB "
            f"(tamaño recibido: {len(data)} bytes)"
        )

    # MIME detection: filetype reads magic bytes
    detected = filetype.guess(data)
    if detected is not None:
        mime = detected.mime
    elif declared_mime in TEXT_MIMES:
        # filetype cannot detect plain text — trust declaration for text/* only
        mime = declared_mime
    else:
        # Binary files MUST be identified by magic bytes
        raise MimeNotAllowedError(
            f"No se pudo verificar el tipo de archivo '{declared_mime}' por cabecera mágica. "
            "Solo archivos de texto pueden omitir la detección automática."
        )

    if mime not in ALLOWED_MIMES:
        raise MimeNotAllowedError(
            f"Tipo de archivo no permitido: {mime!r}. "
            f"Tipos aceptados: {', '.join(sorted(ALLOWED_MIMES))}"
        )

    sha = hashlib.sha256(data).hexdigest()
    ext = _MIME_TO_EXT.get(mime, ".bin")

    dest_dir = upload_root / str(eval_id) / str(message_id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / f"{sha}{ext}"
    # Idempotente: si ya existe el hash, no re-escribir (mismo contenido).
    if not dest.exists():
        dest.write_bytes(data)

    return UploadedFile(
        storage_path=str(dest),
        sha256=sha,
        mime_type=mime,
        size_bytes=len(data),
        original_name=filename,
        is_image=mime in IMAGE_MIMES,
    )
