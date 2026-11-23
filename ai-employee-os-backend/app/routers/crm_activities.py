import uuid

from fastapi import APIRouter

from app.dependencies.auth import CurrentUser
from app.dependencies.db import DbSession
from app.schemas.common import ApiResponse
from app.schemas.crm_activity import ActivityCreate, ActivityOut
from app.services.crm_activity_service import create_activity

router = APIRouter(
    prefix="/customers",
    tags=["CRM Activities"],
)


@router.post(
    "/{customer_id}/activities",
    response_model=ApiResponse[ActivityOut],
    status_code=201,
)
def add_customer_activity(
    customer_id: uuid.UUID,
    payload: ActivityCreate,
    actor: CurrentUser,
    db: DbSession,
):
    activity = create_activity(
        db=db,
        actor=actor,
        customer_id=customer_id,
        payload=payload,
    )

    result = ActivityOut(
        id=activity.id,
        customer_id=activity.customer_id,
        activity_type=activity.data["activity_type"],
        title=activity.title,
        description=activity.data.get("description"),
        created_at=activity.created_at,
    )

    return ApiResponse[ActivityOut](
        message="Customer activity created successfully",
        data=result,
    )