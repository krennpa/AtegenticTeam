from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlmodel import Session, select

from ..core.config import settings
from ..db.session import get_session
from ..db.models import User


bearer_scheme = HTTPBearer(auto_error=True)


def get_db_session() -> Session:
    # Proper generator dependency that FastAPI will finalize (close) after the request
    # This avoids session leaks and ensures commits are persisted reliably.
    yield from get_session()


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    token = creds.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = session.exec(select(User).where(User.id == sub)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
