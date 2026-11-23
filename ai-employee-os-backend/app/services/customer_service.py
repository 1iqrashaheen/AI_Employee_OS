"""Customer (CRM) business rules."""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select,String, cast, func, literal_column, null, select, union_all
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from app.models import Customer, Record, Task, User

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    UnprocessableError,
)
from app.db.query import Pagination, apply_sort, contains, paginate
from app.models import Customer, User
from app.schemas.customer import CustomerCreate, CustomerUpdate

logger = logging.getLogger("app.customers")

CUSTOMER_SORT_FIELDS = {
    "created_at": Customer.created_at,
    "updated_at": Customer.updated_at,
    "name": Customer.name,
    "stage": Customer.stage,
}


def _visible(company_id: uuid.UUID) -> list:
    """Conditions every customer query must have: my company, and not soft-deleted."""
    return [Customer.company_id == company_id, Customer.deleted_at.is_(None)]


def get_customer_or_404(db: Session, company_id: uuid.UUID, customer_id: uuid.UUID) -> Customer:
    stmt = (
        select(Customer)
        .options(joinedload(Customer.owner))  # fetch the owner in the same query (no N+1)
        .where(Customer.id == customer_id, *_visible(company_id))
    )
    customer = db.scalar(stmt)
    if customer is None:
        raise NotFoundError("Customer not found", code="CUSTOMER_NOT_FOUND")
    return customer


def _ensure_owner_valid(db: Session, company_id: uuid.UUID, owner_id: uuid.UUID) -> None:
    owner = db.get(User, owner_id)
    if owner is None or owner.company_id != company_id or not owner.is_active:
        raise UnprocessableError(
            errors=[{"field": "owner_id", "message": "Owner must be an active user of your company"}]
        )


def _ensure_email_free(db: Session, company_id: uuid.UUID, email: str,
                       exclude_id: uuid.UUID | None = None) -> None:
    stmt = select(Customer.id).where(Customer.email == email, *_visible(company_id))
    if exclude_id is not None:
        stmt = stmt.where(Customer.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise ConflictError("A customer with this email already exists", code="CUSTOMER_EMAIL_EXISTS")


def list_customers(db: Session, company_id: uuid.UUID, *, search: str | None, stages: list[str] | None,
                   owner_id: uuid.UUID | None, source: str | None, tag: str | None, pager: Pagination):
    conditions = _visible(company_id)
    if search:
        conditions.append(or_(
            contains(Customer.name, search),
            contains(Customer.email, search),
            contains(Customer.organization, search),
            contains(Customer.phone, search),
        ))
    if stages:
        conditions.append(Customer.stage.in_(stages))
    if owner_id:
        conditions.append(Customer.owner_id == owner_id)
    if source:
        conditions.append(Customer.source == source.strip().lower())
    if tag:
        conditions.append(Customer.tags.contains([tag.strip().lower()]))  # array contains

    stmt = select(Customer).options(joinedload(Customer.owner)).where(*conditions)
    stmt = apply_sort(stmt, pager.sort, CUSTOMER_SORT_FIELDS, default="-created_at", tiebreaker=Customer.id)
    return paginate(db, stmt, pager)


def create_customer(db: Session, actor: User, data: CustomerCreate) -> Customer:
    if data.email:
        _ensure_email_free(db, actor.company_id, data.email)
    if data.owner_id:
        _ensure_owner_valid(db, actor.company_id, data.owner_id)

    customer = Customer(company_id=actor.company_id, created_by=actor.id, **data.model_dump())
    db.add(customer)
    try:
        db.commit()
    except IntegrityError:  # the partial unique index caught a race between two requests
        db.rollback()
        raise ConflictError("A customer with this email already exists",
                            code="CUSTOMER_EMAIL_EXISTS") from None
    logger.info("Customer created: id=%s company=%s", customer.id, actor.company_id)
    return get_customer_or_404(db, actor.company_id, customer.id)


def update_customer(db: Session, actor: User, customer_id: uuid.UUID, data: CustomerUpdate) -> Customer:
    customer = get_customer_or_404(db, actor.company_id, customer_id)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise BadRequestError("Provide at least one field to update", code="NO_FIELDS_TO_UPDATE")

    if changes.get("email"):
        _ensure_email_free(db, actor.company_id, changes["email"], exclude_id=customer.id)
    if changes.get("owner_id"):
        _ensure_owner_valid(db, actor.company_id, changes["owner_id"])

    for field, value in changes.items():
        setattr(customer, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("A customer with this email already exists",
                            code="CUSTOMER_EMAIL_EXISTS") from None
    return get_customer_or_404(db, actor.company_id, customer.id)


def delete_customer(db: Session, actor: User, customer_id: uuid.UUID) -> None:
    """Soft delete: hidden from the API, kept in the database (tasks and records still refer to it)."""
    customer = get_customer_or_404(db, actor.company_id, customer_id)
    customer.deleted_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Customer deleted: id=%s by user=%s", customer.id, actor.id)

def get_timeline(db: Session, company_id: uuid.UUID, customer_id: uuid.UUID, pager: Pagination):
    """A customer's tasks and records merged into ONE list, newest first (database-side UNION)."""
    get_customer_or_404(db, company_id, customer_id)  # 404 if missing, deleted or another company's

    tasks_q = select(
        literal_column("'task'", String).label("kind"),
        Task.id.label("id"),
        cast(null(), String(30)).label("type"),
        Task.title.label("title"),
        Task.status.label("status"),
        Task.created_at.label("at"),
    ).where(Task.company_id == company_id, Task.customer_id == customer_id, Task.deleted_at.is_(None))

    records_q = select(
        literal_column("'record'", String).label("kind"),
        Record.id.label("id"),
        Record.type.label("type"),
        func.coalesce(Record.title, Record.reference_no, Record.type).label("title"),
        Record.status.label("status"),
        Record.created_at.label("at"),
    ).where(Record.company_id == company_id, Record.customer_id == customer_id, Record.deleted_at.is_(None))

    combined = union_all(tasks_q, records_q).subquery()

    total = db.scalar(select(func.count()).select_from(combined)) or 0
    rows = db.execute(
        select(combined).order_by(combined.c.at.desc(), combined.c.id)
        .limit(pager.limit).offset(pager.offset)
    ).all()
    return rows, total