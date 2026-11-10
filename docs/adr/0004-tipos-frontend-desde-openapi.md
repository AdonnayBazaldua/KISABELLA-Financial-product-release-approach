# 0004 — Tipos frontend generados desde OpenAPI

**Estado:** aceptado (implementación parcial: ver nota al final)
**Fecha:** 2026-05-23

## Contexto

El Sprint 1 tenía tipos TypeScript escritos a mano que divergían del backend Pydantic. Cualquier cambio de schema requería actualizar ambos lados manualmente.

## Decisión

Los tipos del frontend se generan con `openapi-typescript` desde `/openapi.json` del backend. Script: `npm run gen:types`. Los tipos manuales en `types.ts` se reemplazan por `types.generated.ts` cuando el codegen esté habilitado.

## Consecuencias

- Positivo: drift backend/frontend imposible.
- Positivo: un comando regenera todos los tipos.
- Negativo: requiere backend corriendo para regenerar.
- Negativo: tipos generados son verbosos — se usan type aliases para ergonomía.

## Alternativas consideradas

- Tipos manuales: descartado por drift comprobado en Sprint 1.
- GraphQL codegen: over-engineering para una API REST sencilla.

## Nota de implementación (2026-11-10)

El script `npm run gen:types` y la dependencia `openapi-typescript` existen, pero el frontend aún consume `frontend/lib/types.ts`, escrito a mano como espejo de `api/v1/schemas.py`. Migrar a `types.generated.ts` está pendiente.
