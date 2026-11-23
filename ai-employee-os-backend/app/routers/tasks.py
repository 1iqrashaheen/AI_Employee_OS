"""Task endpoints. All paths are under /api/v1/tasks."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime

from app.dependencies.auth import CurrentUser
from app.dependencies.db import DbSession
from app.dependencies.pagination import Pager
from app.routers.responses import error_responses
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.task import (
    TaskCreate,
    TaskFilters,
    TaskOut,
    TaskPriority,
    TaskStatus,
    TaskUpdate,
)
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def get_task_filters(
    status: Annotated[list[TaskStatus] | None, Query(description="Repeat for several: ?status=todo&status=in_progress")] = None,
    priority: Annotated[list[TaskPriority] | None, Query(description="Repeat for several")] = None,
    assignee_id: Annotated[uuid.UUID | None, Query()] = None,
    mine: Annotated[bool, Query(description="Only tasks assigned to me")] = False,
    customer_id: Annotated[uuid.UUID | None, Query()] = None,
    due_before: Annotated[AwareDatetime | None, Query(description="e.g. 2026-11-30T00:00:00Z")] = None,
    due_after: Annotated[AwareDatetime | None, Query(description="e.g. 2026-11-01T00:00:00Z")] = None,
    overdue: Annotated[bool, Query(description="Deadline passed and still todo / in_progress")] = False,
    search: Annotated[str | None, Query(max_length=100, description="Matches title or description")] = None,
) -> TaskFilters:
    return TaskFilters(
        statuses=status, priorities=priority, assignee_id=assignee_id, mine=mine,
        customer_id=customer_id, due_before=due_before, due_after=due_after,
        overdue=overdue, search=search,
    )


@router.get("", response_model=PaginatedResponse[TaskOut], summary="List tasks",
            responses=error_responses(401, 403, 422))
def list_tasks(actor: CurrentUser, db: DbSession, pager: Pager,
               filters: Annotated[TaskFilters, Depends(get_task_filters)]):
    tasks, meta = task_service.list_tasks(db, actor, filters, pager)
    return PaginatedResponse[TaskOut](data=[TaskOut.model_validate(t) for t in tasks], meta=meta)


@router.post("", response_model=ApiResponse[TaskOut], status_code=201, summary="Create a task",
             responses=error_responses(401, 403, 422))
def create_task(payload: TaskCreate, actor: CurrentUser, db: DbSession):
    task = task_service.create_task(db, actor, payload)
    return ApiResponse[TaskOut](message="Task created successfully", data=TaskOut.model_validate(task))


@router.get("/{task_id}", response_model=ApiResponse[TaskOut], summary="Get one task",
            responses=error_responses(401, 403, 404, 422))
def get_task(task_id: uuid.UUID, actor: CurrentUser, db: DbSession):
    task = task_service.get_task_or_404(db, actor.company_id, task_id)
    return ApiResponse[TaskOut](data=TaskOut.model_validate(task))


@router.patch("/{task_id}", response_model=ApiResponse[TaskOut], summary="Update a task (partial)",
              responses=error_responses(400, 401, 403, 404, 422))
def update_task(task_id: uuid.UUID, payload: TaskUpdate, actor: CurrentUser, db: DbSession):
    task = task_service.update_task(db, actor, task_id, payload)
    return ApiResponse[TaskOut](message="Task updated successfully", data=TaskOut.model_validate(task))


@router.delete("/{task_id}", response_model=ApiResponse[None],
               summary="Delete a task (admin, manager, or the creator)",
               responses=error_responses(401, 403, 404))
def delete_task(task_id: uuid.UUID, actor: CurrentUser, db: DbSession):
    task_service.delete_task(db, actor, task_id)
    return ApiResponse[None](message="Task deleted")