"""Jumphosts router."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from arq.connections import create_pool

from app.database import get_db
from app.models import Jumphost, SSHKey, AdminUser, JumphostTrafficSnapshot
from app.schemas import JumphostCreate, JumphostUpdate, JumphostResponse
from app.deps import get_current_user
from app.services import ssh
from app.config import settings

router = APIRouter()


async def _get_arq_pool():
    from app.worker import _parse_redis_url
    return await create_pool(_parse_redis_url(settings.REDIS_URL))


@router.get("", response_model=List[JumphostResponse])
async def list_jumphosts(
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(Jumphost).order_by(Jumphost.created_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=JumphostResponse, status_code=201)
async def add_jumphost(
    body: JumphostCreate,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    ssh_result = await db.execute(select(SSHKey).where(SSHKey.id == body.ssh_key_id))
    if not ssh_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="SSH key not found")

    jumphost = Jumphost(
        name=body.name,
        ip=body.ip,
        ssh_port=body.ssh_port,
        ssh_user=body.ssh_user,
        ssh_key_id=body.ssh_key_id,
        status="provisioning",
    )
    db.add(jumphost)
    await db.commit()
    await db.refresh(jumphost)

    pool = await _get_arq_pool()
    await pool.enqueue_job("task_provision_jumphost", str(jumphost.id))
    await pool.close()

    return jumphost


@router.get("/{jumphost_id}", response_model=JumphostResponse)
async def get_jumphost(
    jumphost_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
    jumphost = result.scalar_one_or_none()
    if not jumphost:
        raise HTTPException(status_code=404, detail="Jumphost not found")
    return jumphost


@router.patch("/{jumphost_id}", response_model=JumphostResponse)
async def update_jumphost(
    jumphost_id: str,
    body: JumphostUpdate,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
    jumphost = result.scalar_one_or_none()
    if not jumphost:
        raise HTTPException(status_code=404, detail="Jumphost not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(jumphost, field, value)

    await db.commit()
    await db.refresh(jumphost)
    return jumphost


@router.delete("/{jumphost_id}")
async def delete_jumphost(
    jumphost_id: str,
    force: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
    jumphost = result.scalar_one_or_none()
    if not jumphost:
        raise HTTPException(status_code=404, detail="Jumphost not found")

    if not force and jumphost.status in ("online", "error") and jumphost.ssh_key_id:
        try:
            ssh_result = await db.execute(select(SSHKey).where(SSHKey.id == jumphost.ssh_key_id))
            ssh_key = ssh_result.scalar_one_or_none()
            if ssh_key:
                await ssh.run_command(
                    jumphost.ip, jumphost.ssh_port, jumphost.ssh_user, ssh_key.private_key_path,
                    "systemctl stop sing-box; systemctl disable sing-box; true",
                    timeout=30, known_host_key=jumphost.host_key,
                )
        except Exception:
            pass

    await db.delete(jumphost)
    await db.commit()
    return {"message": "Jumphost deleted"}


@router.post("/{jumphost_id}/sync")
async def sync_jumphost(
    jumphost_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
    jumphost = result.scalar_one_or_none()
    if not jumphost:
        raise HTTPException(status_code=404, detail="Jumphost not found")

    pool = await _get_arq_pool()
    await pool.enqueue_job("task_push_jumphost_config", str(jumphost.id))
    await pool.close()

    return {"message": "Config sync queued"}


@router.post("/{jumphost_id}/reinstall")
async def reinstall_jumphost(
    jumphost_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
    jumphost = result.scalar_one_or_none()
    if not jumphost:
        raise HTTPException(status_code=404, detail="Jumphost not found")

    jumphost.status = "provisioning"
    jumphost.status_message = None
    jumphost.hardened = False
    jumphost.shadowsocks_server_key = None
    jumphost.shadowsocks_port = None
    jumphost.tunnel_private_key = None
    jumphost.sing_box_version = None
    jumphost.last_health_check = None
    db.add(jumphost)
    await db.commit()

    pool = await _get_arq_pool()
    await pool.enqueue_job("task_provision_jumphost", str(jumphost.id))
    await pool.close()

    return {"message": "Reinstall started"}


@router.get("/{jumphost_id}/traffic-history")
async def get_traffic_history(
    jumphost_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Jumphost not found")

    snap_result = await db.execute(
        select(JumphostTrafficSnapshot)
        .where(JumphostTrafficSnapshot.jumphost_id == jumphost_id)
        .order_by(JumphostTrafficSnapshot.recorded_at.asc())
    )
    snapshots = list(snap_result.scalars().all())

    rates = []
    for i in range(1, len(snapshots)):
        prev, curr = snapshots[i - 1], snapshots[i]
        dt = (curr.recorded_at - prev.recorded_at).total_seconds()
        if dt <= 0:
            continue
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

    return {"jumphost_id": jumphost_id, "rates": rates}


@router.get("/{jumphost_id}/logs")
async def get_jumphost_logs(
    jumphost_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
    jumphost = result.scalar_one_or_none()
    if not jumphost:
        raise HTTPException(status_code=404, detail="Jumphost not found")

    if not jumphost.ssh_key_id:
        raise HTTPException(status_code=400, detail="No SSH key configured")

    ssh_result = await db.execute(select(SSHKey).where(SSHKey.id == jumphost.ssh_key_id))
    ssh_key = ssh_result.scalar_one_or_none()
    if not ssh_key:
        raise HTTPException(status_code=400, detail="SSH key not found")

    try:
        stdout, stderr, code = await ssh.run_command(
            jumphost.ip, jumphost.ssh_port, jumphost.ssh_user, ssh_key.private_key_path,
            "journalctl -u sing-box --no-pager -n 50 --output=short-iso 2>/dev/null || echo 'No journal logs available'",
            timeout=15, known_host_key=jumphost.host_key,
        )
        logs = stdout.strip() if stdout.strip() else "No output"
    except Exception as e:
        logs = f"Failed to fetch logs: {str(e)}"

    return {"logs": logs}
