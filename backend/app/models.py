"""SQLAlchemy ORM models."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, BigInteger, Boolean, Text, DateTime,
    ForeignKey, UniqueConstraint, Index, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID, INET, JSON
from sqlalchemy.orm import relationship
from app.database import Base


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CloudflareConfig(Base):
    __tablename__ = "cloudflare_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    api_token = Column(Text, nullable=False)  # encrypted at rest
    zone_id = Column(String(255), nullable=False)
    base_domain = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    servers = relationship("Server", back_populates="cf_config")


class SSHKey(Base):
    __tablename__ = "ssh_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    private_key_path = Column(String(512), nullable=False)
    fingerprint = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    servers = relationship("Server", back_populates="ssh_key")
    jumphosts = relationship("Jumphost", back_populates="ssh_key")


class Server(Base):
    __tablename__ = "servers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    ip = Column(String(45), nullable=False)  # Using String instead of INET for simplicity
    ssh_port = Column(Integer, default=22)
    ssh_key_id = Column(UUID(as_uuid=True), ForeignKey("ssh_keys.id"), nullable=False)
    ssh_user = Column(String(255), default="root")
    cf_config_id = Column(UUID(as_uuid=True), ForeignKey("cloudflare_configs.id"), nullable=False)
    subdomain = Column(String(255), nullable=True)
    fqdn = Column(String(255), nullable=True)
    cf_dns_record_id = Column(String(255), nullable=True)
    hysteria2_port = Column(Integer, default=443)
    reality_port = Column(Integer, default=443)
    reality_private_key = Column(Text, nullable=True)
    reality_public_key = Column(Text, nullable=True)
    reality_short_id = Column(String(16), nullable=True)
    reality_dest = Column(String(255), default="dl.google.com:443")
    reality_server_name = Column(String(255), default="dl.google.com")
    subdomain_prefix = Column(String(50), nullable=True)
    host_key = Column(Text, nullable=True)  # SSH host key (base64), pinned on first connect
    hardened = Column(Boolean, default=False)
    status = Column(String(20), default="provisioning")  # provisioning, online, offline, error
    status_message = Column(Text, nullable=True)
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    sing_box_version = Column(String(50), nullable=True)
    system_stats = Column(JSON, nullable=True)
    traffic_cache = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    ssh_key = relationship("SSHKey", back_populates="servers")
    cf_config = relationship("CloudflareConfig", back_populates="servers")
    traffic_records = relationship("ServerUserTraffic", back_populates="server", cascade="all, delete-orphan")
    traffic_snapshots = relationship("ServerTrafficSnapshot", back_populates="server", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, nullable=False)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    hysteria2_password = Column(String(255), nullable=False)
    sub_token = Column(String(64), unique=True, nullable=True, index=True)
    traffic_limit_bytes = Column(BigInteger, nullable=True)
    traffic_used_bytes = Column(BigInteger, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    traffic_records = relationship("ServerUserTraffic", back_populates="user", cascade="all, delete-orphan")
    routing_rules = relationship("RoutingRule", back_populates="user", cascade="all, delete-orphan")
    routing_config = relationship("UserRoutingConfig", back_populates="user", uselist=False, cascade="all, delete-orphan")


class ServerUserTraffic(Base):
    __tablename__ = "server_user_traffic"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id = Column(UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    bytes_up = Column(BigInteger, default=0)
    bytes_down = Column(BigInteger, default=0)
    recorded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("server_id", "user_id", "recorded_at", name="uq_server_user_traffic"),
    )

    server = relationship("Server", back_populates="traffic_records")
    user = relationship("User", back_populates="traffic_records")


class ServerTrafficSnapshot(Base):
    __tablename__ = "server_traffic_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id = Column(UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False)
    bytes_rx = Column(BigInteger, default=0)
    bytes_tx = Column(BigInteger, default=0)
    recorded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_traffic_snapshots_server_time", "server_id", "recorded_at"),
    )

    server = relationship("Server", back_populates="traffic_snapshots")


# ---------------------------------------------------------------------------
# Jumphosts
# ---------------------------------------------------------------------------

class Jumphost(Base):
    __tablename__ = "jumphosts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    ip = Column(String(45), nullable=False)
    ssh_port = Column(Integer, default=22)
    ssh_user = Column(String(255), default="root")
    ssh_key_id = Column(UUID(as_uuid=True), ForeignKey("ssh_keys.id"), nullable=False)
    host_key = Column(Text, nullable=True)
    shadowsocks_port = Column(Integer, nullable=True)
    shadowsocks_method = Column(String(100), default="2022-blake3-aes-128-gcm")
    shadowsocks_server_key = Column(Text, nullable=True)  # encrypted, 16-byte PSK base64
    tunnel_private_key = Column(Text, nullable=True)  # encrypted, ed25519 PEM for SSH tunnel
    status = Column(String(20), default="provisioning")
    status_message = Column(Text, nullable=True)
    hardened = Column(Boolean, default=False)
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    sing_box_version = Column(String(50), nullable=True)
    system_stats = Column(JSON, nullable=True)
    traffic_cache = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    ssh_key = relationship("SSHKey", back_populates="jumphosts")
    traffic_snapshots = relationship("JumphostTrafficSnapshot", back_populates="jumphost", cascade="all, delete-orphan")


class JumphostTrafficSnapshot(Base):
    __tablename__ = "jumphost_traffic_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jumphost_id = Column(UUID(as_uuid=True), ForeignKey("jumphosts.id", ondelete="CASCADE"), nullable=False)
    bytes_rx = Column(BigInteger, default=0)
    bytes_tx = Column(BigInteger, default=0)
    recorded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_jh_traffic_snapshots_jh_time", "jumphost_id", "recorded_at"),
    )

    jumphost = relationship("Jumphost", back_populates="traffic_snapshots")


# ---------------------------------------------------------------------------
# Routing Rules
# ---------------------------------------------------------------------------

class RoutingRule(Base):
    __tablename__ = "routing_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    domain_pattern = Column(String(500), nullable=False)
    match_type = Column(String(30), nullable=False, default="domain-suffix")  # domain/domain-suffix/domain-keyword/domain-regex
    action = Column(String(10), nullable=False, default="proxy")  # proxy/direct
    order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="routing_rules")


class UserRoutingConfig(Base):
    __tablename__ = "user_routing_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    geo_rules = Column(JSON, nullable=True)  # list of enabled geo rule IDs
    jumphost_id = Column(UUID(as_uuid=True), ForeignKey("jumphosts.id", ondelete="SET NULL"), nullable=True)
    jumphost_protocol = Column(String(10), default="ss")  # "ss" or "ssh"
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="routing_config")
    jumphost = relationship("Jumphost")


# ---------------------------------------------------------------------------
# Chain Configs (Visual Proxy Chain Editor)
# ---------------------------------------------------------------------------

class ChainConfig(Base):
    __tablename__ = "chain_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    graph_data = Column(JSON, nullable=False)
    generated_config = Column(JSON, nullable=True)
    is_valid = Column(Boolean, default=False)
    validation_errors = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    owner = relationship("AdminUser")
