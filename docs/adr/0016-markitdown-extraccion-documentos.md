# 0016 — Markitdown para extracción documento → markdown

**Estado:** aceptado
**Fecha:** 2026-05-29

## Contexto

Los archivos adjuntos al chat (PDF, DOCX, XLSX, CSV) deben ser procesados antes de enviarse
al LLM para maximizar la comprensión y minimizar el uso de tokens.

## Decisión

Único pipeline de extracción: PDF/DOCX/XLSX/CSV/TXT → `MarkItDown().convert()` → markdown.
Imágenes (JPEG, PNG, WebP) NO pasan por Markitdown — van directamente a Claude vision API como bloques base64.
Timeout 20s por archivo; fallo de extracción no aborta el turno (log + `markdown_extracted=None`).

## Por qué

- Tablas y estructura preservadas en markdown: ~15-25% menos tokens vs texto plano.
- Una sola lib reemplaza pypdf + csv + openpyxl + mammoth (4 deps → 1).
- Microsoft OSS (markitdown), Python-only para los formatos usados, ~50MB adicional en Docker.
- Imágenes a Claude vision nativa: mejor comprensión que OCR, sin dependencias extra.

## Consecuencias

- Degradación graceful: si markitdown falla para un archivo, el turno continúa sin ese contenido.
- Sin soporte para imágenes dentro de PDFs (requeriría Azure Vision — fuera de scope).
- ~50MB adicional en imagen Docker del backend (libxml2 + libxslt1.1 + markitdown deps).
