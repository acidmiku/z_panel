"""Pydantic request/response schemas."""
import re
import uuid
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator


# Auth
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Cloudflare Config
class CloudflareConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    api_token: str = Field(..., min_length=1)
    zone_id: str = Field(..., min_length=1, max_length=255)
    base_domain: str = Field(..., min_length=1, max_length=255)

class CloudflareConfigResponse(BaseModel):
    id: uuid.UUID
    name: str
    zone_id: str
    base_domain: str
    created_at: datetime

    class Config:
        from_attributes = True


# SSH Keys
class SSHKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    private_key_path: str = Field(..., min_length=1, max_length=512)

class SSHKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    private_key_path: str
    fingerprint: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


_IP_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


def _validate_ip(v: str) -> str:
    if not _IP_RE.match(v):
        raise ValueError("Must be a valid IPv4 address")
    parts = v.split(".")
    if any(int(p) > 255 for p in parts):
        raise ValueError("Each octet must be 0-255")
    return v


# Servers
class ServerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    ip: str
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_user: str = Field(default="root", min_length=1, max_length=255)
    ssh_key_id: uuid.UUID
    cf_config_id: uuid.UUID
    hysteria2_port: int = Field(default=443, ge=1, le=65535)
    reality_port: int = Field(default=443, ge=1, le=65535)
    reality_dest: str = "dl.google.com:443"
    reality_server_name: str = "dl.google.com"
    subdomain_prefix: Optional[str] = Field(default=None, max_length=50)

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        return _validate_ip(v)

class ServerBatchCreate(BaseModel):
    ips: List[str]
    name_prefix: str = Field(default="vps", min_length=1, max_length=255)
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_user: str = Field(default="root", min_length=1, max_length=255)
    ssh_key_id: uuid.UUID
    cf_config_id: uuid.UUID
    hysteria2_port: int = Field(default=443, ge=1, le=65535)
    reality_port: int = Field(default=443, ge=1, le=65535)
    reality_dest: str = "dl.google.com:443"
    reality_server_name: str = "dl.google.com"
    subdomain_prefix: Optional[str] = Field(default=None, max_length=50)

    @field_validator("ips")
    @classmethod
    def validate_ips(cls, v: list[str]) -> list[str]:
        return [_validate_ip(ip.strip()) for ip in v if ip.strip()]

class ServerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    ip: Optional[str] = None
    ssh_port: Optional[int] = Field(default=None, ge=1, le=65535)
    ssh_user: Optional[str] = Field(default=None, max_length=255)
    ssh_key_id: Optional[uuid.UUID] = None
    cf_config_id: Optional[uuid.UUID] = None
    hysteria2_port: Optional[int] = Field(default=None, ge=1, le=65535)
    reality_port: Optional[int] = Field(default=None, ge=1, le=65535)
    reality_dest: Optional[str] = None
    reality_server_name: Optional[str] = None
    subdomain_prefix: Optional[str] = Field(default=None, max_length=50)

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_ip(v)
        return v

class ServerResponse(BaseModel):
    id: uuid.UUID
    name: str
    ip: str
    ssh_port: int
    ssh_user: str
    ssh_key_id: uuid.UUID
    cf_config_id: uuid.UUID
    subdomain: Optional[str] = None
    fqdn: Optional[str] = None
    subdomain_prefix: Optional[str] = None
    hysteria2_port: int
    reality_port: int
    reality_public_key: Optional[str] = None
    reality_short_id: Optional[str] = None
    reality_dest: str
    reality_server_name: str
    hardened: bool = False
    status: str
    status_message: Optional[str] = None
    last_health_check: Optional[datetime] = None
    sing_box_version: Optional[str] = None
    system_stats: Optional[dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Users
class UserCreate(BaseModel):
    username: str
    traffic_limit_bytes: Optional[int] = None
    expires_at: Optional[datetime] = None

class UserUpdate(BaseModel):
    username: Optional[str] = None
    traffic_limit_bytes: Optional[int] = None
    expires_at: Optional[datetime] = None
    enabled: Optional[bool] = None

class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    uuid: uuid.UUID
    hysteria2_password: str
    sub_token: Optional[str] = None
    traffic_limit_bytes: Optional[int] = None
    traffic_used_bytes: int = 0
    expires_at: Optional[datetime] = None
    enabled: bool = True
    created_at: datetime

    class Config:
        from_attributes = True

class UserDetailResponse(UserResponse):
    traffic_by_server: Optional[List[dict]] = None


# Traffic
class TrafficRecord(BaseModel):
    server_id: uuid.UUID
    user_id: uuid.UUID
    bytes_up: int
    bytes_down: int
    recorded_at: datetime

    class Config:
        from_attributes = True


# Stats
class StatsResponse(BaseModel):
    total_servers: int
    online_servers: int
    total_jumphosts: int = 0
    online_jumphosts: int = 0
    total_users: int
    active_users: int
    total_traffic_bytes: int


# Password change
class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


# Jumphosts
class JumphostCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    ip: str
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_user: str = Field(default="root", min_length=1, max_length=255)
    ssh_key_id: uuid.UUID

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        return _validate_ip(v)


class JumphostUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    ip: Optional[str] = None
    ssh_port: Optional[int] = Field(default=None, ge=1, le=65535)
    ssh_user: Optional[str] = Field(default=None, max_length=255)
    ssh_key_id: Optional[uuid.UUID] = None

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_ip(v)
        return v


class JumphostResponse(BaseModel):
    id: uuid.UUID
    name: str
    ip: str
    ssh_port: int
    ssh_user: str
    ssh_key_id: uuid.UUID
    shadowsocks_port: Optional[int] = None
    shadowsocks_method: str = "2022-blake3-aes-128-gcm"
    hardened: bool = False
    status: str
    status_message: Optional[str] = None
    last_health_check: Optional[datetime] = None
    sing_box_version: Optional[str] = None
    system_stats: Optional[dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Routing Rules
class RoutingRuleCreate(BaseModel):
    domain_pattern: str = Field(..., min_length=1, max_length=500)
    match_type: str = Field(default="domain-suffix", pattern=r"^(domain|domain-suffix|domain-keyword|domain-regex)$")
    action: str = Field(default="proxy", pattern=r"^(proxy|direct)$")
    order: int = 0


class RoutingRuleUpdate(BaseModel):
    domain_pattern: Optional[str] = Field(default=None, max_length=500)
    match_type: Optional[str] = Field(default=None, pattern=r"^(domain|domain-suffix|domain-keyword|domain-regex)$")
    action: Optional[str] = Field(default=None, pattern=r"^(proxy|direct)$")
    order: Optional[int] = None


class RoutingRuleResponse(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    domain_pattern: str
    match_type: str
    action: str
    order: int
    created_at: datetime

    class Config:
        from_attributes = True


class GeoRuleEntry(BaseModel):
    id: str
    action: str = Field(default="DIRECT", pattern=r"^(DIRECT|Proxy|REJECT)$")


class UserRoutingConfigUpsert(BaseModel):
    geo_rules: Optional[List[GeoRuleEntry]] = None
    jumphost_id: Optional[uuid.UUID] = None
    jumphost_protocol: str = Field(default="ss", pattern=r"^(ss|ssh)$")


class UserRoutingConfigResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    geo_rules: Optional[List[dict]] = None
    jumphost_id: Optional[uuid.UUID] = None
    jumphost_protocol: str = "ss"
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Chain Configs (Visual Proxy Chain Editor)
class ChainConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    graph_data: dict

class ChainConfigUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    graph_data: Optional[dict] = None

class ChainConfigResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: Optional[str] = None
    graph_data: dict
    generated_config: Optional[dict] = None
    is_valid: bool = False
    validation_errors: Optional[List[dict]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ChainConfigListResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    is_valid: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class GraphValidationResult(BaseModel):
    is_valid: bool
    errors: List[dict] = []
    warnings: List[dict] = []
    info: List[dict] = []
