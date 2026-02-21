"""Cloudflare API integration for DNS management."""
import httpx
from typing import Optional


async def create_dns_record(
    api_token: str,
    zone_id: str,
    name: str,
    ip: str,
) -> str:
    """Create an A record in Cloudflare DNS. Returns the record ID."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
            headers={"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"},
            json={
                "type": "A",
                "name": name,
                "content": ip,
                "ttl": 1,  # auto
                "proxied": False,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise ValueError(f"Cloudflare API error: {data.get('errors')}")
        return data["result"]["id"]


async def delete_dns_record(
    api_token: str,
    zone_id: str,
    record_id: str,
) -> None:
    """Delete a DNS record from Cloudflare."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.delete(
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}",
            headers={"Authorization": f"Bearer {api_token}"},
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise ValueError(f"Cloudflare API error: {data.get('errors')}")
