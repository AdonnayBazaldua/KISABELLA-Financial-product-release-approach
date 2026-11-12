-- backend/db/migrations/002_effective_rls.sql
--
-- Corrige los 3 bugs de RLS detectados en la auditoría 2026-05-23:
--   1. Sin FORCE RLS → owner bypassea RLS en runtime
--   2. Policies con USING pero sin WITH CHECK → INSERT con created_by ajeno pasa
--   3. Las policies del 001 no validan en escritura
--
-- ADR-008: RLS efectivo (no solo declarado).
--
-- Idempotente: usa DROP POLICY IF EXISTS + ALTER TABLE.
-- Nota sobre rol: el audit recomendó rol `kisabella_app` NO-owner como
-- defensa-en-profundidad. Para 2-3 users internos con IP whitelist en
-- Nginx, FORCE RLS + bindparams es suficiente sin la complejidad de
-- two-role setup. Documentado en ADR-008. Si se suman users en Sprint
-- 7+, se introduce kisabella_app NO-owner.

BEGIN;

-- ============================================================
-- 1. FORCE RLS — aplica RLS incluso al owner de la tabla
-- ============================================================
ALTER TABLE evaluations       FORCE ROW LEVEL SECURITY;
ALTER TABLE evaluation_inputs FORCE ROW LEVEL SECURITY;
ALTER TABLE agent_results     FORCE ROW LEVEL SECURITY;
ALTER TABLE chat_messages     FORCE ROW LEVEL SECURITY;

-- ============================================================
-- 2. Policies con USING + WITH CHECK (lectura Y escritura)
-- ============================================================

-- evaluations
DROP POLICY IF EXISTS eval_rls ON evaluations;
CREATE POLICY eval_rls ON evaluations
    FOR ALL
    USING      (created_by::text = current_setting('app.user_id', true))
    WITH CHECK (created_by::text = current_setting('app.user_id', true));

-- evaluation_inputs (FK → evaluations)
DROP POLICY IF EXISTS inputs_rls ON evaluation_inputs;
CREATE POLICY inputs_rls ON evaluation_inputs
    FOR ALL
    USING (
        evaluation_id IN (
            SELECT id FROM evaluations
            WHERE created_by::text = current_setting('app.user_id', true)
        )
    )
    WITH CHECK (
        evaluation_id IN (
            SELECT id FROM evaluations
            WHERE created_by::text = current_setting('app.user_id', true)
        )
    );

-- agent_results (FK → evaluations)
DROP POLICY IF EXISTS agent_results_rls ON agent_results;
CREATE POLICY agent_results_rls ON agent_results
    FOR ALL
    USING (
        evaluation_id IN (
            SELECT id FROM evaluations
            WHERE created_by::text = current_setting('app.user_id', true)
        )
    )
    WITH CHECK (
        evaluation_id IN (
            SELECT id FROM evaluations
            WHERE created_by::text = current_setting('app.user_id', true)
        )
    );

-- chat_messages (FK → evaluations)
DROP POLICY IF EXISTS chat_rls ON chat_messages;
CREATE POLICY chat_rls ON chat_messages
    FOR ALL
    USING (
        evaluation_id IN (
            SELECT id FROM evaluations
            WHERE created_by::text = current_setting('app.user_id', true)
        )
    )
    WITH CHECK (
        evaluation_id IN (
            SELECT id FROM evaluations
            WHERE created_by::text = current_setting('app.user_id', true)
        )
    );

-- ============================================================
-- 3. Smoke check: sin app.user_id seteado, SELECT debe retornar 0
-- ============================================================
-- (No se ejecuta acá — verificado por tests de integración)

COMMIT;
