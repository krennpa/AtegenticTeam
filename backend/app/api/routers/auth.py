from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError

from ...db.models import User, Profile
from ...core.security import create_access_token, get_password_hash, verify_password
from ...api.deps import get_db_session
from ...schemas import UserCreate, LoginRequest, TokenResponse, UserRead

router = APIRouter()


@router.post("/signup", response_model=TokenResponse)
def signup(payload: UserCreate, session: Session = Depends(get_db_session)):
    existing = session.exec(select(User).where(User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        display_name=payload.display_name,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        # Fallback in case race condition on email
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    session.refresh(user)

    # Ensure a profile exists for the user
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    if not profile:
        profile = Profile(user_id=user.id, display_name=user.display_name)
        session.add(profile)
        try:
            session.commit()
        except Exception:
            session.rollback()
            # Non-fatal for signup; continue
            pass

    token = create_access_token(subject=user.id)
    return TokenResponse(user=UserRead(id=user.id, email=user.email, display_name=user.display_name), token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_db_session)):
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(subject=user.id)
    return TokenResponse(user=UserRead(id=user.id, email=user.email, display_name=user.display_name), token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout():
    # Stateless JWT: client should simply delete the token from storage
    return None
