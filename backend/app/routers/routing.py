"""Routing rules and user routing config router."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models import User, RoutingRule, UserRoutingConfig, AdminUser
from app.schemas import (
    RoutingRuleCreate, RoutingRuleUpdate, RoutingRuleResponse,
    UserRoutingConfigUpsert, UserRoutingConfigResponse,
)
from app.deps import get_current_user
from app.services.clash_config import GEO_RULE_PROVIDERS

router = APIRouter()


@router.get("/rules/{user_id}", response_model=List[RoutingRuleResponse])
async def get_rules(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    """Get routing rules for a user (user-specific + global)."""
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    rules_result = await db.execute(
        select(RoutingRule)
        .where((RoutingRule.user_id == user_id) | (RoutingRule.user_id.is_(None)))
        .order_by(RoutingRule.order.asc(), RoutingRule.created_at.asc())
    )
    return list(rules_result.scalars().all())


@router.post("/rules/{user_id}", response_model=RoutingRuleResponse, status_code=201)
async def add_rule(
    user_id: str,
    body: RoutingRuleCreate,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    rule = RoutingRule(
        user_id=user_id,
        domain_pattern=body.domain_pattern,
        match_type=body.match_type,
        action=body.action,
        order=body.order,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.put("/rules/{rule_id}", response_model=RoutingRuleResponse)
async def update_rule(
    rule_id: str,
    body: RoutingRuleUpdate,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(RoutingRule).where(RoutingRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(rule, field, value)

    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(RoutingRule).where(RoutingRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    await db.delete(rule)
    await db.commit()
    return {"message": "Rule deleted"}


@router.get("/config/{user_id}", response_model=UserRoutingConfigResponse)
async def get_routing_config(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    config_result = await db.execute(
        select(UserRoutingConfig).where(UserRoutingConfig.user_id == user_id)
    )
    config = config_result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="No routing config set")
    return config


@router.put("/config/{user_id}", response_model=UserRoutingConfigResponse)
async def upsert_routing_config(
    user_id: str,
    body: UserRoutingConfigUpsert,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    config_result = await db.execute(
        select(UserRoutingConfig).where(UserRoutingConfig.user_id == user_id)
    )
    config = config_result.scalar_one_or_none()

    geo_rules_json = [e.model_dump() for e in body.geo_rules] if body.geo_rules else None

    if config:
        config.geo_rules = geo_rules_json
        config.jumphost_id = body.jumphost_id
        config.jumphost_protocol = body.jumphost_protocol
        config.updated_at = datetime.now(timezone.utc)
    else:
        config = UserRoutingConfig(
            user_id=user_id,
            geo_rules=geo_rules_json,
            jumphost_id=body.jumphost_id,
            jumphost_protocol=body.jumphost_protocol,
        )
        db.add(config)

    await db.commit()
    await db.refresh(config)
    return config


@router.get("/geo-options")
async def get_geo_options(
    _: AdminUser = Depends(get_current_user),
):
    """Return available geo rule-provider IDs with labels and default actions."""
    options = []
    for geo_id, provider in GEO_RULE_PROVIDERS.items():
        options.append({
            "id": geo_id,
            "label": provider.get("label", geo_id),
            "default_action": provider.get("default_action", "DIRECT"),
        })
    return options
