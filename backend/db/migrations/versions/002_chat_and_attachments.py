"""chat_messages completado + tabla chat_attachments + RLS.

Revision ID: 002
Revises: 001
Create Date: 2026-05-29

Cambios:
- ADD COLUMN IF NOT EXISTS en chat_messages: status, error_msg, updated_at
- Índice compuesto (evaluation_id, created_at) en chat_messages
- GRANT SELECT/INSERT/UPDATE/DELETE sobre chat_messages a capi_app
- Nueva tabla chat_attachments con RLS completo
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 1. ADD missing columns to chat_messages (idempotent via IF NOT EXISTS)
    # ------------------------------------------------------------------ #
    op.execute("""
        ALTER TABLE chat_messages
            ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'complete'
                CONSTRAINT ck_chat_messages_status CHECK (status IN ('complete', 'streaming', 'error')),
            ADD COLUMN IF NOT EXISTS error_msg TEXT,
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    """)

    # ------------------------------------------------------------------ #
    # 2. Composite index on chat_messages(evaluation_id, created_at)
    # ------------------------------------------------------------------ #
    op.create_index(
        "idx_chat_messages_eval_created",
        "chat_messages",
        ["evaluation_id", "created_at"],
    )

    # ------------------------------------------------------------------ #
    # 3. GRANT on chat_messages to capi_app (non-owner role, ADR-008)
    #    RLS ENABLE + FORCE were already applied in migration 001.
    #    Policy chat_rls was also created in 001 — no duplicate needed.
    # ------------------------------------------------------------------ #
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON chat_messages TO capi_app")

    # ------------------------------------------------------------------ #
    # 4. Create table chat_attachments
    # ------------------------------------------------------------------ #
    op.create_table(
        "chat_attachments",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "message_id",
            UUID(as_uuid=True),
            sa.ForeignKey("chat_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evaluation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_path", sa.Text, nullable=False),
        sa.Column("markdown_extracted", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    # ------------------------------------------------------------------ #
    # 5. Index on chat_attachments(message_id)
    # ------------------------------------------------------------------ #
    op.create_index(
        "idx_chat_attachments_message",
        "chat_attachments",
        ["message_id"],
    )

    # ------------------------------------------------------------------ #
    # 6. RLS on chat_attachments (ADR-008: ENABLE + FORCE + policy + GRANT)
    # ------------------------------------------------------------------ #
    op.execute("ALTER TABLE chat_attachments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_attachments FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY chat_attachments_owner ON chat_attachments
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
        )
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON chat_attachments TO capi_app")


def downgrade() -> None:
    # Drop chat_attachments entirely
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON chat_attachments FROM capi_app")
    op.execute("DROP POLICY IF EXISTS chat_attachments_owner ON chat_attachments")
    op.drop_index("idx_chat_attachments_message", table_name="chat_attachments")
    op.drop_table("chat_attachments")

    # Revert chat_messages additions
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON chat_messages FROM capi_app")
    op.drop_index("idx_chat_messages_eval_created", table_name="chat_messages")
    op.execute("ALTER TABLE chat_messages DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE chat_messages DROP COLUMN IF EXISTS error_msg")
    op.execute("ALTER TABLE chat_messages DROP COLUMN IF EXISTS status")
