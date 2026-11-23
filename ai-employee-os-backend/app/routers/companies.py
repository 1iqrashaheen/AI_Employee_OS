from fastapi import APIRouter

from app.dependencies.auth import AdminUser, CurrentUser
from app.dependencies.db import DbSession
from app.routers.responses import error_responses
from app.schemas.auth import CompanyOut
from app.schemas.common import ApiResponse
from app.schemas.company import CompanyUpdate
from app.services import company_service

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("/me", response_model=ApiResponse[CompanyOut],
            summary="Get the current user's company",
            responses=error_responses(401, 403, 404))
def get_my_company(actor: CurrentUser, db: DbSession):
    company = company_service.get_company(db, actor.company_id)
    return ApiResponse[CompanyOut](data=CompanyOut.model_validate(company))


@router.patch("/me", response_model=ApiResponse[CompanyOut],
              summary="Update the current company (admin)",
              responses=error_responses(400, 401, 403, 404, 422))
def update_my_company(payload: CompanyUpdate, actor: AdminUser, db: DbSession):
    company = company_service.update_company(db, actor.company_id, payload)
    return ApiResponse[CompanyOut](
        message="Company updated successfully",
        data=CompanyOut.model_validate(company),
    )
