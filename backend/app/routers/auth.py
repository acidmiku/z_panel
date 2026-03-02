"""Auth router."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import AdminUser
from app.schemas import LoginRequest, PasswordChangeRequest
from app.auth import verify_password, create_access_token, create_refresh_token, decode_refresh_token, decode_access_token, hash_password
from app.deps import get_current_user, get_redis

router = APIRouter()
security = HTTPBearer()


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AdminUser).where(AdminUser.username == body.username)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    return AuthResponse(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_refresh_token(body.refresh_token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    result = await db.execute(select(AdminUser).where(AdminUser.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return AuthResponse(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
    )


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    redis_client=Depends(get_redis),
):
    token = credentials.credentials
    payload = await decode_access_token(token)
    if not payload or "jti" not in payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    jti = payload["jti"]
    exp = payload.get("exp", 0)
    now = datetime.now(timezone.utc).timestamp()
    ttl = max(int(exp - now), 0)

    if ttl > 0:
        await redis_client.setex(f"token_blacklist:{jti}", ttl, "1")

    return {"message": "Logged out successfully"}


@router.post("/change-password")
async def change_password(
    body: PasswordChangeRequest,
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.password_hash = hash_password(body.new_password)
    db.add(current_user)
    await db.commit()
    return {"message": "Password changed successfully"}
