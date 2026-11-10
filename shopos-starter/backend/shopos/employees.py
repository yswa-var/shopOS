from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from shopos.audit import record_event
from shopos.auth import Db, require_owner
from shopos.models import AuthSession, User, UserPermission
from shopos.security import hash_password, normalize_username

router = APIRouter(prefix="/employees", tags=["employees"])
Owner = Annotated[User, Depends(require_owner)]

# Keep the grant catalog here so owner screens cannot invent permissions.
PERMISSION_LABELS = {
    "catalog:read": "Find vendors and items",
    "catalog:write": "Add vendors, items, and aliases",
    "bills:create": "Record purchase bills",
    "bills:read": "Find bills and linked proofs",
    "attachments:write": "Upload proof photos",
    "attachments:read": "View own unlinked uploads",
}
DEFAULT_PERMISSIONS = ["catalog:read", "catalog:write", "bills:create", "bills:read", "attachments:write", "attachments:read"]


class PermissionInfo(BaseModel):
    key: str
    label: str
    default: bool


class EmployeeCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=12, max_length=256)
    permissions: list[str] = Field(default_factory=lambda: DEFAULT_PERMISSIONS.copy())


class PermissionUpdate(BaseModel):
    permissions: list[str]


class StatusUpdate(BaseModel):
    is_active: bool


class PasswordUpdate(BaseModel):
    password: str = Field(min_length=12, max_length=256)


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)


class EmployeeResponse(BaseModel):
    id: UUID
    username: str
    display_name: str
    is_active: bool
    permissions: list[str]
    created_at: datetime


def clean_display_name(value: str) -> str:
    name = " ".join(value.split())
    if not name or len(name) > 100:
        raise HTTPException(status_code=422, detail="Display name must be 1–100 characters")
    return name


def valid_permissions(values: list[str]) -> set[str]:
    if len(values) != len(set(values)) or set(values) - PERMISSION_LABELS.keys():
        raise HTTPException(status_code=422, detail="Unknown or duplicate permission")
    return set(values)


def employee_response(user: User) -> EmployeeResponse:
    return EmployeeResponse(id=user.id, username=user.username, display_name=user.display_name, is_active=user.is_active, permissions=sorted(entry.permission for entry in user.permissions), created_at=user.created_at)


def get_employee(db: Db, employee_id: UUID) -> User:
    user = db.scalar(select(User).options(selectinload(User.permissions)).where(User.id == employee_id, User.role == "employee"))
    if user is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return user


def revoke_sessions(db: Db, employee_id: UUID) -> None:
    db.execute(update(AuthSession).where(AuthSession.user_id == employee_id, AuthSession.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))


@router.get("/permissions", response_model=list[PermissionInfo])
def permissions(_owner: Owner) -> list[PermissionInfo]:
    return [PermissionInfo(key=key, label=label, default=key in DEFAULT_PERMISSIONS) for key, label in PERMISSION_LABELS.items()]


@router.get("", response_model=list[EmployeeResponse])
def list_employees(db: Db, _owner: Owner) -> list[EmployeeResponse]:
    users = db.scalars(select(User).options(selectinload(User.permissions)).where(User.role == "employee").order_by(User.created_at.desc(), User.username)).all()
    return [employee_response(user) for user in users]


@router.post("", status_code=201, response_model=EmployeeResponse)
def create_employee(payload: EmployeeCreate, db: Db, owner: Owner) -> EmployeeResponse:
    try:
        username = normalize_username(payload.username)
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    grants = valid_permissions(payload.permissions)
    employee = User(username=username, display_name=clean_display_name(payload.display_name), password_hash=password_hash, role="employee")
    employee.permissions = [UserPermission(permission=permission) for permission in sorted(grants)]
    db.add(employee)
    try:
        db.flush()
        record_event(db, actor_id=owner.id, action="employee.create", target_type="user", target_id=employee.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists") from None
    return employee_response(employee)


@router.put("/{employee_id}/permissions", response_model=EmployeeResponse)
def set_permissions(employee_id: UUID, payload: PermissionUpdate, db: Db, owner: Owner) -> EmployeeResponse:
    user = get_employee(db, employee_id)
    desired = valid_permissions(payload.permissions)
    current = {entry.permission: entry for entry in user.permissions}
    if desired != current.keys():
        for permission, entry in current.items():
            if permission not in desired:
                user.permissions.remove(entry)
        for permission in desired - current.keys():
            user.permissions.append(UserPermission(permission=permission))
        record_event(db, actor_id=owner.id, action="employee.permissions.update", target_type="user", target_id=user.id)
        db.commit()
    return employee_response(user)


@router.put("/{employee_id}/status", response_model=EmployeeResponse)
def set_status(employee_id: UUID, payload: StatusUpdate, db: Db, owner: Owner) -> EmployeeResponse:
    user = get_employee(db, employee_id)
    if user.is_active != payload.is_active:
        user.is_active = payload.is_active
        if not payload.is_active:
            revoke_sessions(db, user.id)
        record_event(db, actor_id=owner.id, action="employee.activate" if payload.is_active else "employee.deactivate", target_type="user", target_id=user.id)
        db.commit()
    return employee_response(user)


@router.put("/{employee_id}/profile", response_model=EmployeeResponse)
def set_profile(employee_id: UUID, payload: ProfileUpdate, db: Db, owner: Owner) -> EmployeeResponse:
    user = get_employee(db, employee_id)
    name = clean_display_name(payload.display_name)
    if user.display_name != name:
        user.display_name = name
        record_event(db, actor_id=owner.id, action="employee.profile.update", target_type="user", target_id=user.id)
        db.commit()
    return employee_response(user)


@router.put("/{employee_id}/password", status_code=204)
def reset_password(employee_id: UUID, payload: PasswordUpdate, db: Db, owner: Owner) -> None:
    user = get_employee(db, employee_id)
    try:
        user.password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    revoke_sessions(db, user.id)
    record_event(db, actor_id=owner.id, action="employee.password.reset", target_type="user", target_id=user.id)
    db.commit()
