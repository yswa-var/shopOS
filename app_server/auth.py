"""Per-user HTTP Basic authentication over HTTPS."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pwdlib import PasswordHash

from db import Database, get_database


password_hash = PasswordHash.recommended()
security = HTTPBasic(auto_error=False)


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password",
        headers={"WWW-Authenticate": "Basic"},
    )


async def require_user(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(security)],
    database: Annotated[Database, Depends(get_database)],
) -> str:
    if credentials is None:
        raise unauthorized()
    user = await database.fetch_one(
        "SELECT password_hash, is_active FROM api_users WHERE username = $1",
        (credentials.username,),
    )
    if not user or not user["is_active"]:
        raise unauthorized()
    if not password_hash.verify(credentials.password, user["password_hash"]):
        raise unauthorized()
    return credentials.username
