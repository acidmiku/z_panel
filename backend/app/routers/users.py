"""Users router."""
import secrets
import uuid as uuid_mod
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

from arq.connections import create_pool

from app.database import get_db
from app.models import User, Server, Jumphost, ServerUserTraffic, AdminUser
from app.schemas import UserCreate, UserUpdate, UserResponse, UserDetailResponse
from app.deps import get_current_user
from app.config import settings

router = APIRouter()


async def _get_arq_pool():
    from app.worker import _parse_redis_url
    return await create_pool(_parse_redis_url(settings.REDIS_URL))


async def _push_to_all_servers(db: AsyncSession):
    """Enqueue config push for all online servers and jumphosts."""
    result = await db.execute(select(Server).where(Server.status.in_(["online", "error"])))
    servers = list(result.scalars().all())

    jh_result = await db.execute(select(Jumphost).where(Jumphost.status.in_(["online", "error"])))
    jumphosts = list(jh_result.scalars().all())

    if servers or jumphosts:
        pool = await _get_arq_pool()
        for srv in servers:
            await pool.enqueue_job("task_push_config", str(srv.id))
        for jh in jumphosts:
            await pool.enqueue_job("task_push_jumphost_config", str(jh.id))
        await pool.close()


@router.get("", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    # Check unique username
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=body.username,
        uuid=uuid_mod.uuid4(),
        hysteria2_password=secrets.token_urlsafe(24),
        sub_token=secrets.token_urlsafe(32),
        traffic_limit_bytes=body.traffic_limit_bytes,
        expires_at=body.expires_at,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Push configs to all servers
    await _push_to_all_servers(db)

    return user


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get per-server traffic breakdown
    traffic_result = await db.execute(
        select(
            ServerUserTraffic.server_id,
            func.sum(ServerUserTraffic.bytes_up).label("bytes_up"),
            func.sum(ServerUserTraffic.bytes_down).label("bytes_down"),
        )
        .where(ServerUserTraffic.user_id == user_id)
        .group_by(ServerUserTraffic.server_id)
    )
    traffic_by_server = [
        {"server_id": str(row.server_id), "bytes_up": row.bytes_up or 0, "bytes_down": row.bytes_down or 0}
        for row in traffic_result.all()
    ]

    resp = UserDetailResponse.model_validate(user)
    resp.traffic_by_server = traffic_by_server
    return resp


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.username is not None:
        existing = await db.execute(
            select(User).where(User.username == body.username, User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username already exists")
        user.username = body.username
    if body.traffic_limit_bytes is not None:
        user.traffic_limit_bytes = body.traffic_limit_bytes if body.traffic_limit_bytes > 0 else None
    if body.expires_at is not None:
        user.expires_at = body.expires_at
    if body.enabled is not None:
        user.enabled = body.enabled

    db.add(user)
    await db.commit()
    await db.refresh(user)

    await _push_to_all_servers(db)

    return user


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(user)
    await db.commit()

    # Push updated configs to servers and jumphosts
    pool = await _get_arq_pool()
    srv_result = await db.execute(select(Server).where(Server.status.in_(["online", "error"])))
    for srv in srv_result.scalars().all():
        await pool.enqueue_job("task_push_config", str(srv.id))
    jh_result = await db.execute(select(Jumphost).where(Jumphost.status.in_(["online", "error"])))
    for jh in jh_result.scalars().all():
        await pool.enqueue_job("task_push_jumphost_config", str(jh.id))
    await pool.close()

    return {"message": "User deleted"}
