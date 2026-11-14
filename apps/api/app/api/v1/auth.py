# 文件说明：FastAPI 路由：auth。
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AuthServiceDep, CurrentUserDep
from app.domain.user import ProfileChanges, User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.services.auth_service import (
    AuthService,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    UserNotFoundError,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])


def token_response(service: AuthService, user: User) -> TokenResponse:
    token, expires_in = service.issue_token(user)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


@auth_router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    service: AuthServiceDep,
) -> TokenResponse:
    try:
        user = await service.register(
            email=str(payload.email),
            password=payload.password,
            display_name=payload.display_name,
        )
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        ) from exc
    return token_response(service, user)


@auth_router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    try:
        user = await service.authenticate(
            email=str(payload.email),
            password=payload.password,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return token_response(service, user)


@auth_router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUserDep) -> UserResponse:
    return UserResponse.model_validate(current_user)


@users_router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdateRequest,
    current_user: CurrentUserDep,
    service: AuthServiceDep,
) -> UserResponse:
    changes = ProfileChanges(
        display_name=payload.display_name,
        default_origin=payload.default_origin,
        clear_default_origin=(
            "default_origin" in payload.model_fields_set and payload.default_origin is None
        ),
        currency=payload.currency,
        language=payload.language,
    )
    user = await service.update_profile(user_id=current_user.id, changes=changes)
    return UserResponse.model_validate(user)


@users_router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: CurrentUserDep,
    service: AuthServiceDep,
) -> UserResponse:
    try:
        user = await service.get_visible_user(
            requested_id=user_id,
            current_user=current_user,
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from exc
    return UserResponse.model_validate(user)
