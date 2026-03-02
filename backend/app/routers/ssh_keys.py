"""SSH keys router."""
import os
import subprocess
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models import SSHKey, Server, AdminUser
from app.schemas import SSHKeyCreate, SSHKeyResponse
from app.deps import get_current_user

router = APIRouter()


def _compute_fingerprint(key_path: str) -> str:
    try:
        result = subprocess.run(
            ["ssh-keygen", "-lf", key_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip().split()[1] if result.stdout.strip() else ""
    except Exception:
        pass
    return ""


@router.get("", response_model=List[SSHKeyResponse])
async def list_keys(
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(SSHKey).order_by(SSHKey.created_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=SSHKeyResponse, status_code=201)
async def register_key(
    body: SSHKeyCreate,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    if not os.path.isfile(body.private_key_path):
        raise HTTPException(status_code=400, detail="SSH key file not found")

    fingerprint = _compute_fingerprint(body.private_key_path)

    key = SSHKey(
        name=body.name,
        private_key_path=body.private_key_path,
        fingerprint=fingerprint,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return key


@router.delete("/{key_id}")
async def delete_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    result = await db.execute(select(SSHKey).where(SSHKey.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="SSH key not found")

    srv_result = await db.execute(select(Server).where(Server.ssh_key_id == key_id))
    if srv_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Cannot delete: servers still reference this key")

    await db.delete(key)
    await db.commit()
    return {"message": "Deleted"}
