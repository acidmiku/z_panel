"""Generate Clash Meta (mihomo) YAML configuration."""
import base64
import hashlib
from typing import List, Optional
import yaml

from app.models import Server, User, Jumphost, RoutingRule
from app.services.crypto import decrypt


# Available geo rule-providers from MetaCubeX (classical format)
GEO_RULE_PROVIDERS = {
    "geoip-ru": {
        "url": "https://github.com/MetaCubeX/meta-rules-dat/raw/meta/geo/geoip/classical/ru.yaml",
        "type": "http",
        "behavior": "classical",
        "interval": 432000,
        "label": "GeoIP Russia",
        "default_action": "DIRECT",
    },
    "geosite-ru": {
        "url": "https://github.com/MetaCubeX/meta-rules-dat/raw/meta/geo/geosite/classical/category-ru.yaml",
        "type": "http",
        "behavior": "classical",
        "interval": 86400,
        "label": "Sites Russia",
        "default_action": "DIRECT",
    },
    "geoip-cn": {
        "url": "https://github.com/MetaCubeX/meta-rules-dat/raw/meta/geo/geoip/classical/cn.yaml",
        "type": "http",
        "behavior": "classical",
        "interval": 432000,
        "label": "GeoIP China",
        "default_action": "DIRECT",
    },
    "geosite-cn": {
        "url": "https://github.com/MetaCubeX/meta-rules-dat/raw/meta/geo/geosite/classical/cn.yaml",
        "type": "http",
        "behavior": "classical",
        "interval": 86400,
        "label": "Sites China",
        "default_action": "DIRECT",
    },
    "geosite-category-ads-all": {
        "url": "https://github.com/MetaCubeX/meta-rules-dat/raw/meta/geo/geosite/classical/category-ads-all.yaml",
        "type": "http",
        "behavior": "classical",
        "interval": 86400,
        "label": "Ads (Block)",
        "default_action": "REJECT",
    },
    "geosite-private": {
        "url": "https://github.com/MetaCubeX/meta-rules-dat/raw/meta/geo/geosite/classical/private.yaml",
        "type": "http",
        "behavior": "classical",
        "interval": 86400,
        "label": "Private/LAN",
        "default_action": "DIRECT",
    },
    "geosite-google": {
        "url": "https://github.com/MetaCubeX/meta-rules-dat/raw/meta/geo/geosite/classical/google.yaml",
        "type": "http",
        "behavior": "classical",
        "interval": 86400,
        "label": "Google",
        "default_action": "Proxy",
    },
    "geosite-youtube": {
        "url": "https://github.com/MetaCubeX/meta-rules-dat/raw/meta/geo/geosite/classical/youtube.yaml",
        "type": "http",
        "behavior": "classical",
        "interval": 86400,
        "label": "YouTube",
        "default_action": "Proxy",
    },
    "geosite-telegram": {
        "url": "https://github.com/MetaCubeX/meta-rules-dat/raw/meta/geo/geosite/classical/telegram.yaml",
        "type": "http",
        "behavior": "classical",
        "interval": 86400,
        "label": "Telegram",
        "default_action": "Proxy",
    },
    "geosite-openai": {
        "url": "https://github.com/MetaCubeX/meta-rules-dat/raw/meta/geo/geosite/classical/openai.yaml",
        "type": "http",
        "behavior": "classical",
        "interval": 86400,
        "label": "OpenAI",
        "default_action": "Proxy",
    },
    "geosite-netflix": {
        "url": "https://github.com/MetaCubeX/meta-rules-dat/raw/meta/geo/geosite/classical/netflix.yaml",
        "type": "http",
        "behavior": "classical",
        "interval": 86400,
        "label": "Netflix",
        "default_action": "Proxy",
    },
    "geosite-apple": {
        "url": "https://github.com/MetaCubeX/meta-rules-dat/raw/meta/geo/geosite/classical/apple.yaml",
        "type": "http",
        "behavior": "classical",
        "interval": 86400,
        "label": "Apple",
        "default_action": "DIRECT",
    },
    "geosite-microsoft": {
        "url": "https://github.com/MetaCubeX/meta-rules-dat/raw/meta/geo/geosite/classical/microsoft.yaml",
        "type": "http",
        "behavior": "classical",
        "interval": 86400,
        "label": "Microsoft",
        "default_action": "DIRECT",
    },
    "geosite-geolocation-!cn": {
        "url": "https://github.com/MetaCubeX/meta-rules-dat/raw/meta/geo/geosite/classical/geolocation-!cn.yaml",
        "type": "http",
        "behavior": "classical",
        "interval": 86400,
        "label": "Non-China Sites",
        "default_action": "Proxy",
    },
}


def _derive_user_ss_key(hysteria2_password: str) -> str:
    """Derive per-user Shadowsocks 2022 key (must match jumphost_singbox_config)."""
    digest = hashlib.pbkdf2_hmac(
        'sha256', hysteria2_password.encode(),
        b'zpanel-ss2022-user-key-v1', 100_000,
    )[:16]
    return base64.b64encode(digest).decode()


def generate_clash_config(
    user: User,
    servers: List[Server],
    strategy: str = "url-test",
    jumphost: Optional[Jumphost] = None,
    jumphost_protocol: Optional[str] = None,
    routing_rules: Optional[List[RoutingRule]] = None,
    geo_rules: Optional[List[dict]] = None,
) -> str:
    proxies = []
    hy2_names = []
    vless_names = []

    # Add jumphost proxy entry if configured
    jh_proxy_name = None
    if jumphost and jumphost.status == "online":
        if jumphost_protocol == "ssh" and jumphost.tunnel_private_key:
            tunnel_key = decrypt(jumphost.tunnel_private_key)
            jh_proxy_name = f"jh-{jumphost.name}"
            proxies.append({
                "name": jh_proxy_name,
                "type": "ssh",
                "server": jumphost.ip,
                "port": jumphost.ssh_port,
                "username": jumphost.ssh_user,
                "private-key": tunnel_key,
            })
        else:
            # Default: Shadowsocks
            server_key = decrypt(jumphost.shadowsocks_server_key)
            user_key = _derive_user_ss_key(user.hysteria2_password)
            jh_proxy_name = f"jh-{jumphost.name}"
            proxies.append({
                "name": jh_proxy_name,
                "type": "ss",
                "server": jumphost.ip,
                "port": jumphost.shadowsocks_port,
                "cipher": jumphost.shadowsocks_method,
                "password": f"{server_key}:{user_key}",
            })

    for server in servers:
        if server.status != "online":
            continue

        hy2_entry = {
            "name": f"{server.name}-hysteria2",
            "type": "hysteria2",
            "server": server.fqdn,
            "port": server.hysteria2_port,
            "password": user.hysteria2_password,
            "sni": server.fqdn,
        }
        if jh_proxy_name:
            hy2_entry["dialer-proxy"] = jh_proxy_name
        proxies.append(hy2_entry)
        hy2_names.append(hy2_entry["name"])

        vless_entry = {
            "name": f"{server.name}-vless-reality",
            "type": "vless",
            "server": server.ip,
            "port": server.reality_port,
            "uuid": str(user.uuid),
            "network": "tcp",
            "tls": True,
            "flow": "xtls-rprx-vision",
            "servername": server.reality_server_name,
            "reality-opts": {
                "public-key": server.reality_public_key,
                "short-id": server.reality_short_id,
            },
            "client-fingerprint": "chrome",
        }
        if jh_proxy_name:
            vless_entry["dialer-proxy"] = jh_proxy_name
        proxies.append(vless_entry)
        vless_names.append(vless_entry["name"])

    all_names = hy2_names + vless_names

    proxy_groups = [
        {
            "name": "Proxy",
            "type": strategy,
            "proxies": all_names[:],
            "url": "https://www.gstatic.com/generate_204",
            "interval": 300,
        },
        {
            "name": "Hysteria2",
            "type": strategy,
            "proxies": hy2_names[:],
            "url": "https://www.gstatic.com/generate_204",
            "interval": 300,
        },
    ]

    if vless_names:
        proxy_groups.append({
            "name": "VLESS-Reality",
            "type": strategy,
            "proxies": vless_names[:],
            "url": "https://www.gstatic.com/generate_204",
            "interval": 300,
        })

    proxy_groups.append({
        "name": "Manual",
        "type": "select",
        "proxies": ["Proxy", "Hysteria2"] + (["VLESS-Reality"] if vless_names else []) + ["DIRECT"] + all_names,
    })

    # Build rule-providers and rules from geo_rules and routing_rules
    rule_providers = {}
    rules = []

    # Geo rule-providers
    if geo_rules:
        for entry in geo_rules:
            geo_id = entry.get("id") if isinstance(entry, dict) else entry
            action = entry.get("action", "DIRECT") if isinstance(entry, dict) else "DIRECT"
            provider_def = GEO_RULE_PROVIDERS.get(geo_id)
            if not provider_def:
                continue
            # Write only Clash-relevant fields (strip label/default_action)
            rule_providers[geo_id] = {
                k: v for k, v in provider_def.items()
                if k in ("url", "type", "behavior", "interval")
            }
            rules.append(f"RULE-SET,{geo_id},{action}")

    # Custom routing rules
    if routing_rules:
        sorted_rules = sorted(routing_rules, key=lambda r: r.order)
        match_type_map = {
            "domain": "DOMAIN",
            "domain-suffix": "DOMAIN-SUFFIX",
            "domain-keyword": "DOMAIN-KEYWORD",
            "domain-regex": "DOMAIN-REGEX",
        }
        for rule in sorted_rules:
            clash_type = match_type_map.get(rule.match_type, "DOMAIN-SUFFIX")
            action = "Proxy" if rule.action == "proxy" else "DIRECT"
            rules.append(f"{clash_type},{rule.domain_pattern},{action}")

    # Default rules always at the end
    rules.extend([
        "GEOIP,LAN,DIRECT,no-resolve",
        "GEOIP,CN,DIRECT",
        "MATCH,Proxy",
    ])

    config = {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "unified-delay": True,
        "tcp-concurrent": True,
        "find-process-mode": "strict",
        "global-client-fingerprint": "chrome",
        "dns": {
            "enable": True,
            "listen": "0.0.0.0:1053",
            "enhanced-mode": "fake-ip",
            "fake-ip-range": "198.18.0.1/16",
            "fake-ip-filter": [
                "+.lan",
                "+.local",
                "localhost.ptlogin2.qq.com",
            ],
            "default-nameserver": [
                "223.5.5.5",
                "1.0.0.1",
            ],
            "nameserver": [
                "https://dns.google/dns-query",
                "https://cloudflare-dns.com/dns-query",
            ],
        },
        "proxies": proxies,
        "proxy-groups": proxy_groups,
        "rules": rules,
    }

    if rule_providers:
        config["rule-providers"] = rule_providers

    return yaml.dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False)
