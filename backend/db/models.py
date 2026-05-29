import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Numeric, Integer, Text, DateTime, ForeignKey, JSON, SmallInteger, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AppUser(Base):
    __tablename__ = "app_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    evaluations: Mapped[list["Evaluation"]] = relationship(back_populates="user")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("app_users.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    final_verdict: Mapped[str | None] = mapped_column(String(30), nullable=True)
    final_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    final_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    warn_flags: Mapped[list] = mapped_column(JSON, default=list)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False)
    idempotency_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user: Mapped["AppUser"] = relationship(back_populates="evaluations")
    inputs: Mapped["EvaluationInput"] = relationship(back_populates="evaluation", uselist=False)
    agent_results: Mapped[list["AgentResult"]] = relationship(back_populates="evaluation")
    chat_messages: Mapped[list["ChatMessage"]] = relationship(back_populates="evaluation", cascade="all, delete-orphan")


class EvaluationInput(Base):
    __tablename__ = "evaluation_inputs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"))
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(20), default="fisico")
    cost_purchase: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    cost_purchase_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    cost_freight: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    cost_customs: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    cost_storage: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    cost_logistics_vehicle: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    cost_logistics_viaticos: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    cost_logistics_personnel: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    cost_shrinkage_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    cost_commission_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    cost_marketing: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    cost_overhead: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    target_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    estimated_units_month: Mapped[int] = mapped_column(Integer, default=1)
    sales_channel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exchange_rate_used: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    exchange_rate_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    evaluation: Mapped["Evaluation"] = relationship(back_populates="inputs")


class AgentResult(Base):
    __tablename__ = "agent_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"))
    agent_name: Mapped[str] = mapped_column(String(30), nullable=False)
    score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    veredicto_corto: Mapped[str | None] = mapped_column(String(255), nullable=True)
    analisis_extenso: Mapped[str | None] = mapped_column(Text, nullable=True)
    hallazgos_clave: Mapped[list] = mapped_column(JSON, default=list)
    recomendaciones: Mapped[list] = mapped_column(JSON, default=list)
    raw_calculations: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    evaluation: Mapped["Evaluation"] = relationship(back_populates="agent_results")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="complete")
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    evaluation: Mapped["Evaluation"] = relationship(back_populates="chat_messages")
    attachments: Mapped[list["ChatAttachment"]] = relationship(back_populates="message", cascade="all, delete-orphan")


class ChatAttachment(Base):
    __tablename__ = "chat_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    markdown_extracted: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    message: Mapped["ChatMessage"] = relationship(back_populates="attachments")
