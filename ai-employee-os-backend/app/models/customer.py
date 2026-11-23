import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column,relationship

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from app.models.user import User

class Customer(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "customers"

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(30))
    organization: Mapped[str | None] = mapped_column(String(150))
    address: Mapped[str | None] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="lead"
    )
    source: Mapped[str | None] = mapped_column(String(30))
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)), nullable=False, server_default=text("'{}'")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


        # Read-only link used to show the owner's name. We still WRITE through owner_id.
    owner: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys="Customer.owner_id", viewonly=True
    )
    
    __table_args__ = (
        CheckConstraint(
            "stage IN ('lead','qualified','proposal','negotiation','won','lost')",
            name="stage_valid",
        ),
        # No duplicate email inside one company (ignores empty emails and deleted rows)
        Index(
            "uq_customers_company_email",
            "company_id",
            "email",
            unique=True,
            postgresql_where=text("email IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index("ix_customers_company_stage", "company_id", "stage"),
        Index("ix_customers_company_name", "company_id", "name"),
        Index("ix_customers_company_owner", "company_id", "owner_id"),
    )