"""Generate sing-box JSON configuration."""
import json
from datetime import datetime, timezone
from typing import List, Optional

from app.models import Server, User
from app.services.crypto import decrypt


def is_user_active(user: User) -> bool:
    """Check if user should be included in the config."""
    if not user.enabled:
        return False
    if user.expires_at and user.expires_at < datetime.now(timezone.utc):
        return False
    if user.traffic_limit_bytes and user.traffic_used_bytes >= user.traffic_limit_bytes:
        return False
    return True


def generate_singbox_config(server: Server, users: List[User], cf_api_token: str) -> dict:
    """Generate a complete sing-box config for the given server and user list."""
    active_users = [u for u in users if is_user_active(u)]

    hy2_users = [
        {"name": u.username, "password": u.hysteria2_password}
        for u in active_users
    ]

    vless_users = [
        {"name": u.username, "uuid": str(u.uuid), "flow": "xtls-rprx-vision"}
        for u in active_users
    ]

    active_usernames = [u.username for u in active_users]

    config = {
        "experimental": {
            "clash_api": {
                "external_controller": "127.0.0.1:9090",
            },
            "v2ray_api": {
                "listen": "127.0.0.1:10085",
                "stats": {
                    "enabled": True,
                    "inbounds": ["hy2-in", "vless-reality-in"],
                    "users": active_usernames,
                },
            },
        },
        "log": {
            "level": "info",
            "timestamp": True,
        },
        "dns": {
            "servers": [
                {
                    "tag": "cloudflare",
                    "address": "https://1.1.1.1/dns-query",
                    "detour": "direct",
                },
                {
                    "tag": "google",
                    "address": "https://8.8.8.8/dns-query",
                    "detour": "direct",
                },
            ],
            "final": "cloudflare",
            "strategy": "prefer_ipv4",
        },
        "inbounds": [
            {
                "type": "hysteria2",
                "tag": "hy2-in",
                "listen": "::",
                "listen_port": server.hysteria2_port,
                "sniff": True,
                "sniff_override_destination": True,
                "users": hy2_users,
                "tls": {
                    "enabled": True,
                    "acme": {
                        "domain": [server.fqdn],
                        "email": f"acme@{server.fqdn.split('.', 1)[1] if server.fqdn and '.' in server.fqdn else 'example.com'}",
                        "dns01_challenge": {
                            "provider": "cloudflare",
                            "api_token": cf_api_token,
                        },
                    },
                },
            },
            {
                "type": "vless",
                "tag": "vless-reality-in",
                "listen": "::",
                "listen_port": server.reality_port,
                "sniff": True,
                "sniff_override_destination": True,
                "users": vless_users,
                "tls": {
                    "enabled": True,
                    "server_name": server.reality_server_name,
                    "reality": {
                        "enabled": True,
                        "handshake": {
                            "server": server.reality_dest.split(":")[0] if ":" in server.reality_dest else server.reality_dest,
                            "server_port": int(server.reality_dest.split(":")[1]) if ":" in server.reality_dest else 443,
                        },
                        "private_key": decrypt(server.reality_private_key),
                        "short_id": [server.reality_short_id],
                    },
                },
            },
        ],
        "outbounds": [
            {
                "type": "direct",
                "tag": "direct",
                "domain_strategy": "prefer_ipv4",
            },
        ],
        "route": {
            "final": "direct",
        },
    }

    return config


def config_to_json(config: dict) -> str:
    return json.dumps(config, indent=2)
