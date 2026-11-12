# 0009 — Deploy en VPS IONOS

**Estado:** reemplazado por ADR-0019
**Fecha:** 2026-05-23

## Contexto

Herramienta interna para 2-3 usuarios. No necesita auto-scaling ni alta disponibilidad. El presupuesto es mínimo (~$100/año).

## Decisión

Deploy en VPS IONOS.mx ($8-12/mes, 2 vCPU + 4GB RAM). Todo corre en una caja: Nginx + Frontend + Backend + PostgreSQL via Docker Compose.

## Consecuencias

- Positivo: TCO ~$100-150/año total.
- Positivo: IP whitelist nativa en Nginx (sin WAF extra).
- Positivo: sin vendor lock-in cloud (migratable a cualquier VPS).
- Negativo: single point of failure (aceptable para herramienta interna).
- Negativo: scaling manual si alguna vez se necesita.

## Alternativas consideradas

- AWS/GCP/Azure: overkill en costo y complejidad para 2-3 usuarios.
- Railway/Render: más caro para uptime 24/7 con DB incluida.
- Vercel + Supabase: fragmenta el deployment y limita control de Nginx.
