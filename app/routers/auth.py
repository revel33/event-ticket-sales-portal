from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import TokenOut, UserCreate, UserOut
from app.security import create_access_token
from app.services import users

router = APIRouter(prefix="/api/auth", tags=["Аутентификация"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Зарегистрироваться",
)
def register(data: UserCreate, db: Session = Depends(get_db)) -> User:
    if users.get_by_email(db, data.email) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Пользователь с таким email уже зарегистрирован",
        )
    return users.create_user(db, email=data.email, password=data.password, full_name=data.full_name)


@router.post(
    "/token",
    response_model=TokenOut,
    summary="Войти и получить токен",
)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenOut:
    user = users.authenticate(db, form.username, form.password)
    return TokenOut(access_token=create_access_token(user))


@router.get("/me", response_model=UserOut, summary="Профиль текущего пользователя")
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user