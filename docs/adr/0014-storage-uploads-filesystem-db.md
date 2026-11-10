# 0014 — Storage de uploads = filesystem + metadata en DB

**Estado:** aceptado
**Fecha:** 2026-05-29

## Contexto

Sprint 5 añade uploads de documentos al chat de seguimiento (PDFs, DOCX, XLSX, CSV, imágenes).
Necesitamos decidir dónde almacenar los archivos físicos.

## Decisión

Archivos físicos en volumen Docker `uploads_data` montado en `/data/uploads/{eval_id}/{msg_id}/{sha256}.{ext}`.
La DB guarda metadata + sha256 + `markdown_extracted`. Sin object storage en V1.

## Por qué

- Coherente con ADR-009 (single-box, todo en una caja, VPS IONOS).
- Backup = rsync del volumen + pg_dump. Sin dependencias externas.
- SHA256 como nombre de archivo = deduplicación automática.
- Upgrade futuro a S3/R2 aislado exclusivamente en `upload_service.py` — no toca API ni modelos.

## Consecuencias

- Archivos no accesibles directamente por URL pública (intencional — IP whitelist).
- Backup requiere sincronizar dos artefactos (DB + volumen Docker).
- Migración a object storage en V2: solo cambiar `upload_service.py`.
