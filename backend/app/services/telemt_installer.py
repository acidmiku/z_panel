"""Telemt (MTProxy) installer service.

Downloads pre-built binary from GitHub releases, generates maximum-security
config (TLS-only, fake-TLS masking, silent logging), creates systemd unit,
opens firewall port, and generates tg:// sharing link.

Also handles TCP relay setup (socat) for jumphost→server relay chains,
and TLS domain auto-suggestion based on IP reverse DNS.
"""
import logging
import secrets
import socket

from sqlalchemy import select

from app.models import Server, Jumphost, SSHKey
from app.services import ssh
from app.services.crypto import encrypt, decrypt
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

TELEMT_VERSION = "3.3.18"
TELEMT_BINARY_URL = (
    f"https://github.com/telemt/telemt/releases/download/{TELEMT_VERSION}"
    f"/telemt-x86_64-linux-gnu.tar.gz"
)


def generate_mtproxy_secret() -> str:
    """Generate a 32-character hex secret for MTProxy."""
    return secrets.token_hex(16)


def generate_tg_link(host: str, port: int, secret: str, tls_domain: str) -> str:
    """Generate tg:// proxy link with fake-TLS (ee prefix) encoding."""
    domain_hex = tls_domain.encode().hex()
    full_secret = f"ee{secret}{domain_hex}"
    return f"tg://proxy?server={host}&port={port}&secret={full_secret}"


def generate_telemt_config(port: int, secret: str, tls_domain: str) -> str:
    """Generate maximum-security telemt config.toml."""
    # Defense-in-depth: strip any characters that could break TOML string literals
    import re
    tls_domain = re.sub(r'[^a-zA-Z0-9.\-]', '', tls_domain)
    secret = re.sub(r'[^a-fA-F0-9]', '', secret)
    return f"""\
# Z Panel managed telemt config — maximum security mode
# DO NOT EDIT MANUALLY — managed by z_panel

[general]
use_middle_proxy = false
log_level = "silent"

[general.modes]
classic = false
secure = false
tls = true

[general.links]
show = "*"
public_port = {port}

[[server.listeners]]
ip = "0.0.0.0"

[server]
port = {port}

[server.api]
enabled = false

[censorship]
tls_domain = "{tls_domain}"
mask = true
tls_emulation = true
tls_front_dir = "/etc/telemt/tlsfront"

[access.users]
proxy = "{secret}"
"""


async def _set_server_progress(server_id: str, message: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.id == server_id))
        srv = result.scalar_one_or_none()
        if srv:
            srv.status_message = message
            await db.commit()


async def _set_jumphost_progress(jumphost_id: str, message: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
        jh = result.scalar_one_or_none()
        if jh:
            jh.status_message = message
            await db.commit()


async def install_telemt(
    host: str,
    port: int,
    username: str,
    key_path: str,
    hk: str,
    mtproxy_port: int,
    secret: str,
    tls_domain: str,
    name: str = "",
) -> int:
    """Install telemt binary, config, and systemd service on a remote host.

    Returns the actual port used (may differ from mtproxy_port if it was taken).
    """
    logger.info(f"[{name}] Installing telemt (MTProxy) on port {mtproxy_port}")

    # Check if requested port is already in use
    stdout, _, _ = await ssh.run_command(
        host, port, username, key_path,
        f"ss -tlnp | grep ':{mtproxy_port} ' | head -1",
        timeout=10, known_host_key=hk,
    )
    if stdout.strip():
        old_port = mtproxy_port
        mtproxy_port = 8443
        # Check 8443 too
        stdout2, _, _ = await ssh.run_command(
            host, port, username, key_path,
            f"ss -tlnp | grep ':{mtproxy_port} ' | head -1",
            timeout=10, known_host_key=hk,
        )
        if stdout2.strip():
            import random
            mtproxy_port = random.randint(10000, 60000)
        logger.warning(f"[{name}] Port {old_port} already in use, using {mtproxy_port} for MTProxy")

    # Download and install binary
    install_script = (
        "set -e && "
        "mkdir -p /etc/telemt/tlsfront && "
        f"curl -sSL '{TELEMT_BINARY_URL}' | tar xz -C /tmp && "
        "mv /tmp/telemt /usr/local/bin/telemt && "
        "chmod +x /usr/local/bin/telemt"
    )
    stdout, stderr, code = await ssh.run_command(
        host, port, username, key_path,
        install_script, timeout=120, known_host_key=hk,
    )
    if code != 0:
        raise RuntimeError(f"telemt binary installation failed: {stderr[:500]}")

    # Write config
    config_content = generate_telemt_config(mtproxy_port, secret, tls_domain)
    await ssh.write_file(
        host, port, username, key_path,
        "/etc/telemt/config.toml", config_content,
        known_host_key=hk,
    )

    # Create systemd service
    service_content = (
        "[Unit]\n"
        "Description=telemt MTProxy\n"
        "After=network.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        "ExecStart=/usr/local/bin/telemt /etc/telemt/config.toml\n"
        "Restart=on-failure\n"
        "RestartSec=5\n"
        "LimitNOFILE=65536\n"
        "\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )
    await ssh.write_file(
        host, port, username, key_path,
        "/etc/systemd/system/telemt.service", service_content,
        known_host_key=hk,
    )

    # Reload systemd, enable and start
    await ssh.run_command(
        host, port, username, key_path,
        "systemctl daemon-reload && systemctl enable telemt && systemctl restart telemt",
        timeout=30, known_host_key=hk,
    )

    # Open port in UFW if active
    ufw_script = (
        f'if command -v ufw &>/dev/null && ufw status | grep -q "Status: active"; then '
        f"ufw allow {mtproxy_port}/tcp comment 'MTProxy' > /dev/null 2>&1; fi"
    )
    await ssh.run_command(host, port, username, key_path, ufw_script, known_host_key=hk)

    # Verify it started and is actually bound to the port
    # telemt needs time for TLS bootstrapping (cert fetch, STUN probes) before binding
    import asyncio as _asyncio
    is_bound = False
    for attempt in range(6):
        await _asyncio.sleep(5)
        stdout, _, _ = await ssh.run_command(
            host, port, username, key_path,
            f"systemctl is-active telemt && ss -tlnp | grep ':{mtproxy_port} '",
            timeout=10, known_host_key=hk,
        )
        lines = stdout.strip().splitlines()
        is_active = lines[0].strip() == "active" if lines else False
        is_bound = any(f":{mtproxy_port} " in line for line in lines)
        if is_bound:
            break
        if not is_active:
            break
        logger.info(f"[{name}] telemt not bound yet (attempt {attempt + 1}/6)")

    if not is_bound:
        log_stdout, _, _ = await ssh.run_command(
            host, port, username, key_path,
            "journalctl -u telemt --no-pager -n 20 --output=cat 2>/dev/null | tail -10",
            timeout=10, known_host_key=hk,
        )
        # Clean up failed install
        await ssh.run_command(
            host, port, username, key_path,
            "systemctl stop telemt 2>/dev/null; systemctl disable telemt 2>/dev/null; true",
            timeout=10, known_host_key=hk,
        )
        raise RuntimeError(f"telemt failed to bind on port {mtproxy_port}: {log_stdout.strip()}")

    logger.info(f"[{name}] telemt installed and running on port {mtproxy_port}")
    return mtproxy_port


async def uninstall_telemt(
    host: str,
    port: int,
    username: str,
    key_path: str,
    hk: str,
    mtproxy_port: int | None = None,
    name: str = "",
) -> None:
    """Stop and remove telemt from a remote host."""
    logger.info(f"[{name}] Uninstalling telemt")

    await ssh.run_command(
        host, port, username, key_path,
        "systemctl stop telemt 2>/dev/null; "
        "systemctl disable telemt 2>/dev/null; "
        "rm -f /etc/systemd/system/telemt.service && "
        "systemctl daemon-reload && "
        "rm -f /usr/local/bin/telemt && "
        "rm -rf /etc/telemt",
        timeout=30, known_host_key=hk,
    )

    if mtproxy_port:
        await ssh.run_command(
            host, port, username, key_path,
            f'if command -v ufw &>/dev/null && ufw status | grep -q "Status: active"; then '
            f"ufw delete allow {mtproxy_port}/tcp > /dev/null 2>&1; fi",
            timeout=10, known_host_key=hk,
        )

    logger.info(f"[{name}] telemt uninstalled")


async def install_mtproxy_on_server(server_id: str, mtproxy_port: int = 443, tls_domain: str = "www.google.com") -> dict:
    """Install telemt on an existing provisioned server."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.id == server_id))
        server = result.scalar_one_or_none()
        if not server:
            raise ValueError("Server not found")

        if server.status not in ("online", "error"):
            raise ValueError(f"Server must be online to install MTProxy (current: {server.status})")

        ssh_result = await db.execute(select(SSHKey).where(SSHKey.id == server.ssh_key_id))
        ssh_key = ssh_result.scalar_one_or_none()
        if not ssh_key:
            raise ValueError("SSH key not found")

    await _set_server_progress(server_id, "Installing MTProxy…")

    secret = generate_mtproxy_secret()
    try:
        actual_port = await install_telemt(
            host=server.ip,
            port=server.ssh_port,
            username=server.ssh_user,
            key_path=ssh_key.private_key_path,
            hk=server.host_key,
            mtproxy_port=mtproxy_port,
            secret=secret,
            tls_domain=tls_domain,
            name=server.name,
        )
    except Exception as e:
        await _set_server_progress(server_id, f"MTProxy install failed: {str(e)[:500]}")
        raise

    link = generate_tg_link(server.ip, actual_port, secret, tls_domain)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.id == server_id))
        srv = result.scalar_one()
        srv.mtproxy_enabled = True
        srv.mtproxy_port = actual_port
        srv.mtproxy_secret = encrypt(secret)
        srv.mtproxy_tls_domain = tls_domain
        srv.mtproxy_link = link
        srv.status_message = None
        await db.commit()

    logger.info(f"[{server.name}] MTProxy installed successfully")
    return {"link": link, "port": actual_port}


async def uninstall_mtproxy_from_server(server_id: str) -> None:
    """Uninstall telemt from a server."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.id == server_id))
        server = result.scalar_one_or_none()
        if not server:
            raise ValueError("Server not found")

        if not server.mtproxy_enabled:
            raise ValueError("MTProxy is not installed on this server")

        ssh_result = await db.execute(select(SSHKey).where(SSHKey.id == server.ssh_key_id))
        ssh_key = ssh_result.scalar_one_or_none()

    await _set_server_progress(server_id, "Uninstalling MTProxy…")

    try:
        await uninstall_telemt(
            host=server.ip,
            port=server.ssh_port,
            username=server.ssh_user,
            key_path=ssh_key.private_key_path,
            hk=server.host_key,
            mtproxy_port=server.mtproxy_port,
            name=server.name,
        )
    except Exception as e:
        logger.error(f"[{server.name}] MTProxy uninstall failed: {e}")

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.id == server_id))
        srv = result.scalar_one()
        srv.mtproxy_enabled = False
        srv.mtproxy_port = None
        srv.mtproxy_secret = None
        srv.mtproxy_tls_domain = None
        srv.mtproxy_link = None
        srv.status_message = None
        await db.commit()


async def install_mtproxy_on_jumphost(jumphost_id: str, mtproxy_port: int = 443, tls_domain: str = "www.google.com") -> dict:
    """Install telemt on an existing provisioned jumphost."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
        jumphost = result.scalar_one_or_none()
        if not jumphost:
            raise ValueError("Jumphost not found")

        if jumphost.status not in ("online", "error"):
            raise ValueError(f"Jumphost must be online to install MTProxy (current: {jumphost.status})")

        ssh_result = await db.execute(select(SSHKey).where(SSHKey.id == jumphost.ssh_key_id))
        ssh_key = ssh_result.scalar_one_or_none()
        if not ssh_key:
            raise ValueError("SSH key not found")

    await _set_jumphost_progress(jumphost_id, "Installing MTProxy…")

    secret = generate_mtproxy_secret()
    try:
        actual_port = await install_telemt(
            host=jumphost.ip,
            port=jumphost.ssh_port,
            username=jumphost.ssh_user,
            key_path=ssh_key.private_key_path,
            hk=jumphost.host_key,
            mtproxy_port=mtproxy_port,
            secret=secret,
            tls_domain=tls_domain,
            name=jumphost.name,
        )
    except Exception as e:
        await _set_jumphost_progress(jumphost_id, f"MTProxy install failed: {str(e)[:500]}")
        raise

    link = generate_tg_link(jumphost.ip, actual_port, secret, tls_domain)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
        jh = result.scalar_one()
        jh.mtproxy_enabled = True
        jh.mtproxy_port = actual_port
        jh.mtproxy_secret = encrypt(secret)
        jh.mtproxy_tls_domain = tls_domain
        jh.mtproxy_link = link
        jh.status_message = None
        await db.commit()

    logger.info(f"[{jumphost.name}] MTProxy installed successfully")
    return {"link": link, "port": actual_port}


async def uninstall_mtproxy_from_jumphost(jumphost_id: str) -> None:
    """Uninstall telemt from a jumphost."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
        jumphost = result.scalar_one_or_none()
        if not jumphost:
            raise ValueError("Jumphost not found")

        if not jumphost.mtproxy_enabled:
            raise ValueError("MTProxy is not installed on this jumphost")

        ssh_result = await db.execute(select(SSHKey).where(SSHKey.id == jumphost.ssh_key_id))
        ssh_key = ssh_result.scalar_one_or_none()

    await _set_jumphost_progress(jumphost_id, "Uninstalling MTProxy…")

    try:
        await uninstall_telemt(
            host=jumphost.ip,
            port=jumphost.ssh_port,
            username=jumphost.ssh_user,
            key_path=ssh_key.private_key_path,
            hk=jumphost.host_key,
            mtproxy_port=jumphost.mtproxy_port,
            name=jumphost.name,
        )
    except Exception as e:
        logger.error(f"[{jumphost.name}] MTProxy uninstall failed: {e}")

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
        jh = result.scalar_one()
        jh.mtproxy_enabled = False
        jh.mtproxy_port = None
        jh.mtproxy_secret = None
        jh.mtproxy_tls_domain = None
        jh.mtproxy_link = None
        jh.mtproxy_relay_server_id = None
        jh.status_message = None
        await db.commit()


# ---------------------------------------------------------------------------
# TLS domain auto-suggestion
# ---------------------------------------------------------------------------

# Map reverse-DNS hostname patterns → suggested fronting domains
_PROVIDER_DOMAINS: list[tuple[str, list[str]]] = [
    # Hetzner
    ("hetzner", ["hetzner.com", "cloud.hetzner.com", "www.hetzner.com"]),
    ("your-server.de", ["hetzner.com", "cloud.hetzner.com"]),
    # DigitalOcean
    ("digitalocean", ["digitalocean.com", "www.digitalocean.com"]),
    # Vultr
    ("vultr", ["vultr.com", "www.vultr.com"]),
    # OVH
    ("ovh", ["ovh.com", "www.ovh.com"]),
    # AWS
    ("amazonaws", ["aws.amazon.com", "console.aws.amazon.com"]),
    ("amazon", ["aws.amazon.com"]),
    # Google Cloud
    ("googleusercontent", ["cloud.google.com", "www.google.com"]),
    ("google", ["www.google.com", "cloud.google.com"]),
    # Azure
    ("azure", ["azure.microsoft.com", "portal.azure.com"]),
    ("microsoft", ["azure.microsoft.com"]),
    # Yandex
    ("yandex", ["yandex.ru", "cloud.yandex.ru", "ya.ru"]),
    # Selectel
    ("selectel", ["selectel.ru", "my.selectel.ru"]),
    # Linode / Akamai
    ("linode", ["linode.com", "www.linode.com"]),
    ("akamai", ["akamai.com", "linode.com"]),
    # Contabo
    ("contabo", ["contabo.com", "www.contabo.com"]),
    # Scaleway
    ("scaleway", ["scaleway.com", "console.scaleway.com"]),
    # Timeweb
    ("timeweb", ["timeweb.cloud", "timeweb.com"]),
    # MVPS / FirstVDS / reg.ru (Russian)
    ("firstvds", ["firstvds.ru", "reg.ru"]),
    ("reg.ru", ["reg.ru", "www.reg.ru"]),
    ("mchost", ["mchost.ru"]),
    # Oracle Cloud
    ("oracle", ["cloud.oracle.com", "oracle.com"]),
    # Cloudflare
    ("cloudflare", ["cloudflare.com", "www.cloudflare.com"]),
]

# Generic safe defaults when provider can't be detected
_DEFAULT_SUGGESTIONS = ["www.google.com", "www.microsoft.com", "cdn.jsdelivr.net"]


def suggest_tls_domains(ip: str) -> list[str]:
    """Suggest plausible TLS fronting domains based on IP reverse DNS."""
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
    except (socket.herror, socket.gaierror, OSError):
        hostname = ""

    hostname_lower = hostname.lower()

    for pattern, domains in _PROVIDER_DOMAINS:
        if pattern in hostname_lower:
            return domains

    return _DEFAULT_SUGGESTIONS


# ---------------------------------------------------------------------------
# MTProxy TCP relay (socat-based)
# ---------------------------------------------------------------------------

async def install_mtproxy_relay(
    jumphost_id: str, server_id: str,
    relay_port: int = 443, tls_domain: str = "www.google.com",
) -> dict:
    """Set up a TCP relay on jumphost forwarding to server's telemt.

    The jumphost runs socat to transparently forward MTProxy traffic.
    DPI sees TLS traffic to a whitelisted jumphost IP.
    """
    async with AsyncSessionLocal() as db:
        jh_result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
        jumphost = jh_result.scalar_one_or_none()
        if not jumphost:
            raise ValueError("Jumphost not found")
        if jumphost.status not in ("online", "error"):
            raise ValueError(f"Jumphost must be online (current: {jumphost.status})")
        if jumphost.mtproxy_enabled:
            raise ValueError("MTProxy is already active on this jumphost (direct or relay)")

        srv_result = await db.execute(select(Server).where(Server.id == server_id))
        server = srv_result.scalar_one_or_none()
        if not server:
            raise ValueError("Server not found")
        if not server.mtproxy_enabled:
            raise ValueError("Server does not have MTProxy installed")

        jh_ssh = await db.execute(select(SSHKey).where(SSHKey.id == jumphost.ssh_key_id))
        jh_key = jh_ssh.scalar_one_or_none()
        if not jh_key:
            raise ValueError("Jumphost SSH key not found")

        server_secret = decrypt(server.mtproxy_secret)
        server_tls_domain = server.mtproxy_tls_domain or tls_domain
        server_telemt_port = server.mtproxy_port

    await _set_jumphost_progress(jumphost_id, "Setting up MTProxy relay…")

    name = jumphost.name

    # Check if relay port is available
    stdout, _, _ = await ssh.run_command(
        jumphost.ip, jumphost.ssh_port, jumphost.ssh_user, jh_key.private_key_path,
        f"ss -tlnp | grep ':{relay_port} ' | head -1",
        timeout=10, known_host_key=jumphost.host_key,
    )
    if stdout.strip():
        old_port = relay_port
        relay_port = 8443
        stdout2, _, _ = await ssh.run_command(
            jumphost.ip, jumphost.ssh_port, jumphost.ssh_user, jh_key.private_key_path,
            f"ss -tlnp | grep ':{relay_port} ' | head -1",
            timeout=10, known_host_key=jumphost.host_key,
        )
        if stdout2.strip():
            import random
            relay_port = random.randint(10000, 60000)
        logger.warning(f"[{name}] Port {old_port} in use, using {relay_port} for relay")

    # Ensure socat is installed
    _, _, code = await ssh.run_command(
        jumphost.ip, jumphost.ssh_port, jumphost.ssh_user, jh_key.private_key_path,
        "command -v socat || (apt-get update -qq && apt-get install -y -qq socat)",
        timeout=60, known_host_key=jumphost.host_key,
    )

    # Create systemd service for the TCP relay
    service_content = (
        "[Unit]\n"
        "Description=MTProxy TCP Relay (socat)\n"
        "After=network.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart=/usr/bin/socat TCP-LISTEN:{relay_port},reuseaddr,fork "
        f"TCP:{server.ip}:{server_telemt_port}\n"
        "Restart=on-failure\n"
        "RestartSec=3\n"
        "LimitNOFILE=65536\n"
        "\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )
    await ssh.write_file(
        jumphost.ip, jumphost.ssh_port, jumphost.ssh_user, jh_key.private_key_path,
        "/etc/systemd/system/telemt-relay.service", service_content,
        known_host_key=jumphost.host_key,
    )

    # Enable and start
    await ssh.run_command(
        jumphost.ip, jumphost.ssh_port, jumphost.ssh_user, jh_key.private_key_path,
        "systemctl daemon-reload && systemctl enable telemt-relay && systemctl restart telemt-relay",
        timeout=30, known_host_key=jumphost.host_key,
    )

    # Open port in UFW
    ufw_script = (
        f'if command -v ufw &>/dev/null && ufw status | grep -q "Status: active"; then '
        f"ufw allow {relay_port}/tcp comment 'MTProxy-Relay' > /dev/null 2>&1; fi"
    )
    await ssh.run_command(
        jumphost.ip, jumphost.ssh_port, jumphost.ssh_user, jh_key.private_key_path,
        ufw_script, known_host_key=jumphost.host_key,
    )

    # Verify relay is listening
    import asyncio as _asyncio
    await _asyncio.sleep(2)
    stdout, _, _ = await ssh.run_command(
        jumphost.ip, jumphost.ssh_port, jumphost.ssh_user, jh_key.private_key_path,
        f"systemctl is-active telemt-relay && ss -tlnp | grep ':{relay_port} '",
        timeout=10, known_host_key=jumphost.host_key,
    )
    lines = stdout.strip().splitlines()
    is_active = lines[0].strip() == "active" if lines else False
    is_bound = any(f":{relay_port} " in line for line in lines)

    if not is_bound:
        raise RuntimeError(f"Relay failed to bind on port {relay_port}")

    # If the user chose a different tls_domain, reconfigure server's telemt
    if tls_domain != server_tls_domain:
        try:
            await _reconfigure_server_tls_domain(server_id, tls_domain, server_secret)
        except Exception as e:
            logger.warning(f"Could not reconfigure server TLS domain: {e}")
        server_tls_domain = tls_domain

    # Generate tg:// link with jumphost IP
    link = generate_tg_link(jumphost.ip, relay_port, server_secret, server_tls_domain)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
        jh = result.scalar_one()
        jh.mtproxy_enabled = True
        jh.mtproxy_port = relay_port
        jh.mtproxy_secret = encrypt(server_secret)
        jh.mtproxy_tls_domain = server_tls_domain
        jh.mtproxy_link = link
        jh.mtproxy_relay_server_id = server_id
        jh.status_message = None
        await db.commit()

    logger.info(f"[{name}] MTProxy relay to {server.name}:{server_telemt_port} on port {relay_port}")
    return {"link": link, "port": relay_port}


async def _reconfigure_server_tls_domain(server_id: str, tls_domain: str, secret: str) -> None:
    """Update a server's telemt config with a new TLS domain."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.id == server_id))
        server = result.scalar_one_or_none()
        if not server or not server.mtproxy_enabled:
            return

        ssh_result = await db.execute(select(SSHKey).where(SSHKey.id == server.ssh_key_id))
        ssh_key = ssh_result.scalar_one_or_none()
        if not ssh_key:
            return

    config_content = generate_telemt_config(server.mtproxy_port, secret, tls_domain)
    await ssh.write_file(
        server.ip, server.ssh_port, server.ssh_user, ssh_key.private_key_path,
        "/etc/telemt/config.toml", config_content,
        known_host_key=server.host_key,
    )
    await ssh.run_command(
        server.ip, server.ssh_port, server.ssh_user, ssh_key.private_key_path,
        "systemctl restart telemt",
        timeout=30, known_host_key=server.host_key,
    )

    # Update DB
    link = generate_tg_link(server.ip, server.mtproxy_port, secret, tls_domain)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.id == server_id))
        srv = result.scalar_one()
        srv.mtproxy_tls_domain = tls_domain
        srv.mtproxy_link = link
        await db.commit()

    logger.info(f"[{server.name}] TLS domain reconfigured to {tls_domain}")


async def uninstall_mtproxy_relay(jumphost_id: str) -> None:
    """Remove TCP relay from a jumphost."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
        jumphost = result.scalar_one_or_none()
        if not jumphost:
            raise ValueError("Jumphost not found")
        if not jumphost.mtproxy_enabled or not jumphost.mtproxy_relay_server_id:
            raise ValueError("No MTProxy relay is active on this jumphost")

        ssh_result = await db.execute(select(SSHKey).where(SSHKey.id == jumphost.ssh_key_id))
        ssh_key = ssh_result.scalar_one_or_none()

    await _set_jumphost_progress(jumphost_id, "Removing MTProxy relay…")

    try:
        await ssh.run_command(
            jumphost.ip, jumphost.ssh_port, jumphost.ssh_user, ssh_key.private_key_path,
            "systemctl stop telemt-relay 2>/dev/null; "
            "systemctl disable telemt-relay 2>/dev/null; "
            "rm -f /etc/systemd/system/telemt-relay.service && "
            "systemctl daemon-reload",
            timeout=30, known_host_key=jumphost.host_key,
        )

        if jumphost.mtproxy_port:
            await ssh.run_command(
                jumphost.ip, jumphost.ssh_port, jumphost.ssh_user, ssh_key.private_key_path,
                f'if command -v ufw &>/dev/null && ufw status | grep -q "Status: active"; then '
                f"ufw delete allow {jumphost.mtproxy_port}/tcp > /dev/null 2>&1; fi",
                timeout=10, known_host_key=jumphost.host_key,
            )
    except Exception as e:
        logger.error(f"[{jumphost.name}] Relay removal failed: {e}")

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
        jh = result.scalar_one()
        jh.mtproxy_enabled = False
        jh.mtproxy_port = None
        jh.mtproxy_secret = None
        jh.mtproxy_tls_domain = None
        jh.mtproxy_link = None
        jh.mtproxy_relay_server_id = None
        jh.status_message = None
        await db.commit()

    logger.info(f"[{jumphost.name}] MTProxy relay removed")
