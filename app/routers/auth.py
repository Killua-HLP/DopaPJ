import hashlib
from typing import cast

from fastapi import APIRouter, Depends, Form, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.models.user import User
from app.security import rate_limiter
from app.schemas.user import AuthResponse, PasswordChange, UserCreate, UserLogin, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])
_DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing-equalization")


def _authenticate(identity: str, password: str, db: Session) -> User:
    normalized_identity = identity.strip().lower()
    account_key = "login-account:" + hashlib.sha256(normalized_identity.encode("utf-8")).hexdigest()
    limited, retry_after = rate_limiter.is_limited(account_key, 5, 900)
    if limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many unsuccessful sign-in attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = (
        db.query(User)
        .filter(
            or_(
                func.lower(User.email) == normalized_identity,
                func.lower(User.name) == normalized_identity,
            )
        )
        .first()
    )
    password_hash = user.hashed_password if user else _DUMMY_PASSWORD_HASH
    password_matches = verify_password(password, cast(str, password_hash))
    if not user or not password_matches or not user.is_active:
        rate_limiter.record(account_key, 900)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email or password is incorrect.")
    rate_limiter.clear_key(account_key)
    return user


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)) -> AuthResponse:
    existing = db.query(User).filter(
        (func.lower(User.email) == user_data.email)
        | (func.lower(User.name) == user_data.name.lower())
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That email or display name is already in use.")

    user = User(
        name=user_data.name,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That email or display name is already in use.") from exc
    db.refresh(user)
    return AuthResponse(access_token=create_access_token(cast(int, user.id)), user=UserResponse.model_validate(user))


@router.post("/login", response_model=AuthResponse)
def login(
    credentials: UserLogin,
    db: Session = Depends(get_db),
) -> AuthResponse:
    user = _authenticate(credentials.email, credentials.password, db)
    return AuthResponse(access_token=create_access_token(cast(int, user.id)), user=UserResponse.model_validate(user))


@router.post("/token")
def issue_oauth_token(
    username: str = Form(min_length=3, max_length=254),
    password: str = Form(min_length=1, max_length=128),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    user = _authenticate(username, password, db)
    return {"access_token": create_access_token(cast(int, user.id)), "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def current_account(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    credentials: PasswordChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if not verify_password(credentials.current_password, cast(str, user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    user.hashed_password = hash_password(credentials.new_password)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
