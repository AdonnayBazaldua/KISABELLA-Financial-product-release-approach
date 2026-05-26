-- backend/db/migrations/001_initial.sql

-- Extensión para UUIDs
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Usuario de aplicación (para RLS)
CREATE TABLE IF NOT EXISTS app_users (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username   VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insertar usuario por defecto (Sprint 1: sin auth complejo)
INSERT INTO app_users (id, username)
VALUES ('00000000-0000-0000-0000-000000000001', 'admin')
ON CONFLICT DO NOTHING;

-- Evaluaciones
CREATE TABLE IF NOT EXISTS evaluations (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_by     UUID REFERENCES app_users(id),
    name           VARCHAR(255) NOT NULL,
    status         VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending | running | complete | error
    final_verdict  VARCHAR(30),
    -- viable | viable_con_ajustes | no_viable
    final_score    SMALLINT CHECK (final_score BETWEEN 0 AND 100),
    final_summary  TEXT,
    error_message  TEXT,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Inputs del formulario
CREATE TABLE IF NOT EXISTS evaluation_inputs (
    id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id              UUID NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    product_name               VARCHAR(255) NOT NULL,
    description                TEXT,
    category                   VARCHAR(20) DEFAULT 'fisico',
    -- Costos en MXN
    cost_purchase              NUMERIC(12,2) NOT NULL DEFAULT 0,
    cost_purchase_usd          NUMERIC(12,2),
    cost_freight               NUMERIC(12,2) NOT NULL DEFAULT 0,
    cost_customs               NUMERIC(12,2) NOT NULL DEFAULT 0,
    cost_storage               NUMERIC(12,2) NOT NULL DEFAULT 0,
    cost_logistics_vehicle     NUMERIC(12,2) NOT NULL DEFAULT 0,
    cost_logistics_viaticos    NUMERIC(12,2) NOT NULL DEFAULT 0,
    cost_logistics_personnel   NUMERIC(12,2) NOT NULL DEFAULT 0,
    cost_shrinkage_pct         NUMERIC(5,2)  NOT NULL DEFAULT 0,
    cost_commission_pct        NUMERIC(5,2)  NOT NULL DEFAULT 0,
    cost_marketing             NUMERIC(12,2) NOT NULL DEFAULT 0,
    cost_overhead              NUMERIC(12,2) NOT NULL DEFAULT 0,
    -- Precio y volumen
    target_price               NUMERIC(12,2) NOT NULL,
    estimated_units_month      INTEGER NOT NULL DEFAULT 1,
    sales_channel              VARCHAR(100),
    -- Tipo de cambio (guardado al momento de la evaluación)
    exchange_rate_used         NUMERIC(8,4),
    exchange_rate_at           TIMESTAMPTZ
);

-- Resultados por agente
CREATE TABLE IF NOT EXISTS agent_results (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id    UUID NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    agent_name       VARCHAR(30) NOT NULL,
    -- financiero | mercado | riesgo | estrategia | orquestador
    score            SMALLINT CHECK (score BETWEEN 0 AND 100),
    veredicto_corto  VARCHAR(255),
    analisis_extenso TEXT,
    hallazgos_clave  JSONB NOT NULL DEFAULT '[]',
    recomendaciones  JSONB NOT NULL DEFAULT '[]',
    raw_calculations JSONB,
    completed_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Chat (Sprint 5, tabla preparada)
CREATE TABLE IF NOT EXISTS chat_messages (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id UUID NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    role          VARCHAR(10) NOT NULL CHECK (role IN ('user', 'assistant')),
    content       TEXT NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Índices ─────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_evaluations_created_by ON evaluations(created_by);
CREATE INDEX IF NOT EXISTS idx_evaluations_status ON evaluations(status);
CREATE INDEX IF NOT EXISTS idx_evaluations_created_at ON evaluations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_results_evaluation ON agent_results(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_evaluation ON chat_messages(evaluation_id);

-- ─── Row Level Security ───────────────────────────────────────────────────────
ALTER TABLE evaluations      ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluation_inputs ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_results    ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages    ENABLE ROW LEVEL SECURITY;

CREATE POLICY eval_rls ON evaluations
    FOR ALL
    USING (created_by::text = current_setting('app.user_id', true));

CREATE POLICY inputs_rls ON evaluation_inputs
    FOR ALL
    USING (evaluation_id IN (
        SELECT id FROM evaluations
        WHERE created_by::text = current_setting('app.user_id', true)
    ));

CREATE POLICY agent_results_rls ON agent_results
    FOR ALL
    USING (evaluation_id IN (
        SELECT id FROM evaluations
        WHERE created_by::text = current_setting('app.user_id', true)
    ));

CREATE POLICY chat_rls ON chat_messages
    FOR ALL
    USING (evaluation_id IN (
        SELECT id FROM evaluations
        WHERE created_by::text = current_setting('app.user_id', true)
    ));

-- Función trigger para updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER evaluations_updated_at
    BEFORE UPDATE ON evaluations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
