import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError, PermissionDeniedError, UnprocessableError
from app.db.query import Pagination, apply_sort, contains, paginate
from app.models import Customer, Record, Task, User
from app.schemas.record import RecordCreate, RecordUpdate

logger = logging.getLogger("app.records")

RECORD_SORT_FIELDS = {
    "created_at": Record.created_at,
    "updated_at": Record.updated_at,
    "type": Record.type,
    "status": Record.status,
    "amount": Record.amount,
}


def _get_record_or_404(db: Session, company_id: uuid.UUID, record_id: uuid.UUID) -> Record:
    record = db.scalar(select(Record).where(
        Record.id == record_id,
        Record.company_id == company_id,
        Record.deleted_at.is_(None),
    ))
    if record is None:
        raise NotFoundError("Record not found", code="RECORD_NOT_FOUND")
    return record


def _validate_links(db: Session, company_id: uuid.UUID, customer_id: uuid.UUID,
                    task_id: uuid.UUID | None = None) -> None:
    errors: list[dict[str, str]] = []

    customer = db.scalar(select(Customer.id).where(
        Customer.id == customer_id,
        Customer.company_id == company_id,
        Customer.deleted_at.is_(None),
    ))
    if customer is None:
        errors.append({"field": "customer_id", "message": "Customer not found in your company"})

    if task_id is not None:
        task = db.scalar(select(Task.id).where(
            Task.id == task_id,
            Task.company_id == company_id,
            Task.deleted_at.is_(None),
            Task.customer_id == customer_id,
        ))
        if task is None:
            errors.append({"field": "task_id", "message": "Task must belong to the same customer and your company"})

    if errors:
        raise UnprocessableError(errors=errors)


def list_records(db: Session, actor: User, *, record_type: str | None, customer_id: uuid.UUID | None,
                 search: str | None, pager: Pagination):
    conditions = [Record.company_id == actor.company_id, Record.deleted_at.is_(None)]
    if record_type:
        conditions.append(Record.type == record_type)
    if customer_id:
        conditions.append(Record.customer_id == customer_id)
    if search:
        conditions.append(or_(contains(Record.title, search), contains(Record.reference_no, search)))

    stmt = apply_sort(
        select(Record).where(*conditions),
        pager.sort,
        RECORD_SORT_FIELDS,
        default="-created_at",
        tiebreaker=Record.id,
    )
    return paginate(db, stmt, pager)


def get_record(db: Session, actor: User, record_id: uuid.UUID) -> Record:
    return _get_record_or_404(db, actor.company_id, record_id)


def create_record(db: Session, actor: User, data: RecordCreate) -> Record:
    _validate_links(db, actor.company_id, data.customer_id, data.task_id)
    record = Record(
        company_id=actor.company_id,
        created_by=actor.id,
        currency=data.currency.upper(),
        **data.model_dump(exclude={"currency"}),
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("A record with this reference already exists",
                            code="RECORD_REFERENCE_EXISTS") from None
    db.refresh(record)
    logger.info("Record created: id=%s company=%s", record.id, actor.company_id)
    return record


def update_record(db: Session, actor: User, record_id: uuid.UUID, data: RecordUpdate) -> Record:
    record = _get_record_or_404(db, actor.company_id, record_id)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise BadRequestError("Provide at least one field to update", code="NO_FIELDS_TO_UPDATE")

    customer_id = changes.get("customer_id", record.customer_id)
    task_id = changes.get("task_id", record.task_id)
    if customer_id is not None:
        _validate_links(db, actor.company_id, customer_id, task_id)

    if "currency" in changes:
        changes["currency"] = changes["currency"].upper()

    for field, value in changes.items():
        setattr(record, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("A record with this reference already exists",
                            code="RECORD_REFERENCE_EXISTS") from None
    db.refresh(record)
    return record


def delete_record(db: Session, actor: User, record_id: uuid.UUID) -> None:
    record = _get_record_or_404(db, actor.company_id, record_id)
    if actor.role == "member" and record.created_by != actor.id:
        raise PermissionDeniedError("Members can only delete records they created")
    record.deleted_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Record deleted: id=%s by user=%s", record.id, actor.id)
