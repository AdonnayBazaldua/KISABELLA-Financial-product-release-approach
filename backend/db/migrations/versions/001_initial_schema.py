"""initial schema — migra desde legacy SQL 001+002 al control de Alembic.

Revision ID: 001
Revises: None
Create Date: 2026-05-26

Tablas: app_users, evaluations, evaluation_inputs, agent_results, chat_messages.
Incluye RLS (ENABLE + FORCE), policies con USING+WITH CHECK, índices, trigger updated_at.
Equivale a legacy/001_initial.sql + legacy/002_effective_rls.sql.

Para DBs existentes con las SQL legacy ya aplicadas:
    alembic stamp 001
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # --- app_users ---
    op.create_table(
        "app_users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(50), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.execute(
        "INSERT INTO app_users (id, username) "
        "VALUES ('00000000-0000-0000-0000-000000000001', 'admin') "
        "ON CONFLICT DO NOTHING"
    )

    # --- evaluations ---
    op.create_table(
        "evaluations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("app_users.id")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("final_verdict", sa.String(30), nullable=True),
        sa.Column("final_score", sa.SmallInteger, nullable=True),
        sa.Column("final_summary", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("warn_flags", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("requires_human_review", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("idempotency_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.CheckConstraint("final_score BETWEEN 0 AND 100", name="ck_evaluations_score_range"),
    )
    op.create_index("idx_evaluations_created_by", "evaluations", ["created_by"])
    op.create_index("idx_evaluations_status", "evaluations", ["status"])
    op.create_index("idx_evaluations_created_at", "evaluations", ["created_at"], postgresql_using="btree")
    op.create_index("ix_evaluations_idempotency_hash", "evaluations", ["idempotency_hash"])

    # --- evaluation_inputs ---
    op.create_table(
        "evaluation_inputs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("evaluation_id", UUID(as_uuid=True), sa.ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(20), server_default="fisico"),
        sa.Column("cost_purchase", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cost_purchase_usd", sa.Numeric(12, 2), nullable=True),
        sa.Column("cost_freight", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cost_customs", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cost_storage", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cost_logistics_vehicle", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cost_logistics_viaticos", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cost_logistics_personnel", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cost_shrinkage_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("cost_commission_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("cost_marketing", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cost_overhead", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("target_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("estimated_units_month", sa.Integer, nullable=False, server_default="1"),
        sa.Column("sales_channel", sa.String(100), nullable=True),
        sa.Column("exchange_rate_used", sa.Numeric(8, 4), nullable=True),
        sa.Column("exchange_rate_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- agent_results ---
    op.create_table(
        "agent_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("evaluation_id", UUID(as_uuid=True), sa.ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_name", sa.String(30), nullable=False),
        sa.Column("score", sa.SmallInteger, nullable=True),
        sa.Column("veredicto_corto", sa.String(255), nullable=True),
        sa.Column("analisis_extenso", sa.Text, nullable=True),
        sa.Column("hallazgos_clave", JSONB, nullable=False, server_default="[]"),
        sa.Column("recomendaciones", JSONB, nullable=False, server_default="[]"),
        sa.Column("raw_calculations", JSONB, nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.CheckConstraint("score BETWEEN 0 AND 100", name="ck_agent_results_score_range"),
    )
    op.create_index("idx_agent_results_evaluation", "agent_results", ["evaluation_id"])

    # --- chat_messages ---
    op.create_table(
        "chat_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("evaluation_id", UUID(as_uuid=True), sa.ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_messages_role"),
    )
    op.create_index("idx_chat_messages_evaluation", "chat_messages", ["evaluation_id"])

    # --- RLS: ENABLE + FORCE (ADR-008) ---
    for table in ("evaluations", "evaluation_inputs", "agent_results", "chat_messages"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # --- RLS Policies (USING + WITH CHECK) ---
    op.execute("""
        CREATE POLICY eval_rls ON evaluations FOR ALL
        USING      (created_by::text = current_setting('app.user_id', true))
        WITH CHECK (created_by::text = current_setting('app.user_id', true))
    """)
    for table, policy in [
        ("evaluation_inputs", "inputs_rls"),
        ("agent_results", "agent_results_rls"),
        ("chat_messages", "chat_rls"),
    ]:
        op.execute(f"""
            CREATE POLICY {policy} ON {table} FOR ALL
            USING (evaluation_id IN (
                SELECT id FROM evaluations
                WHERE created_by::text = current_setting('app.user_id', true)
            ))
            WITH CHECK (evaluation_id IN (
                SELECT id FROM evaluations
                WHERE created_by::text = current_setting('app.user_id', true)
            ))
        """)

    # --- Trigger updated_at ---
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER evaluations_updated_at
        BEFORE UPDATE ON evaluations
        FOR EACH ROW EXECUTE FUNCTION update_updated_at()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS evaluations_updated_at ON evaluations")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at()")
    for table, policy in [
        ("chat_messages", "chat_rls"),
        ("agent_results", "agent_results_rls"),
        ("evaluation_inputs", "inputs_rls"),
        ("evaluations", "eval_rls"),
    ]:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
    op.drop_table("chat_messages")
    op.drop_table("agent_results")
    op.drop_table("evaluation_inputs")
    op.drop_table("evaluations")
    op.drop_table("app_users")
