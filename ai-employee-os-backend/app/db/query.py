"""Helpers shared by every list endpoint: safe text search, whitelisted sorting, pagination."""
import math
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import UnprocessableError
from app.schemas.common import PageMeta


@dataclass(frozen=True)
class Pagination:
    page: int
    limit: int
    sort: str | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


def escape_like(value: str) -> str:
    """Make %, _ and \\ in user input match literally instead of acting as wildcards."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def contains(column: Any, term: str):
    """Case-insensitive 'column contains term'."""
    return column.ilike(f"%{escape_like(term.strip())}%", escape="\\")


def apply_sort(stmt: Select, sort: str | None, allowed: dict[str, Any], *, default: str, tiebreaker: Any) -> Select:
    """
    Apply ?sort=field or ?sort=-field using ONLY fields in `allowed`.
    `tiebreaker` (the id column) keeps page boundaries stable when many rows share a value.
    """
    value = sort or default
    descending = value.startswith("-")
    key = value[1:] if descending else value

    if key not in allowed:
        raise UnprocessableError(
            errors=[{
                "field": "sort",
                "message": f"Sort by one of: {', '.join(sorted(allowed))} (prefix with - for descending)",
            }]
        )
    expression = allowed[key]
    ordering = expression.desc().nulls_last() if descending else expression.asc().nulls_last()
    return stmt.order_by(ordering, tiebreaker)


def paginate(db: Session, stmt: Select, pager: Pagination) -> tuple[list[Any], PageMeta]:
    """Run the count and the page query; return (items, meta)."""
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = list(db.scalars(stmt.limit(pager.limit).offset(pager.offset)).unique())
    meta = PageMeta(
        page=pager.page,
        limit=pager.limit,
        total=total,
        total_pages=math.ceil(total / pager.limit),
    )
    return items, meta