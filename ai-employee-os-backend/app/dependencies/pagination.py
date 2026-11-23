from typing import Annotated

from fastapi import Depends, Query

from app.db.query import Pagination


def get_pagination(
    page: Annotated[int, Query(ge=1, description="Page number, starting at 1")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page (1 to 100)")] = 20,
    sort: Annotated[
        str | None,
        Query(max_length=50, description="Field to sort by; prefix with - for descending, e.g. -created_at"),
    ] = None,
) -> Pagination:
    return Pagination(page=page, limit=limit, sort=sort)


# Use `pager: Pager` in a list endpoint.
Pager = Annotated[Pagination, Depends(get_pagination)]