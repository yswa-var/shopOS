from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from shopos.audit import record_event
from shopos.db import make_engine
from shopos.models import AuthSession, User
from shopos.security import hash_token, new_token, normalize_username, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)
SESSION_HOURS = 12


def get_db():
    with sessionmaker(make_engine())() as db:
        yield db


Db = Annotated[Session, Depends(get_db)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: "UserResponse"


class UserResponse(BaseModel):
    id: UUID
    username: str
    display_name: str
    role: str
    permissions: list[str]


def unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired credentials", headers={"WWW-Authenticate": "Bearer"})


def current_session(db: Db, credentials: Credentials) -> AuthSession:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    auth_session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(credentials.credentials)))
    if auth_session is None or auth_session.revoked_at is not None or auth_session.expires_at <= datetime.now(timezone.utc) or not auth_session.user.is_active:
        raise unauthorized()
    return auth_session


CurrentSession = Annotated[AuthSession, Depends(current_session)]


def current_user(auth_session: CurrentSession) -> User:
    return auth_session.user


CurrentUser = Annotated[User, Depends(current_user)]


def require_permission(permission: str):
    def check(user: CurrentUser) -> User:
        if user.role != "owner" and permission not in {entry.permission for entry in user.permissions}:
            raise HTTPException(status_code=403, detail="Permission denied")
        return user
    return check


def require_owner(user: CurrentUser) -> User:
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")
    return user


def to_user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, username=user.username, display_name=user.display_name, role=user.role, permissions=sorted(entry.permission for entry in user.permissions))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Db) -> TokenResponse:
    try:
        username = normalize_username(payload.username)
    except ValueError:
        raise unauthorized() from None
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(payload.password, user.password_hash) or not user.is_active:
        raise unauthorized()
    token = new_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)
    db.add(AuthSession(user_id=user.id, token_hash=hash_token(token), expires_at=expires_at))
    record_event(db, actor_id=user.id, action="auth.login", target_type="user", target_id=user.id)
    db.commit()
    return TokenResponse(access_token=token, expires_at=expires_at, user=to_user_response(user))


@router.post("/logout", status_code=204)
def logout(db: Db, auth_session: CurrentSession) -> None:
    auth_session.revoked_at = datetime.now(timezone.utc)
    record_event(db, actor_id=auth_session.user_id, action="auth.logout", target_type="user", target_id=auth_session.user_id)
    db.commit()


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return to_user_response(user)
