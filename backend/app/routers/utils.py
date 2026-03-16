"""Utility endpoints."""
import re

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models import AdminUser
from app.deps import get_current_user
from app.services.telemt_installer import suggest_tls_domains

router = APIRouter()

_IP_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


@router.get("/suggest-tls-domain")
async def suggest_tls_domain(
    ip: str = Query(..., min_length=7, max_length=45),
    _: AdminUser = Depends(get_current_user),
):
    if not _IP_RE.match(ip) or any(int(p) > 255 for p in ip.split(".")):
        raise HTTPException(status_code=400, detail="Invalid IPv4 address")
    suggestions = suggest_tls_domains(ip)
    return {"ip": ip, "suggestions": suggestions}
