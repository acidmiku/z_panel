"""Stats router."""
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List

from app.database import get_db
from app.models import Server, Jumphost, User, ServerUserTraffic, AdminUser
from app.schemas import StatsResponse, TrafficRecord
from app.deps import get_current_user

router = APIRouter()


@router.get("/summary", response_model=StatsResponse)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    srv_result = await db.execute(select(func.count(Server.id)))
    total_servers = srv_result.scalar() or 0

    online_result = await db.execute(
        select(func.count(Server.id)).where(Server.status == "online")
    )
    online_servers = online_result.scalar() or 0

    jh_result = await db.execute(select(func.count(Jumphost.id)))
    total_jumphosts = jh_result.scalar() or 0

    jh_online_result = await db.execute(
        select(func.count(Jumphost.id)).where(Jumphost.status == "online")
    )
    online_jumphosts = jh_online_result.scalar() or 0

    usr_result = await db.execute(select(func.count(User.id)))
    total_users = usr_result.scalar() or 0

    active_result = await db.execute(
        select(func.count(User.id)).where(User.enabled == True)
    )
    active_users = active_result.scalar() or 0

    traffic_result = await db.execute(
        select(func.coalesce(func.sum(User.traffic_used_bytes), 0))
    )
    total_traffic = traffic_result.scalar() or 0

    return StatsResponse(
        total_servers=total_servers,
        online_servers=online_servers,
        total_jumphosts=total_jumphosts,
        online_jumphosts=online_jumphosts,
        total_users=total_users,
        active_users=active_users,
        total_traffic_bytes=total_traffic,
    )


@router.get("/traffic", response_model=List[TrafficRecord])
async def get_traffic(
    user_id: Optional[str] = Query(default=None),
    server_id: Optional[str] = Query(default=None),
    from_date: Optional[datetime] = Query(default=None, alias="from"),
    to_date: Optional[datetime] = Query(default=None, alias="to"),
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    query = select(ServerUserTraffic)
    if user_id:
        query = query.where(ServerUserTraffic.user_id == user_id)
    if server_id:
        query = query.where(ServerUserTraffic.server_id == server_id)
    if from_date:
        query = query.where(ServerUserTraffic.recorded_at >= from_date)
    if to_date:
        query = query.where(ServerUserTraffic.recorded_at <= to_date)

    query = query.order_by(ServerUserTraffic.recorded_at.desc()).limit(1000)
    result = await db.execute(query)
    return list(result.scalars().all())
