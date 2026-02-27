"""Profiles router - generate Clash Meta and v2rayN configs."""
import base64
import hashlib
from datetime import datetime, timezone
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.models import User, Server, Jumphost, RoutingRule, UserRoutingConfig, AdminUser
from app.deps import get_current_user
from app.services.clash_config import generate_clash_config
from app.services.singbox_config import is_user_active
from app.services.crypto import decrypt

router = APIRouter()


async def _load_routing_context(db, user_id):
    """Load jumphost, routing rules, and geo rules for a user."""
    jumphost = None
    jumphost_protocol = None
    routing_rules = None
    geo_rules = None

    config_result = await db.execute(
        select(UserRoutingConfig).where(UserRoutingConfig.user_id == user_id)
    )
    config = config_result.scalar_one_or_none()

    if config:
        geo_rules = config.geo_rules
        jumphost_protocol = config.jumphost_protocol

        if config.jumphost_id:
            jh_result = await db.execute(
                select(Jumphost).where(Jumphost.id == config.jumphost_id)
            )
            jumphost = jh_result.scalar_one_or_none()

    rules_result = await db.execute(
        select(RoutingRule)
        .where((RoutingRule.user_id == user_id) | (RoutingRule.user_id.is_(None)))
        .order_by(RoutingRule.order.asc())
    )
    rules = list(rules_result.scalars().all())
    if rules:
        routing_rules = rules

    return jumphost, jumphost_protocol, routing_rules, geo_rules


@router.get("/sub/{token}")
async def subscription_profile(
    token: str,
    strategy: str = Query(default="url-test", regex="^(url-test|fallback|load-balance)$"),
    db: AsyncSession = Depends(get_db),
):
    """Public subscription endpoint - no auth required, identified by token."""
    result = await db.execute(select(User).where(User.sub_token == token))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Invalid subscription")

    if not is_user_active(user):
        raise HTTPException(status_code=403, detail="Subscription inactive")

    srv_result = await db.execute(select(Server).where(Server.status == "online"))
    server_list = list(srv_result.scalars().all())

    if not server_list:
        raise HTTPException(status_code=404, detail="No online servers available")

    jumphost, jumphost_protocol, routing_rules, geo_rules = await _load_routing_context(db, str(user.id))

    yaml_content = generate_clash_config(
        user, server_list, strategy,
        jumphost=jumphost,
        jumphost_protocol=jumphost_protocol,
        routing_rules=routing_rules,
        geo_rules=geo_rules,
    )

    return Response(
        content=yaml_content,
        media_type="application/x-yaml",
        headers={
            "Content-Disposition": f'attachment; filename="{user.username}.yaml"',
            "Profile-Update-Interval": "6",
            "Subscription-Userinfo": f"upload=0; download={user.traffic_used_bytes}; total={user.traffic_limit_bytes or 0}",
        },
    )


@router.get("/sub/{token}/v2ray")
async def subscription_v2ray(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Public v2rayN/v2rayNG subscription endpoint."""
    result = await db.execute(select(User).where(User.sub_token == token))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Invalid subscription")

    if not is_user_active(user):
        raise HTTPException(status_code=403, detail="Subscription inactive")

    srv_result = await db.execute(select(Server).where(Server.status == "online"))
    server_list = list(srv_result.scalars().all())

    if not server_list:
        raise HTTPException(status_code=404, detail="No online servers available")

    # Check if user has a jumphost configured — prepend SS URI
    jumphost, jumphost_protocol, _, _ = await _load_routing_context(db, str(user.id))

    uris = []

    if jumphost and jumphost.status == "online" and jumphost.shadowsocks_server_key:
        server_key = decrypt(jumphost.shadowsocks_server_key)
        user_key_bytes = hashlib.sha256(user.hysteria2_password.encode()).digest()[:16]
        user_key = base64.b64encode(user_key_bytes).decode()
        password = f"{server_key}:{user_key}"
        encoded_password = base64.b64encode(
            f"{jumphost.shadowsocks_method}:{password}".encode()
        ).decode()
        jh_name = quote(f"JH-{jumphost.name}")
        ss_uri = f"ss://{encoded_password}@{jumphost.ip}:{jumphost.shadowsocks_port}#{jh_name}"
        uris.append(ss_uri)

    for server in server_list:
        # hysteria2://password@host:port?sni=fqdn#name
        hy2_name = quote(f"{server.name}-Hysteria2")
        hy2_uri = (
            f"hysteria2://{user.hysteria2_password}@{server.fqdn}:{server.hysteria2_port}"
            f"?sni={server.fqdn}&insecure=0#{hy2_name}"
        )
        uris.append(hy2_uri)

        # vless://uuid@ip:port?params#name
        vless_name = quote(f"{server.name}-VLESS-Reality")
        vless_uri = (
            f"vless://{user.uuid}@{server.ip}:{server.reality_port}"
            f"?encryption=none&flow=xtls-rprx-vision&security=reality"
            f"&sni={server.reality_server_name}"
            f"&fp=chrome&pbk={server.reality_public_key}"
            f"&sid={server.reality_short_id}&type=tcp"
            f"#{vless_name}"
        )
        uris.append(vless_uri)

    content = base64.b64encode("\n".join(uris).encode()).decode()

    return Response(
        content=content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{user.username}-v2ray.txt"',
            "Profile-Update-Interval": "6",
            "Subscription-Userinfo": f"upload=0; download={user.traffic_used_bytes}; total={user.traffic_limit_bytes or 0}",
        },
    )


@router.get("/{user_id}/clash")
async def get_clash_profile(
    user_id: str,
    strategy: str = Query(default="url-test", regex="^(url-test|fallback|load-balance)$"),
    servers: Optional[str] = Query(default="all"),
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not is_user_active(user):
        reason = "disabled"
        if not user.enabled:
            reason = "disabled"
        elif user.expires_at and user.expires_at < datetime.now(timezone.utc):
            reason = "expired"
        elif user.traffic_limit_bytes and user.traffic_used_bytes >= user.traffic_limit_bytes:
            reason = "traffic limit exceeded"
        raise HTTPException(status_code=403, detail=f"User is {reason}")

    # Get servers
    if servers == "all":
        srv_result = await db.execute(select(Server).where(Server.status == "online"))
        server_list = list(srv_result.scalars().all())
    else:
        server_ids = [s.strip() for s in servers.split(",")]
        srv_result = await db.execute(
            select(Server).where(Server.id.in_(server_ids), Server.status == "online")
        )
        server_list = list(srv_result.scalars().all())

    if not server_list:
        raise HTTPException(status_code=404, detail="No online servers available")

    jumphost, jumphost_protocol, routing_rules, geo_rules = await _load_routing_context(db, user_id)

    yaml_content = generate_clash_config(
        user, server_list, strategy,
        jumphost=jumphost,
        jumphost_protocol=jumphost_protocol,
        routing_rules=routing_rules,
        geo_rules=geo_rules,
    )

    filename = f"{user.username}-{strategy}.yaml"
    return Response(
        content=yaml_content,
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
