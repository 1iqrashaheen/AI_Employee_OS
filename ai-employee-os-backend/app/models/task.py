import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Task(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "tasks"

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="todo"
    )
    priority: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="medium"
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remind_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id"))
    # tasks <-> records point at each other, so this FK is created separately
    # in the migration (see Step 9). use_alter + name tells SQLAlchemy about that.
    record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("records.id", use_alter=True, name="fk_tasks_record_id_records")
    )

    source: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="manual"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    __table_args__ = (
        CheckConstraint(
            "status IN ('todo','in_progress','done','cancelled')", name="status_valid"
        ),
        CheckConstraint(
            "priority IN ('low','medium','high','urgent')", name="priority_valid"
        ),
        CheckConstraint(
            "source IN ('manual','ai_agent','automation')", name="source_valid"
        ),
        Index("ix_tasks_company_status", "company_id", "status"),
        Index("ix_tasks_company_assignee", "company_id", "assignee_id"),
        Index("ix_tasks_company_customer", "company_id", "customer_id"),
        Index("ix_tasks_company_due_date", "company_id", "due_date"),
    )