# 0008 — RLS efectivo con FORCE y rol no-owner

**Estado:** aceptado
**Fecha:** 2026-05-23

## Contexto

El Sprint 1 declaraba RLS policies pero el rol de la aplicación era owner de las tablas, lo que bypasea RLS por defecto en PostgreSQL. Las policies nunca se aplicaban en runtime.

## Decisión

RLS efectivo requiere tres condiciones simultáneas:

1. Rol `kisabella_app` que NO es owner de las tablas.
2. `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` (aplica incluso al owner para mayor seguridad).
3. Policies con `USING` (lectura) y `WITH CHECK` (escritura) basadas en `current_setting('app.user_id', true)`.

El `SET LOCAL app.user_id` se ejecuta siempre con `text().bindparams(uid=...)`, nunca con f-strings.

## Consecuencias

- Positivo: defensa en profundidad real — un bug en la aplicación no expone datos de otro usuario.
- Positivo: auditable: las policies son SQL declarativo.
- Negativo: requiere setup de roles en migración.
- Negativo: `SET LOCAL` en cada request agrega ~1ms de latencia.

## Alternativas consideradas

- Filtro WHERE en queries: frágil, un JOIN sin filtro expone datos.
- RLS sin FORCE + owner: no aplica en runtime (bug del Sprint 1).
