"""
Graph-to-config generator for visual proxy chain editor.

Takes a React Flow graph (nodes + edges) and produces
a valid sing-box client configuration JSON.

Algorithm:
1. Parse graph into internal representation
2. Validate graph (cycles, orphans, terminal nodes)
3. Walk graph from Client node, building outbounds with detour chains
4. Generate DNS section
5. Generate route section from Route nodes
6. Generate inbound section (tun)
7. Assemble final config
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Server, User, Jumphost


# ---------------------------------------------------------------------------
# Graph Validation
# ---------------------------------------------------------------------------

TLS_PROTOCOLS = {"vless", "trojan", "hysteria2"}


def validate_graph(graph_data: dict) -> dict:
    """Validate a React Flow graph and return errors/warnings/info."""
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    errors: list[dict] = []
    warnings: list[dict] = []
    info: list[dict] = []

    node_map: dict[str, dict] = {n["id"]: n for n in nodes}
    outgoing: dict[str, list[dict]] = defaultdict(list)
    incoming: dict[str, list[dict]] = defaultdict(list)

    for e in edges:
        outgoing[e["source"]].append(e)
        incoming[e["target"]].append(e)

    # Find client node
    client_nodes = [n for n in nodes if n.get("type") == "clientNode"]
    if not client_nodes:
        errors.append({"type": "error", "code": "NO_CLIENT", "message": "Client node is missing"})
        return {"is_valid": False, "errors": errors, "warnings": warnings, "info": info}

    client_id = client_nodes[0]["id"]

    # Client must have exactly one outgoing edge
    client_out = outgoing.get(client_id, [])
    if len(client_out) == 0:
        errors.append({"type": "error", "code": "CLIENT_NO_OUTPUT", "message": "Client node has no outgoing connection"})
    elif len(client_out) > 1:
        errors.append({"type": "error", "code": "CLIENT_MULTI_OUTPUT", "message": "Client node must have exactly one outgoing connection"})

    # Cycle detection (DFS)
    visited: set[str] = set()
    rec_stack: set[str] = set()

    def has_cycle(node_id: str) -> bool:
        visited.add(node_id)
        rec_stack.add(node_id)
        for edge in outgoing.get(node_id, []):
            target = edge["target"]
            if target not in visited:
                if has_cycle(target):
                    return True
            elif target in rec_stack:
                return True
        rec_stack.discard(node_id)
        return False

    if has_cycle(client_id):
        errors.append({"type": "error", "code": "CYCLE", "message": "Cycle detected in graph"})

    # Reachability from client (BFS)
    reachable: set[str] = set()
    queue: deque[str] = deque([client_id])
    while queue:
        nid = queue.popleft()
        if nid in reachable:
            continue
        reachable.add(nid)
        for edge in outgoing.get(nid, []):
            queue.append(edge["target"])

    # Orphan detection
    for n in nodes:
        if n["id"] not in reachable and n.get("type") != "clientNode":
            errors.append({
                "type": "error",
                "code": "ORPHAN",
                "message": f"Node '{n.get('data', {}).get('label', n['id'])}' is not connected to Client",
            })

    # Terminal node check — every path from client must end at server or direct
    terminal_types = {"serverNode", "directNode"}

    def check_paths(node_id: str, depth: int, path: list[str]) -> None:
        node = node_map.get(node_id)
        if not node:
            return
        ntype = node.get("type", "")
        outs = outgoing.get(node_id, [])

        if ntype in terminal_types and not outs:
            # Valid terminal
            if depth > 3:
                warnings.append({
                    "type": "warning",
                    "code": "DEEP_CHAIN",
                    "message": f"Chain depth >{3} hops — latency will be high ({' -> '.join(path)})",
                })
            return

        if ntype == "directNode":
            return  # Direct is always terminal

        if ntype == "serverNode" and not outs:
            return  # Server with no output is exit node

        if not outs and ntype not in terminal_types:
            errors.append({
                "type": "error",
                "code": "NO_TERMINAL",
                "message": f"Path leads nowhere at node '{node.get('data', {}).get('label', node_id)}'",
            })
            return

        # Strategy nodes need >= 2 outputs
        if ntype == "strategyNode" and len(outs) < 2:
            errors.append({
                "type": "error",
                "code": "STRATEGY_LOW_OUTPUTS",
                "message": f"Strategy node '{node.get('data', {}).get('label', node_id)}' needs at least 2 outputs",
            })

        for edge in outs:
            target = edge["target"]
            target_node = node_map.get(target)
            if not target_node:
                continue

            new_path = path + [target_node.get("data", {}).get("label", target)]

            # TLS-over-TLS check
            if ntype == "serverNode" and target_node.get("type") == "serverNode":
                src_proto = (node.get("data", {}).get("protocol", "") or "").lower()
                dst_proto = (target_node.get("data", {}).get("protocol", "") or "").lower()
                if src_proto in TLS_PROTOCOLS and dst_proto in TLS_PROTOCOLS:
                    warnings.append({
                        "type": "warning",
                        "code": "TLS_OVER_TLS",
                        "message": f"TLS-over-TLS detected: {node.get('data', {}).get('label', '')} -> {target_node.get('data', {}).get('label', '')} — may cause connection failures. Consider SSH or Shadowsocks for the jump hop.",
                    })

            # SS as first hop warning
            if node_id == client_id and target_node.get("type") == "serverNode":
                proto = (target_node.get("data", {}).get("protocol", "") or "").lower()
                if proto == "shadowsocks":
                    warnings.append({
                        "type": "warning",
                        "code": "SS_FIRST_HOP",
                        "message": "Shadowsocks as first hop — detectable by DPI within hours. Consider SSH instead.",
                    })

            hop_depth = depth + (1 if target_node.get("type") == "serverNode" else 0)
            check_paths(target, hop_depth, new_path)

    if client_out:
        check_paths(client_id, 0, ["Client"])

    # Server offline warnings
    for n in nodes:
        if n.get("type") == "serverNode":
            status = n.get("data", {}).get("status", "")
            if status == "offline" or status == "error":
                warnings.append({
                    "type": "warning",
                    "code": "SERVER_OFFLINE",
                    "message": f"Server '{n.get('data', {}).get('label', '')}' is currently {status}",
                })

    # Chain summary info
    if not errors:
        _build_chain_info(client_id, outgoing, node_map, info)

    is_valid = len(errors) == 0
    return {"is_valid": is_valid, "errors": errors, "warnings": warnings, "info": info}


def _build_chain_info(
    client_id: str,
    outgoing: dict[str, list[dict]],
    node_map: dict[str, dict],
    info: list[dict],
) -> None:
    """Build chain summary and estimated RTT."""
    hop_latency_ms = {"ssh": 30, "shadowsocks": 20, "vless": 25, "hysteria2": 15}

    def walk(nid: str) -> tuple[list[str], int]:
        node = node_map.get(nid)
        if not node:
            return [], 0
        label = node.get("data", {}).get("label", nid)
        ntype = node.get("type", "")
        outs = outgoing.get(nid, [])

        if ntype == "directNode" or (ntype == "serverNode" and not outs):
            proto = (node.get("data", {}).get("protocol", "") or "").lower()
            lat = hop_latency_ms.get(proto, 25) if ntype == "serverNode" else 0
            return [label], lat

        if outs:
            first_target = outs[0]["target"]
            rest, rest_lat = walk(first_target)
            proto = (node.get("data", {}).get("protocol", "") or "").lower()
            lat = hop_latency_ms.get(proto, 0) if ntype == "serverNode" else 0
            return [label] + rest, lat + rest_lat

        return [label], 0

    chain, total_lat = walk(client_id)
    hops = sum(1 for nid in chain if node_map.get(nid, {}).get("type") == "serverNode")

    # Count hops by counting server labels in the walk
    server_count = 0
    for label in chain:
        for n in node_map.values():
            if n.get("data", {}).get("label") == label and n.get("type") == "serverNode":
                server_count += 1
                break

    info.append({
        "type": "info",
        "code": "CHAIN_SUMMARY",
        "message": f"Chain: {' -> '.join(chain)} ({server_count} hop{'s' if server_count != 1 else ''})",
    })
    if total_lat > 0:
        info.append({
            "type": "info",
            "code": "ESTIMATED_RTT",
            "message": f"Estimated RTT: ~{total_lat}ms",
        })


# ---------------------------------------------------------------------------
# Config Generation
# ---------------------------------------------------------------------------


async def generate_singbox_client_config(
    graph_data: dict,
    db: AsyncSession,
    user_id: str | None = None,
) -> dict:
    """
    Generate a sing-box client config from a React Flow graph.

    The graph is walked from the Client node, building outbound chains
    with `detour` fields linking them together.
    """
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    node_map = {n["id"]: n for n in nodes}
    outgoing: dict[str, list[dict]] = defaultdict(list)
    for e in edges:
        outgoing[e["source"]].append(e)

    # Fetch all servers and jumphosts from DB
    server_result = await db.execute(select(Server))
    servers = {str(s.id): s for s in server_result.scalars().all()}

    jumphost_result = await db.execute(select(Jumphost))
    jumphosts = {str(j.id): j for j in jumphost_result.scalars().all()}

    # Fetch user if specified (for credentials)
    vpn_user = None
    if user_id:
        user_result = await db.execute(select(User).where(User.id == user_id))
        vpn_user = user_result.scalar_one_or_none()

    # Find client node
    client_node = next((n for n in nodes if n.get("type") == "clientNode"), None)
    if not client_node:
        raise ValueError("No client node in graph")

    outbounds: list[dict] = []
    route_rules: list[dict] = []
    rule_sets: list[dict] = []
    seen_tags: set[str] = set()
    first_hop_tag: str | None = None

    def make_tag(node: dict, suffix: str = "") -> str:
        label = node.get("data", {}).get("label", node["id"])
        tag = label.lower().replace(" ", "-").replace(":", "-")
        if suffix:
            tag = f"{tag}-{suffix}"
        # Ensure unique
        base = tag
        i = 1
        while tag in seen_tags:
            tag = f"{base}-{i}"
            i += 1
        seen_tags.add(tag)
        return tag

    def build_outbound(node_id: str, detour_tag: str | None = None) -> str | None:
        """Recursively build outbounds. Returns the tag of the built outbound."""
        node = node_map.get(node_id)
        if not node:
            return None

        ntype = node.get("type", "")
        data = node.get("data", {})
        outs = outgoing.get(node_id, [])

        if ntype == "directNode":
            tag = "direct"
            if tag not in seen_tags:
                seen_tags.add(tag)
                outbounds.append({"type": "direct", "tag": "direct"})
            return "direct"

        if ntype == "serverNode":
            server_id = data.get("serverId")
            server = servers.get(server_id) if server_id else None
            protocol = (data.get("protocol", "") or "").lower()
            tag = make_tag(node)

            # Build the next hop first (if any)
            next_tag = None
            if outs:
                next_tag = build_outbound(outs[0]["target"])

            outbound = _build_server_outbound(
                tag=tag,
                protocol=protocol,
                server=server,
                data=data,
                vpn_user=vpn_user,
                jumphosts=jumphosts,
                detour_tag=next_tag,
            )
            outbounds.append(outbound)
            return tag

        if ntype == "strategyNode":
            strategy_type = (data.get("strategyType", "urltest") or "urltest").lower()
            tag = make_tag(node)
            child_tags: list[str] = []

            for edge in outs:
                child_tag = build_outbound(edge["target"])
                if child_tag:
                    child_tags.append(child_tag)

            strategy_outbound: dict[str, Any] = {
                "type": strategy_type,
                "tag": tag,
                "outbounds": child_tags,
            }

            if strategy_type in ("urltest", "fallback"):
                strategy_outbound["url"] = data.get("testUrl", "https://www.gstatic.com/generate_204")
                strategy_outbound["interval"] = data.get("interval", "5m")
                if strategy_type == "urltest":
                    strategy_outbound["tolerance"] = data.get("tolerance", 50)

            outbounds.append(strategy_outbound)
            return tag

        if ntype == "routeNode":
            rules = data.get("rules", [])
            default_out = None

            for rule in rules:
                rule_type = rule.get("type", "")
                value = rule.get("value", "")
                handle_id = rule.get("handleId", "")

                # Find the edge from this handle
                matching_edges = [
                    e for e in outs
                    if e.get("sourceHandle") == handle_id
                ]
                if not matching_edges:
                    continue

                target_tag = build_outbound(matching_edges[0]["target"])
                if not target_tag:
                    continue

                if rule_type == "final":
                    default_out = target_tag
                    continue

                sb_rule = _build_route_rule(rule_type, value, target_tag, rule_sets)
                if sb_rule:
                    route_rules.append(sb_rule)

            # Also handle the final/default edge
            final_edges = [e for e in outs if e.get("sourceHandle", "").startswith("final")]
            if final_edges and not default_out:
                default_out = build_outbound(final_edges[0]["target"])

            return default_out

        return None

    # Walk from client
    client_outs = outgoing.get(client_node["id"], [])
    if client_outs:
        first_hop_tag = build_outbound(client_outs[0]["target"])

    # Add block outbound
    if "block" not in seen_tags:
        seen_tags.add("block")
        outbounds.append({"type": "block", "tag": "block"})

    # Ensure direct exists
    if "direct" not in seen_tags:
        seen_tags.add("direct")
        outbounds.append({"type": "direct", "tag": "direct"})

    # Determine the final outbound (last exit node)
    final_outbound = first_hop_tag or "direct"

    # Build DNS section
    dns = _build_dns(final_outbound)

    # Build inbound
    inbounds = [
        {
            "type": "tun",
            "tag": "tun-in",
            "address": ["172.18.0.1/30", "fdfe:dcba:9876::1/126"],
            "auto_route": True,
            "strict_route": True,
            "sniff": True,
            "sniff_override_destination": True,
        }
    ]

    # Build route
    route: dict[str, Any] = {}
    if route_rules:
        route["rules"] = [{"outbound": "any", "server": "dns-direct"}] if False else []
        route["rules"] = route_rules
    if rule_sets:
        route["rule_set"] = rule_sets
    route["auto_detect_interface"] = True
    route["final"] = final_outbound

    config = {
        "log": {"level": "info", "timestamp": True},
        "dns": dns,
        "inbounds": inbounds,
        "outbounds": outbounds,
        "route": route,
    }

    return config


def _build_server_outbound(
    tag: str,
    protocol: str,
    server: Server | None,
    data: dict,
    vpn_user: User | None,
    jumphosts: dict[str, Jumphost],
    detour_tag: str | None,
) -> dict:
    """Build a single server outbound entry."""
    outbound: dict[str, Any] = {"tag": tag}

    port_override = data.get("portOverride")
    jumphost_id = data.get("jumphostId")

    if protocol == "ssh":
        outbound["type"] = "ssh"
        if server:
            outbound["server"] = server.ip
            outbound["server_port"] = int(port_override) if port_override else server.ssh_port
            outbound["user"] = server.ssh_user or "proxy"
        elif jumphost_id and jumphost_id in jumphosts:
            jh = jumphosts[jumphost_id]
            outbound["server"] = jh.ip
            outbound["server_port"] = int(port_override) if port_override else jh.ssh_port
            outbound["user"] = jh.ssh_user or "proxy"
        else:
            outbound["server"] = data.get("host", "0.0.0.0")
            outbound["server_port"] = int(port_override or 22)

    elif protocol == "shadowsocks":
        outbound["type"] = "shadowsocks"
        if jumphost_id and jumphost_id in jumphosts:
            jh = jumphosts[jumphost_id]
            outbound["server"] = jh.ip
            outbound["server_port"] = int(port_override) if port_override else (jh.shadowsocks_port or 1080)
            outbound["method"] = jh.shadowsocks_method or "2022-blake3-aes-128-gcm"
            outbound["password"] = "<server_key>:<user_key>"
        elif server:
            outbound["server"] = server.ip
            outbound["server_port"] = int(port_override or 1080)
            outbound["method"] = "2022-blake3-aes-128-gcm"
            outbound["password"] = ""
        else:
            outbound["server"] = data.get("host", "0.0.0.0")
            outbound["server_port"] = int(port_override or 1080)
            outbound["method"] = "2022-blake3-aes-128-gcm"
            outbound["password"] = ""

    elif protocol == "hysteria2":
        outbound["type"] = "hysteria2"
        if server:
            outbound["server"] = server.fqdn or server.ip
            outbound["server_port"] = int(port_override) if port_override else server.hysteria2_port
            if vpn_user:
                outbound["password"] = vpn_user.hysteria2_password
            outbound["tls"] = {
                "enabled": True,
                "server_name": server.fqdn or server.ip,
            }
        else:
            outbound["server"] = data.get("host", "0.0.0.0")
            outbound["server_port"] = int(port_override or 443)
            outbound["tls"] = {"enabled": True}

    elif protocol == "vless":
        outbound["type"] = "vless"
        transport = data.get("transport", "tcp")
        if server:
            outbound["server"] = server.ip
            outbound["server_port"] = int(port_override) if port_override else server.reality_port
            if vpn_user:
                outbound["uuid"] = str(vpn_user.uuid)
            outbound["flow"] = "xtls-rprx-vision"
            outbound["tls"] = {
                "enabled": True,
                "server_name": server.reality_server_name or "dl.google.com",
                "utls": {"enabled": True, "fingerprint": "chrome"},
                "reality": {
                    "enabled": True,
                    "public_key": server.reality_public_key or "",
                    "short_id": server.reality_short_id or "",
                },
            }
        else:
            outbound["server"] = data.get("host", "0.0.0.0")
            outbound["server_port"] = int(port_override or 443)
            outbound["tls"] = {"enabled": True}

        if transport and transport != "tcp":
            outbound["transport"] = {"type": transport}

    else:
        # Fallback: treat as direct
        outbound["type"] = "direct"

    # MUX
    if data.get("mux"):
        outbound["multiplex"] = {
            "enabled": True,
            "protocol": "h2mux",
            "max_connections": 4,
        }

    # Padding
    if data.get("padding"):
        outbound.setdefault("tls", {})["padding"] = True

    # Detour (chain to next hop)
    if detour_tag:
        outbound["detour"] = detour_tag

    return outbound


def _build_route_rule(
    rule_type: str,
    value: str,
    outbound_tag: str,
    rule_sets: list[dict],
) -> dict | None:
    """Build a single sing-box route rule from a Route node rule."""
    if rule_type.startswith("geoip:"):
        country = rule_type.split(":", 1)[1].lower() if ":" in rule_type else value.lower()
        tag = f"geoip-{country}"
        rule_sets.append({
            "tag": tag,
            "type": "remote",
            "format": "binary",
            "url": f"https://raw.githubusercontent.com/SagerNet/sing-geoip/rule-set/geoip-{country}.srs",
        })
        return {"rule_set": tag, "outbound": outbound_tag}

    if rule_type.startswith("geosite:"):
        category = rule_type.split(":", 1)[1].lower() if ":" in rule_type else value.lower()
        tag = f"geosite-{category}"
        rule_sets.append({
            "tag": tag,
            "type": "remote",
            "format": "binary",
            "url": f"https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-{category}.srs",
        })
        return {"rule_set": tag, "outbound": outbound_tag}

    if rule_type == "domain_suffix":
        suffixes = [s.strip() for s in value.split(",") if s.strip()]
        return {"domain_suffix": suffixes, "outbound": outbound_tag}

    if rule_type == "ip_cidr":
        cidrs = [s.strip() for s in value.split(",") if s.strip()]
        return {"ip_cidr": cidrs, "outbound": outbound_tag}

    if rule_type == "domain":
        domains = [s.strip() for s in value.split(",") if s.strip()]
        return {"domain": domains, "outbound": outbound_tag}

    if rule_type == "domain_keyword":
        keywords = [s.strip() for s in value.split(",") if s.strip()]
        return {"domain_keyword": keywords, "outbound": outbound_tag}

    return None


def _build_dns(exit_outbound: str) -> dict:
    """Build the DNS section for the client config."""
    return {
        "servers": [
            {
                "tag": "dns-remote",
                "address": "https://1.1.1.1/dns-query",
                "address_resolver": "dns-resolver",
                "detour": exit_outbound,
            },
            {
                "tag": "dns-direct",
                "address": "https://8.8.8.8/dns-query",
                "address_resolver": "dns-resolver",
                "detour": "direct",
            },
            {
                "tag": "dns-resolver",
                "address": "8.8.8.8",
                "detour": "direct",
            },
        ],
        "rules": [
            {"outbound": "any", "server": "dns-resolver"},
        ],
        "final": "dns-remote",
    }
