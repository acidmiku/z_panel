"""Generate Clash Meta (mihomo) YAML configuration."""
from typing import List
import yaml

from app.models import Server, User


def generate_clash_config(
    user: User,
    servers: List[Server],
    strategy: str = "url-test",
) -> str:
    proxies = []
    hy2_names = []
    vless_names = []

    for server in servers:
        if server.status != "online":
            continue

        hy2_name = f"{server.name}-hysteria2"
        proxies.append({
            "name": hy2_name,
            "type": "hysteria2",
            "server": server.fqdn,
            "port": server.hysteria2_port,
            "password": user.hysteria2_password,
            "sni": server.fqdn,
        })
        hy2_names.append(hy2_name)

        vless_name = f"{server.name}-vless-reality"
        proxies.append({
            "name": vless_name,
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
        })
        vless_names.append(vless_name)

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
        "rules": [
            "GEOIP,LAN,DIRECT,no-resolve",
            "GEOIP,CN,DIRECT",
            "MATCH,Proxy",
        ],
    }

    return yaml.dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False)
