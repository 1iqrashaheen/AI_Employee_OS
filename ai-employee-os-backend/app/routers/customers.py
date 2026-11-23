"""Customer (CRM) endpoints. All paths are under /api/v1/customers."""
import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.dependencies.auth import CurrentUser, ManagerOrAdmin
from app.dependencies.db import DbSession
from app.dependencies.pagination import Pager
from app.routers.responses import error_responses
from app.schemas.common import ApiResponse, PageMeta, PaginatedResponse
from app.schemas.customer import CustomerCreate, CustomerOut, CustomerStage, CustomerUpdate, TimelineItem
from app.services import customer_service

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("", response_model=PaginatedResponse[CustomerOut],
            summary="List customers", responses=error_responses(401, 403, 422))
def list_customers(
    actor: CurrentUser, db: DbSession, pager: Pager,
    search: Annotated[str | None, Query(max_length=100, description="Matches name, email, organization, phone")] = None,
    stage: Annotated[list[CustomerStage] | None, Query(description="Repeat for several: ?stage=lead&stage=qualified")] = None,
    owner_id: Annotated[uuid.UUID | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=30)] = None,
    tag: Annotated[str | None, Query(max_length=50)] = None,
):
    customers, meta = customer_service.list_customers(
        db, actor.company_id, search=search, stages=stage, owner_id=owner_id,
        source=source, tag=tag, pager=pager,
    )
    return PaginatedResponse[CustomerOut](data=[CustomerOut.model_validate(c) for c in customers], meta=meta)


@router.post("", response_model=ApiResponse[CustomerOut], status_code=201,
             summary="Create a customer or lead", responses=error_responses(401, 403, 409, 422))
def create_customer(payload: CustomerCreate, actor: CurrentUser, db: DbSession):
    customer = customer_service.create_customer(db, actor, payload)
    return ApiResponse[CustomerOut](message="Customer created successfully", data=CustomerOut.model_validate(customer))


@router.get("/{customer_id}", response_model=ApiResponse[CustomerOut],
            summary="Get one customer", responses=error_responses(401, 403, 404, 422))
def get_customer(customer_id: uuid.UUID, actor: CurrentUser, db: DbSession):
    customer = customer_service.get_customer_or_404(db, actor.company_id, customer_id)
    return ApiResponse[CustomerOut](data=CustomerOut.model_validate(customer))


@router.patch("/{customer_id}", response_model=ApiResponse[CustomerOut],
              summary="Update a customer (partial)", responses=error_responses(400, 401, 403, 404, 409, 422))
def update_customer(customer_id: uuid.UUID, payload: CustomerUpdate, actor: CurrentUser, db: DbSession):
    customer = customer_service.update_customer(db, actor, customer_id, payload)
    return ApiResponse[CustomerOut](message="Customer updated successfully", data=CustomerOut.model_validate(customer))


@router.delete("/{customer_id}", response_model=ApiResponse[None],
               summary="Delete a customer (admin, manager)", responses=error_responses(401, 403, 404))
def delete_customer(customer_id: uuid.UUID, actor: ManagerOrAdmin, db: DbSession):
    customer_service.delete_customer(db, actor, customer_id)
    return ApiResponse[None](message="Customer deleted")

@router.get("/{customer_id}/timeline", response_model=PaginatedResponse[TimelineItem],
            summary="Customer history: tasks and records, newest first",
            responses=error_responses(401, 403, 404, 422))
def customer_timeline(customer_id: uuid.UUID, actor: CurrentUser, db: DbSession, pager: Pager):
    rows, total = customer_service.get_timeline(db, actor.company_id, customer_id, pager)
    meta = PageMeta(page=pager.page, limit=pager.limit, total=total,
                    total_pages=math.ceil(total / pager.limit))
    items = [
        TimelineItem(kind=r.kind, id=r.id, type=r.type, title=r.title, status=r.status, at=r.at)
        for r in rows
    ]
    return PaginatedResponse[TimelineItem](data=items, meta=meta)