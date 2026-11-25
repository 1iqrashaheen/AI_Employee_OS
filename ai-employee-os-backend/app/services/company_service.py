import logging

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.models import Company
from app.schemas.company import CompanyUpdate

logger = logging.getLogger("app.companies")


def get_company(db: Session, company_id) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise NotFoundError("Company not found", code="COMPANY_NOT_FOUND")
    return company


def update_company(db: Session, company_id, data: CompanyUpdate) -> Company:
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise BadRequestError("Provide at least one field to update", code="NO_FIELDS_TO_UPDATE")

    company = get_company(db, company_id)
    for field, value in changes.items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    logger.info("Company updated: company_id=%s", company.id)
    return company
