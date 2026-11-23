"""User management rules (who may see, edit, create or deactivate whom)."""
import logging
import uuid

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from app.core.security import hash_password
from app.db.query import Pagination, apply_sort, contains, paginate
from app.models import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.auth_service import get_user_by_email

logger = logging.getLogger("app.users")

USER_SORT_FIELDS = {
    "created_at": User.created_at,
    "full_name": User.full_name,
    "email": User.email,
    "role": User.role,
}


def _get_user_or_404(db: Session, company_id: uuid.UUID, user_id: uuid.UUID) -> User:
    """Always scoped to the caller's company: another company's user looks like it doesn't exist."""
    user = db.scalar(select(User).where(User.id == user_id, User.company_id == company_id))
    if user is None:
        raise NotFoundError("User not found", code="USER_NOT_FOUND")
    return user


def list_users(db: Session, actor: User, *, search: str | None, role: str | None,
               is_active: bool | None, pager: Pagination):
    conditions = [User.company_id == actor.company_id]
    if search:
        conditions.append(or_(contains(User.full_name, search), contains(User.email, search)))
    if role:
        conditions.append(User.role == role)
    if is_active is not None:
        conditions.append(User.is_active.is_(is_active))

    stmt = apply_sort(select(User).where(*conditions), pager.sort, USER_SORT_FIELDS,
                      default="full_name", tiebreaker=User.id)
    return paginate(db, stmt, pager)


def list_directory(db: Session, actor: User, *, search: str | None, pager: Pagination):
    """Active users, names only: lets ANY role fill an assignee dropdown without seeing emails."""
    conditions = [User.company_id == actor.company_id, User.is_active.is_(True)]
    if search:
        conditions.append(contains(User.full_name, search))
    stmt = apply_sort(select(User).where(*conditions), "full_name", USER_SORT_FIELDS,
                      default="full_name", tiebreaker=User.id)
    return paginate(db, stmt, pager)


def get_user(db: Session, actor: User, user_id: uuid.UUID) -> User:
    target = _get_user_or_404(db, actor.company_id, user_id)
    if actor.role == "member" and actor.id != target.id:
        raise PermissionDeniedError("You can only view your own profile")
    return target


def create_user(db: Session, actor: User, data: UserCreate) -> User:
    if get_user_by_email(db, data.email) is not None:
        raise ConflictError("An account with this email already exists", code="EMAIL_ALREADY_REGISTERED")

    password_hash = hash_password(data.password)  # slow: do it before the transaction
    user = User(
        company_id=actor.company_id,  # ALWAYS the caller's company, never from the request body
        full_name=data.full_name,
        email=data.email,
        password_hash=password_hash,
        role=data.role,
        phone=data.phone,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two admins creating the same email at the same moment
        db.rollback()
        raise ConflictError("An account with this email already exists",
                            code="EMAIL_ALREADY_REGISTERED") from None
    db.refresh(user)
    logger.info("User created: user_id=%s by admin_id=%s role=%s", user.id, actor.id, user.role)
    return user


def update_user(db: Session, actor: User, user_id: uuid.UUID, data: UserUpdate) -> User:
    target = _get_user_or_404(db, actor.company_id, user_id)
    changes = data.model_dump(exclude_unset=True)  # only the fields the client actually sent
    if not changes:
        raise BadRequestError("Provide at least one field to update", code="NO_FIELDS_TO_UPDATE")

    is_admin = actor.role == "admin"
    is_self = actor.id == target.id

    if not is_admin and not is_self:
        raise PermissionDeniedError("You can only edit your own profile")
    if not is_admin and {"role", "is_active"} & changes.keys():
        raise PermissionDeniedError("Only an admin can change a role or the active status")
    # These two rules guarantee a company never ends up without an admin.
    if is_self and "role" in changes and changes["role"] != target.role:
        raise BadRequestError("You cannot change your own role", code="SELF_ROLE_CHANGE_NOT_ALLOWED")
    if is_self and changes.get("is_active") is False:
        raise BadRequestError("You cannot deactivate your own account", code="SELF_DEACTIVATION_NOT_ALLOWED")

    was_active = target.is_active
    for field, value in changes.items():
        setattr(target, field, value)
    if was_active and not target.is_active:
        target.token_version += 1  # signs the user out everywhere, immediately

    db.commit()
    db.refresh(target)
    return target


def deactivate_user(db: Session, actor: User, user_id: uuid.UUID) -> User:
    target = _get_user_or_404(db, actor.company_id, user_id)
    if target.id == actor.id:
        raise BadRequestError("You cannot deactivate your own account", code="SELF_DEACTIVATION_NOT_ALLOWED")
    if target.is_active:
        target.is_active = False
        target.token_version += 1
        db.commit()
        db.refresh(target)
        logger.info("User deactivated: user_id=%s by admin_id=%s", target.id, actor.id)
    return target