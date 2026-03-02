"""Generate sing-box JSON configuration for jumphosts (Shadowsocks relay)."""
import base64
import hashlib
import json
from typing import List

from app.models import Jumphost, User
from app.services.crypto import decrypt
from app.services.singbox_config import is_user_active


def _derive_user_key(hysteria2_password: str) -> str:
    """Derive per-user Shadowsocks 2022 key from Hysteria2 password.

    PBKDF2-SHA256(password, salt, 100k iterations)[:16] → base64
    """
    digest = hashlib.pbkdf2_hmac(
        'sha256', hysteria2_password.encode(),
        b'zpanel-ss2022-user-key-v1', 100_000,
    )[:16]
    return base64.b64encode(digest).decode()


def generate_jumphost_singbox_config(jumphost: Jumphost, users: List[User]) -> dict:
    """Generate a sing-box config for a jumphost with Shadowsocks inbound."""
    server_key = decrypt(jumphost.shadowsocks_server_key)

    active_users = [u for u in users if is_user_active(u)]

    ss_users = []
    for u in active_users:
        user_key = _derive_user_key(u.hysteria2_password)
        ss_users.append({
            "name": u.username,
            "password": user_key,
        })

    active_usernames = [u.username for u in active_users]

    config = {
        "experimental": {
            "v2ray_api": {
                "listen": "127.0.0.1:10085",
                "stats": {
                    "enabled": True,
                    "inbounds": ["ss-in"],
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
                "type": "shadowsocks",
                "tag": "ss-in",
                "listen": "::",
                "listen_port": jumphost.shadowsocks_port,
                "sniff": True,
                "sniff_override_destination": False,
                "method": jumphost.shadowsocks_method,
                "password": server_key,
                "users": ss_users,
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
