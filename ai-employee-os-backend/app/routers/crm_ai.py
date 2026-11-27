import uuid

from fastapi import APIRouter

from app.dependencies.auth import CurrentUser
from app.dependencies.db import DbSession
from app.schemas.common import ApiResponse
from app.schemas.crm_ai import CustomerAIRequest, CustomerAIResponse
from app.services.customer_service import get_customer_or_404
from app.services.crm_ai_service import generate_customer_insights

router = APIRouter(
    prefix="/customers",
    tags=["CRM AI Insights"],
)


@router.post(
    "/{customer_id}/insights",
    response_model=ApiResponse[CustomerAIResponse],
)
def customer_insights(
    customer_id: uuid.UUID,
    actor: CurrentUser,
    db: DbSession,
):
    # Fetch only a customer belonging to the logged-in company
    customer = get_customer_or_404(
        db, actor.company_id, customer_id
    )

    request = CustomerAIRequest(
        name=customer.name,
        organization=customer.organization,
        stage=customer.stage,
        notes=customer.notes,
    )

    result = generate_customer_insights(request)

    return ApiResponse[CustomerAIResponse](
        message="Customer insights generated successfully",
        data=result,
    )