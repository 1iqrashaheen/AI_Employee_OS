import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Record(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "records"

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    reference_no: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="draft"
    )
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="USD"
    )
    data: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id"))
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"))
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="manual"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    __table_args__ = (
        CheckConstraint(
            "type IN ('quotation','invoice','payment','meeting_summary','note','activity')",
            name="type_valid",
        ),
        CheckConstraint("amount IS NULL OR amount >= 0", name="amount_non_negative"),
        CheckConstraint(
            "source IN ('manual','ai_agent','automation')", name="source_valid"
        ),
        Index(
            "uq_records_company_type_reference",
            "company_id",
            "type",
            "reference_no",
            unique=True,
            postgresql_where=text("reference_no IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index("ix_records_company_type", "company_id", "type"),
        Index("ix_records_company_customer", "company_id", "customer_id"),
        Index("ix_records_company_status", "company_id", "status"),
        Index("ix_records_company_created_at", "company_id", "created_at"),
    )