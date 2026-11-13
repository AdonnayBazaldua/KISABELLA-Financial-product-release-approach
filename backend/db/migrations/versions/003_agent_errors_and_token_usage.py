"""Error de agentes fallidos + consumo real de tokens por evaluacion.

Revision ID: 003
Revises: 002
Create Date: 2026-11-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agent_results", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("evaluations", sa.Column("tokens_input", sa.Integer(), nullable=True))
    op.add_column("evaluations", sa.Column("tokens_output", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("evaluations", "tokens_output")
    op.drop_column("evaluations", "tokens_input")
    op.drop_column("agent_results", "error_message")
