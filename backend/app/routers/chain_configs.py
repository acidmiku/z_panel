"""Chain config CRUD + validation + export + profile import endpoints."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import AdminUser, ChainConfig, User, Server, Jumphost, RoutingRule, UserRoutingConfig
from app.schemas import (
    ChainConfigCreate,
    ChainConfigUpdate,
    ChainConfigResponse,
    ChainConfigListResponse,
    GraphValidationResult,
)
from app.services.chain_config_generator import validate_graph, generate_singbox_client_config

router = APIRouter()


@router.get("", response_model=List[ChainConfigListResponse])
async def list_chain_configs(
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    result = await db.execute(
        select(ChainConfig)
        .where(ChainConfig.user_id == current_user.id)
        .order_by(ChainConfig.updated_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=ChainConfigResponse, status_code=201)
async def create_chain_config(
    body: ChainConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    validation = validate_graph(body.graph_data)
    config = ChainConfig(
        user_id=current_user.id,
        name=body.name,
        description=body.description,
        graph_data=body.graph_data,
        is_valid=validation["is_valid"],
        validation_errors=validation["errors"] + validation["warnings"],
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@router.get("/{config_id}", response_model=ChainConfigResponse)
async def get_chain_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    result = await db.execute(
        select(ChainConfig).where(
            ChainConfig.id == config_id,
            ChainConfig.user_id == current_user.id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Chain config not found")
    return config


@router.patch("/{config_id}", response_model=ChainConfigResponse)
async def update_chain_config(
    config_id: str,
    body: ChainConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    result = await db.execute(
        select(ChainConfig).where(
            ChainConfig.id == config_id,
            ChainConfig.user_id == current_user.id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Chain config not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(config, field, value)

    # Re-validate if graph changed
    if "graph_data" in updates:
        validation = validate_graph(config.graph_data)
        config.is_valid = validation["is_valid"]
        config.validation_errors = validation["errors"] + validation["warnings"]
        config.generated_config = None  # Invalidate cache

    await db.commit()
    await db.refresh(config)
    return config


@router.delete("/{config_id}", status_code=204)
async def delete_chain_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    result = await db.execute(
        select(ChainConfig).where(
            ChainConfig.id == config_id,
            ChainConfig.user_id == current_user.id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Chain config not found")
    await db.delete(config)
    await db.commit()


@router.post("/validate", response_model=GraphValidationResult)
async def validate_chain_config(
    body: dict,
    _: AdminUser = Depends(get_current_user),
):
    result = validate_graph(body)
    return result


@router.post("/{config_id}/export")
async def export_chain_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    result = await db.execute(
        select(ChainConfig).where(
            ChainConfig.id == config_id,
            ChainConfig.user_id == current_user.id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Chain config not found")

    # Validate first
    validation = validate_graph(config.graph_data)
    if not validation["is_valid"]:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Graph has validation errors",
                "errors": validation["errors"],
            },
        )

    # Generate config
    generated = await generate_singbox_client_config(config.graph_data, db)

    # Cache it
    config.generated_config = generated
    config.is_valid = True
    config.validation_errors = validation.get("warnings", [])
    await db.commit()

    return generated


@router.post("/import-from-profile/{user_id}")
async def import_from_profile(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    """
    Read a VPN user's current profile (servers, jumphost, routing rules)
    and convert it into a React Flow graph for the chain editor.
    """
    # Load user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Load servers
    srv_result = await db.execute(select(Server).order_by(Server.created_at))
    all_servers = list(srv_result.scalars().all())
    online_servers = [s for s in all_servers if s.status == "online"]

    # Load routing context
    jumphost = None
    jumphost_protocol = "ss"
    routing_rules = []
    geo_rules = []

    cfg_result = await db.execute(
        select(UserRoutingConfig).where(UserRoutingConfig.user_id == user_id)
    )
    routing_config = cfg_result.scalar_one_or_none()

    if routing_config:
        geo_rules = routing_config.geo_rules or []
        jumphost_protocol = routing_config.jumphost_protocol or "ss"
        if routing_config.jumphost_id:
            jh_result = await db.execute(
                select(Jumphost).where(Jumphost.id == routing_config.jumphost_id)
            )
            jumphost = jh_result.scalar_one_or_none()

    rules_result = await db.execute(
        select(RoutingRule)
        .where((RoutingRule.user_id == user_id) | (RoutingRule.user_id.is_(None)))
        .order_by(RoutingRule.order.asc())
    )
    routing_rules = list(rules_result.scalars().all())

    # --- Build graph ---
    nodes = []
    edges = []
    node_id_counter = 0

    def next_id(prefix: str = "node") -> str:
        nonlocal node_id_counter
        node_id_counter += 1
        return f"{prefix}-{node_id_counter}"

    # Layout constants
    X_CLIENT = 50
    X_JUMPHOST = 280
    X_STRATEGY = 510
    X_SERVERS = 740
    X_ROUTE = 280
    X_DIRECT = 510
    Y_START = 80
    Y_SPACING = 120

    # 1) Client node
    client_id = "client-1"
    nodes.append({
        "id": client_id,
        "type": "clientNode",
        "position": {"x": X_CLIENT, "y": 250},
        "data": {"label": "Client"},
    })

    # 2) Build server nodes (one per protocol per server)
    server_nodes: list[dict] = []
    for i, srv in enumerate(online_servers):
        # VLESS node
        vless_id = next_id("srv")
        server_nodes.append({
            "id": vless_id,
            "type": "serverNode",
            "position": {"x": X_SERVERS, "y": Y_START + i * Y_SPACING * 2},
            "data": {
                "label": f"{srv.name} VLESS",
                "serverId": str(srv.id),
                "protocol": "vless",
                "ip": srv.ip,
                "status": srv.status,
            },
        })

        # Hysteria2 node
        hy2_id = next_id("srv")
        server_nodes.append({
            "id": hy2_id,
            "type": "serverNode",
            "position": {"x": X_SERVERS, "y": Y_START + i * Y_SPACING * 2 + Y_SPACING},
            "data": {
                "label": f"{srv.name} Hy2",
                "serverId": str(srv.id),
                "protocol": "hysteria2",
                "ip": srv.ip,
                "status": srv.status,
            },
        })

    nodes.extend(server_nodes)

    # 3) Strategy node (urltest) if multiple server nodes
    strategy_id = None
    if len(server_nodes) >= 2:
        strategy_id = next_id("strat")
        # Center it vertically among server nodes
        avg_y = sum(n["position"]["y"] for n in server_nodes) / len(server_nodes)
        nodes.append({
            "id": strategy_id,
            "type": "strategyNode",
            "position": {"x": X_STRATEGY, "y": avg_y - 30},
            "data": {
                "label": "URL Test",
                "strategyType": "urltest",
                "testUrl": "https://www.gstatic.com/generate_204",
                "interval": "5m",
                "tolerance": 50,
            },
        })
        # Edge from strategy to each server
        for sn in server_nodes:
            edges.append({
                "id": next_id("e"),
                "source": strategy_id,
                "target": sn["id"],
                "type": "detour",
            })
    elif len(server_nodes) == 1:
        strategy_id = server_nodes[0]["id"]

    # The "proxy exit" tag — what non-direct traffic goes to
    proxy_target = strategy_id

    # 4) Jumphost node (sits between client and strategy/servers)
    jumphost_id_node = None
    if jumphost and jumphost.status == "online":
        jumphost_id_node = next_id("jh")
        proto = "ssh" if jumphost_protocol == "ssh" else "shadowsocks"
        nodes.append({
            "id": jumphost_id_node,
            "type": "serverNode",
            "position": {"x": X_JUMPHOST, "y": 250},
            "data": {
                "label": f"JH:{jumphost.name}",
                "jumphostId": str(jumphost.id),
                "protocol": proto,
                "ip": jumphost.ip,
                "status": jumphost.status,
            },
        })
        # Jumphost → strategy/server (the servers detour through jumphost)
        # In the visual chain, jumphost is in the middle:
        #   Client → Route/JH → Strategy → Servers
        # But in sing-box detour, servers point back to jumphost.
        # For the visual graph, connect jumphost → strategy
        if proxy_target and proxy_target != jumphost_id_node:
            edges.append({
                "id": next_id("e"),
                "source": jumphost_id_node,
                "target": proxy_target,
            })
        proxy_target = jumphost_id_node

    # 5) Routing rules → Route node + Direct node
    has_routing = bool(geo_rules) or bool(routing_rules)
    if has_routing:
        direct_id = next_id("direct")
        nodes.append({
            "id": direct_id,
            "type": "directNode",
            "position": {"x": X_DIRECT, "y": Y_START},
            "data": {"label": "Direct"},
        })

        route_id = next_id("route")
        rules_data = []

        # Geo rules
        for gr in geo_rules:
            geo_id = gr.get("id", "") if isinstance(gr, dict) else str(gr)
            action = gr.get("action", "DIRECT") if isinstance(gr, dict) else "DIRECT"
            rule_entry_id = next_id("rule")
            rule_type = geo_id  # e.g. "geoip-ru", "geosite-cn"
            # Normalize to geoip:/geosite: format
            if rule_type.startswith("geoip-"):
                rule_type = f"geoip:{rule_type[6:]}"
            elif rule_type.startswith("geosite-"):
                rule_type = f"geosite:{rule_type[8:]}"
            rules_data.append({
                "id": rule_entry_id,
                "type": rule_type,
                "value": geo_id,
                "handleId": rule_entry_id,
                "action": action,
            })

        # Custom routing rules
        for rr in routing_rules:
            rule_entry_id = next_id("rule")
            rt = rr.match_type  # domain, domain-suffix, etc.
            # Map to our Route node types
            type_map = {
                "domain": "domain",
                "domain-suffix": "domain_suffix",
                "domain-keyword": "domain_keyword",
                "domain-regex": "domain_suffix",
            }
            rules_data.append({
                "id": rule_entry_id,
                "type": type_map.get(rt, "domain_suffix"),
                "value": rr.domain_pattern,
                "handleId": rule_entry_id,
                "action": rr.action,
            })

        # Compute route node Y position
        route_y = 250 - 60 if not jumphost_id_node else 100
        nodes.append({
            "id": route_id,
            "type": "routeNode",
            "position": {"x": X_ROUTE, "y": route_y},
            "data": {
                "label": "Route",
                "rules": rules_data,
            },
        })

        # Client → Route
        edges.append({
            "id": next_id("e"),
            "source": client_id,
            "target": route_id,
        })

        # Route rule handles → Direct or Proxy
        for rule in rules_data:
            action = rule.get("action", "DIRECT")
            target = direct_id if action in ("DIRECT", "direct") else (proxy_target or direct_id)
            edges.append({
                "id": next_id("e"),
                "source": route_id,
                "sourceHandle": rule["handleId"],
                "target": target,
            })

        # Route final → proxy
        if proxy_target:
            edges.append({
                "id": next_id("e"),
                "source": route_id,
                "sourceHandle": "final",
                "target": proxy_target,
            })

    else:
        # No routing rules — Client connects directly to proxy chain
        if proxy_target:
            edges.append({
                "id": next_id("e"),
                "source": client_id,
                "target": proxy_target,
            })

    graph_data = {"nodes": nodes, "edges": edges}

    return {
        "graph_data": graph_data,
        "user_name": user.username,
        "server_count": len(online_servers),
        "has_jumphost": jumphost is not None,
        "has_routing": has_routing,
    }
