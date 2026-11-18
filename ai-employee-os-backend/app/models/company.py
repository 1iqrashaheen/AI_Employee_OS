from sqlalchemy import Boolean, CheckConstraint, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(30))
    plan: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="basic"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    __table_args__ = (
        CheckConstraint("plan IN ('basic','pro','business')", name="plan_valid"),
    )