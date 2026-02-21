"""Cloudflare configs router."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models import CloudflareConfig, Server, AdminUser
from app.schemas import CloudflareConfigCreate, CloudflareConfigResponse
from app.deps import get_current_user
from app.services.crypto import encrypt

router = APIRouter()


@router.get("", response_model=List[CloudflareConfigResponse])
async def list_configs(
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(CloudflareConfig).order_by(CloudflareConfig.created_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=CloudflareConfigResponse, status_code=201)
async def create_config(
    body: CloudflareConfigCreate,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    config = CloudflareConfig(
        name=body.name,
        api_token=encrypt(body.api_token),
        zone_id=body.zone_id,
        base_domain=body.base_domain,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@router.delete("/{config_id}")
async def delete_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(
        select(CloudflareConfig).where(CloudflareConfig.id == config_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    # Check if any servers reference this config
    srv_result = await db.execute(
        select(Server).where(Server.cf_config_id == config_id)
    )
    if srv_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Cannot delete: servers still reference this config")

    await db.delete(config)
    await db.commit()
    return {"message": "Deleted"}
