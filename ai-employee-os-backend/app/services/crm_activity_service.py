import uuid

from sqlalchemy.orm import Session

from app.models import Record, User
from app.schemas.crm_activity import ActivityCreate
from app.services.customer_service import get_customer_or_404


def create_activity(
    db: Session,
    actor: User,
    customer_id: uuid.UUID,
    payload: ActivityCreate,
) -> Record:
    # Ensure the customer belongs to the logged-in user's company
    get_customer_or_404(db, actor.company_id, customer_id)

    activity = Record(
        company_id=actor.company_id,
        customer_id=customer_id,
        type="activity",
        title=payload.title,
        status="completed",
        source="manual",
        created_by=actor.id,
        data={
            "activity_type": payload.activity_type,
            "description": payload.description,
        },
    )

    db.add(activity)
    db.commit()
    db.refresh(activity)

    return activity