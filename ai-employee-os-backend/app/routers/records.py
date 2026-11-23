import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.dependencies.auth import CurrentUser
from app.dependencies.db import DbSession
from app.dependencies.pagination import Pager
from app.routers.responses import error_responses
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.record import RecordCreate, RecordOut, RecordType, RecordUpdate
from app.services import record_service

router = APIRouter(prefix="/records", tags=["Records"])


@router.get("", response_model=PaginatedResponse[RecordOut],
            summary="List records",
            responses=error_responses(401, 403, 422))
def list_records(
    actor: CurrentUser,
    db: DbSession,
    pager: Pager,
    type: Annotated[RecordType | None, Query()] = None,
    customer_id: Annotated[uuid.UUID | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
):
    records, meta = record_service.list_records(
        db, actor, record_type=type, customer_id=customer_id, search=search, pager=pager
    )
    return PaginatedResponse[RecordOut](
        data=[RecordOut.model_validate(record) for record in records],
        meta=meta,
    )


@router.post("", response_model=ApiResponse[RecordOut], status_code=201,
             summary="Create a record",
             responses=error_responses(401, 403, 409, 422))
def create_record(payload: RecordCreate, actor: CurrentUser, db: DbSession):
    record = record_service.create_record(db, actor, payload)
    return ApiResponse[RecordOut](message="Record created successfully",
                                  data=RecordOut.model_validate(record))


@router.get("/{record_id}", response_model=ApiResponse[RecordOut],
            summary="Get one record",
            responses=error_responses(401, 403, 404, 422))
def get_record(record_id: uuid.UUID, actor: CurrentUser, db: DbSession):
    record = record_service.get_record(db, actor, record_id)
    return ApiResponse[RecordOut](data=RecordOut.model_validate(record))


@router.patch("/{record_id}", response_model=ApiResponse[RecordOut],
              summary="Update a record (partial)",
              responses=error_responses(400, 401, 403, 404, 409, 422))
def update_record(record_id: uuid.UUID, payload: RecordUpdate, actor: CurrentUser, db: DbSession):
    record = record_service.update_record(db, actor, record_id, payload)
    return ApiResponse[RecordOut](message="Record updated successfully",
                                  data=RecordOut.model_validate(record))


@router.delete("/{record_id}", response_model=ApiResponse[None],
               summary="Delete a record",
               responses=error_responses(401, 403, 404))
def delete_record(record_id: uuid.UUID, actor: CurrentUser, db: DbSession):
    record_service.delete_record(db, actor, record_id)
    return ApiResponse[None](message="Record deleted")
