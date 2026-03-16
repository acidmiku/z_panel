"""Servers router."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from arq.connections import create_pool
from arq.connections import RedisSettings

from app.database import get_db
from app.models import Server, CloudflareConfig, SSHKey, AdminUser, ServerTrafficSnapshot
from app.schemas import ServerCreate, ServerBatchCreate, ServerUpdate, ServerResponse, MtproxyInstallRequest
from app.deps import get_current_user
from app.services.cloudflare import delete_dns_record
from app.services.crypto import decrypt
from app.services import ssh
from app.config import settings

router = APIRouter()


async def _get_arq_pool():
    from app.worker import _parse_redis_url
    return await create_pool(_parse_redis_url(settings.REDIS_URL))


@router.get("", response_model=List[ServerResponse])
async def list_servers(
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(Server).order_by(Server.created_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=ServerResponse, status_code=201)
async def add_server(
    body: ServerCreate,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    # Validate references
    ssh_result = await db.execute(select(SSHKey).where(SSHKey.id == body.ssh_key_id))
    if not ssh_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="SSH key not found")

    cf_result = await db.execute(select(CloudflareConfig).where(CloudflareConfig.id == body.cf_config_id))
    if not cf_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Cloudflare config not found")

    server = Server(
        name=body.name,
        ip=body.ip,
        ssh_port=body.ssh_port,
        ssh_user=body.ssh_user,
        ssh_key_id=body.ssh_key_id,
        cf_config_id=body.cf_config_id,
        hysteria2_port=body.hysteria2_port,
        reality_port=body.reality_port,
        reality_dest=body.reality_dest,
        reality_server_name=body.reality_server_name,
        subdomain_prefix=body.subdomain_prefix,
        mtproxy_tls_domain=body.mtproxy_tls_domain if body.install_mtproxy else None,
        mtproxy_port=body.mtproxy_port if body.install_mtproxy else None,
        status="provisioning",
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)

    # Enqueue provisioning task
    pool = await _get_arq_pool()
    await pool.enqueue_job("task_provision_server", str(server.id))
    await pool.close()

    return server


@router.post("/batch", response_model=List[ServerResponse], status_code=201)
async def batch_add_servers(
    body: ServerBatchCreate,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    ips = [ip.strip() for ip in body.ips if ip.strip()]
    if not ips:
        raise HTTPException(status_code=400, detail="No IPs provided")

    ssh_result = await db.execute(select(SSHKey).where(SSHKey.id == body.ssh_key_id))
    if not ssh_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="SSH key not found")

    cf_result = await db.execute(select(CloudflareConfig).where(CloudflareConfig.id == body.cf_config_id))
    if not cf_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Cloudflare config not found")

    created = []
    for i, ip in enumerate(ips, 1):
        server = Server(
            name=f"{body.name_prefix}-{i}",
            ip=ip,
            ssh_port=body.ssh_port,
            ssh_user=body.ssh_user,
            ssh_key_id=body.ssh_key_id,
            cf_config_id=body.cf_config_id,
            hysteria2_port=body.hysteria2_port,
            reality_port=body.reality_port,
            reality_dest=body.reality_dest,
            reality_server_name=body.reality_server_name,
            subdomain_prefix=body.subdomain_prefix,
            mtproxy_tls_domain=body.mtproxy_tls_domain if body.install_mtproxy else None,
            mtproxy_port=body.mtproxy_port if body.install_mtproxy else None,
            status="provisioning",
        )
        db.add(server)
        created.append(server)

    await db.commit()
    for s in created:
        await db.refresh(s)

    pool = await _get_arq_pool()
    for s in created:
        await pool.enqueue_job("task_provision_server", str(s.id))
    await pool.close()

    return created


@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


@router.patch("/{server_id}", response_model=ServerResponse)
async def update_server(
    server_id: str,
    body: ServerUpdate,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(server, field, value)

    await db.commit()
    await db.refresh(server)
    return server


@router.delete("/{server_id}")
async def delete_server(
    server_id: str,
    force: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    # Try to stop sing-box and clean up on remote (skip if force=true)
    if not force and server.status in ("online", "error") and server.ssh_key_id:
        try:
            ssh_result = await db.execute(select(SSHKey).where(SSHKey.id == server.ssh_key_id))
            ssh_key = ssh_result.scalar_one_or_none()
            if ssh_key:
                await ssh.run_command(
                    server.ip, server.ssh_port, server.ssh_user, ssh_key.private_key_path,
                    "systemctl stop sing-box; systemctl disable sing-box; apt-get remove -y sing-box || true",
                    timeout=30, known_host_key=server.host_key,
                )
        except Exception:
            pass  # Best effort

    # Delete CF DNS record
    if server.cf_dns_record_id and server.cf_config_id:
        try:
            cf_result = await db.execute(
                select(CloudflareConfig).where(CloudflareConfig.id == server.cf_config_id)
            )
            cf_config = cf_result.scalar_one_or_none()
            if cf_config:
                cf_token = decrypt(cf_config.api_token)
                await delete_dns_record(cf_token, cf_config.zone_id, server.cf_dns_record_id)
        except Exception:
            pass  # Best effort

    await db.delete(server)
    await db.commit()
    return {"message": "Server deleted"}


@router.post("/{server_id}/sync")
async def sync_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    pool = await _get_arq_pool()
    await pool.enqueue_job("task_push_config", str(server.id))
    await pool.close()

    return {"message": "Config sync queued"}


@router.post("/{server_id}/reinstall")
async def reinstall_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    # Delete old CF DNS record if it exists (a new one will be created)
    if server.cf_dns_record_id and server.cf_config_id:
        try:
            cf_result = await db.execute(
                select(CloudflareConfig).where(CloudflareConfig.id == server.cf_config_id)
            )
            cf_config = cf_result.scalar_one_or_none()
            if cf_config:
                cf_token = decrypt(cf_config.api_token)
                await delete_dns_record(cf_token, cf_config.zone_id, server.cf_dns_record_id)
        except Exception:
            pass  # Best effort

    # Reset provisioning state (host_key preserved — same server, same key)
    server.status = "provisioning"
    server.status_message = None
    server.hardened = False
    server.reality_private_key = None
    server.reality_public_key = None
    server.reality_short_id = None
    server.subdomain = None
    server.fqdn = None
    server.cf_dns_record_id = None
    server.sing_box_version = None
    server.last_health_check = None
    db.add(server)
    await db.commit()

    pool = await _get_arq_pool()
    await pool.enqueue_job("task_provision_server", str(server.id))
    await pool.close()

    return {"message": "Reinstall started"}


@router.get("/{server_id}/traffic-history")
async def get_traffic_history(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Server not found")

    snap_result = await db.execute(
        select(ServerTrafficSnapshot)
        .where(ServerTrafficSnapshot.server_id == server_id)
        .order_by(ServerTrafficSnapshot.recorded_at.asc())
    )
    snapshots = list(snap_result.scalars().all())

    # Compute rates from consecutive snapshots
    rates = []
    for i in range(1, len(snapshots)):
        prev, curr = snapshots[i - 1], snapshots[i]
        dt = (curr.recorded_at - prev.recorded_at).total_seconds()
        if dt <= 0:
            continue
        # Handle counter resets (reboot)
        rx_diff = curr.bytes_rx - prev.bytes_rx
        tx_diff = curr.bytes_tx - prev.bytes_tx
        if rx_diff < 0:
            rx_diff = curr.bytes_rx
        if tx_diff < 0:
            tx_diff = curr.bytes_tx
        rates.append({
            "timestamp": curr.recorded_at.isoformat(),
            "rx_rate": round(rx_diff / dt),
            "tx_rate": round(tx_diff / dt),
        })

    return {"server_id": server_id, "rates": rates}


@router.post("/{server_id}/install-mtproxy")
async def install_mtproxy(
    server_id: str,
    body: MtproxyInstallRequest,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    if server.mtproxy_enabled:
        raise HTTPException(status_code=400, detail="MTProxy is already installed")

    if server.status not in ("online", "error"):
        raise HTTPException(status_code=400, detail=f"Server must be online (current: {server.status})")

    pool = await _get_arq_pool()
    await pool.enqueue_job("task_install_mtproxy_server", str(server.id), body.port, body.tls_domain)
    await pool.close()

    return {"message": "MTProxy installation queued"}


@router.delete("/{server_id}/uninstall-mtproxy")
async def uninstall_mtproxy(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    if not server.mtproxy_enabled:
        raise HTTPException(status_code=400, detail="MTProxy is not installed")

    pool = await _get_arq_pool()
    await pool.enqueue_job("task_uninstall_mtproxy_server", str(server.id))
    await pool.close()

    return {"message": "MTProxy uninstall queued"}


@router.get("/{server_id}/logs")
async def get_server_logs(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    if not server.ssh_key_id:
        raise HTTPException(status_code=400, detail="No SSH key configured")

    ssh_result = await db.execute(select(SSHKey).where(SSHKey.id == server.ssh_key_id))
    ssh_key = ssh_result.scalar_one_or_none()
    if not ssh_key:
        raise HTTPException(status_code=400, detail="SSH key not found")

    try:
        stdout, stderr, code = await ssh.run_command(
            server.ip, server.ssh_port, server.ssh_user, ssh_key.private_key_path,
            "journalctl -u sing-box --no-pager -n 50 --output=short-iso 2>/dev/null || echo 'No journal logs available'",
            timeout=15, known_host_key=server.host_key,
        )
        logs = stdout.strip() if stdout.strip() else "No output"
    except Exception as e:
        logs = f"Failed to fetch logs: {str(e)}"

    return {"logs": logs}
