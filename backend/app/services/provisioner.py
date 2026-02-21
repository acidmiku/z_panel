"""Server provisioning logic."""
import asyncio
import logging
import secrets

from sqlalchemy import select

from app.models import Server, User, CloudflareConfig, SSHKey
from app.services import ssh
from app.services.cloudflare import create_dns_record
from app.services.singbox_config import generate_singbox_config, config_to_json
from app.services.crypto import decrypt, encrypt
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def _set_progress(server_id: str, message: str) -> None:
    """Update status_message to reflect current provisioning step."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.id == server_id))
        srv = result.scalar_one_or_none()
        if srv:
            srv.status_message = message
            await db.commit()


def _generate_subdomain(prefix: str = "") -> str:
    if prefix:
        return prefix + "-" + secrets.token_hex(4)
    # Generate a neutral-looking subdomain (no vpn/proxy/node hints)
    return "s" + secrets.token_hex(5)


async def provision_server(server_id: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.id == server_id))
        server = result.scalar_one_or_none()
        if not server:
            logger.error(f"Server {server_id} not found")
            return

        cf_result = await db.execute(
            select(CloudflareConfig).where(CloudflareConfig.id == server.cf_config_id)
        )
        cf_config = cf_result.scalar_one_or_none()

        ssh_result = await db.execute(
            select(SSHKey).where(SSHKey.id == server.ssh_key_id)
        )
        ssh_key = ssh_result.scalar_one_or_none()

        users_result = await db.execute(select(User))
        users = list(users_result.scalars().all())

    try:
        await _do_provision(server, cf_config, ssh_key, users)
    except Exception as e:
        logger.exception(f"Provisioning failed for server {server_id}: {e}")
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Server).where(Server.id == server_id))
            srv = result.scalar_one_or_none()
            if srv:
                srv.status = "error"
                srv.status_message = str(e)[:1000]
                await db.commit()


async def _do_provision(server, cf_config, ssh_key, users):
    host = server.ip
    port = server.ssh_port
    username = server.ssh_user
    key_path = ssh_key.private_key_path

    sid = str(server.id)

    logger.info(f"[{server.name}] Step 1: Testing SSH connectivity + pinning host key")
    await _set_progress(sid, "Connecting via SSH…")
    # TOFU: first connection captures the host key
    conn, host_key = await ssh.connect_and_pin(host, port, username, key_path)
    try:
        result = await asyncio.wait_for(conn.run("echo ok"), timeout=10)
        if "ok" not in (result.stdout or ""):
            raise ConnectionError("Cannot reach server via SSH")
    finally:
        conn.close()

    # Store the pinned host key
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.id == server.id))
        srv = result.scalar_one()
        srv.host_key = host_key
        await db.commit()
    hk = host_key  # use for all subsequent calls

    logger.info(f"[{server.name}] Step 2: Cleaning up old install + deploying sing-box + grpcurl")
    await _set_progress(sid, "Installing sing-box…")
    cleanup_script = (
        "systemctl stop sing-box 2>/dev/null || true && "
        "systemctl disable sing-box 2>/dev/null || true && "
        "rm -f /etc/sing-box/config.json && "
        "rm -rf /etc/systemd/system/sing-box.service.d"
    )
    await ssh.run_command(host, port, username, key_path, cleanup_script, timeout=30, known_host_key=hk)

    # Deploy pre-built sing-box binary (built with v2ray_api tag in Docker image)
    import os
    singbox_binary = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "sing-box-binary")
    if os.path.isfile(singbox_binary):
        logger.info(f"[{server.name}] Deploying pre-built sing-box binary")
        await ssh.upload_file(host, port, username, key_path, singbox_binary, "/usr/bin/sing-box", known_host_key=hk)
        await ssh.run_command(host, port, username, key_path, "chmod +x /usr/bin/sing-box", timeout=10, known_host_key=hk)
    else:
        # Fallback: install from apt (without v2ray_api support)
        logger.warning(f"[{server.name}] Pre-built sing-box binary not found, falling back to apt install")
        install_script = (
            "set -e && "
            "mkdir -p /etc/apt/keyrings && "
            "curl -fsSL https://sing-box.app/gpg.key -o /etc/apt/keyrings/sagernet.asc && "
            'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/sagernet.asc] '
            'https://deb.sagernet.org/ * *" > /etc/apt/sources.list.d/sagernet.list && '
            "apt-get update -qq && "
            "apt-get install -y sing-box"
        )
        stdout, stderr, code = await ssh.run_command(host, port, username, key_path, install_script, timeout=300, known_host_key=hk)
        if code != 0:
            raise RuntimeError(f"sing-box installation failed: {stderr[:500]}")

    # Ensure systemd service file exists (needed when deploying binary directly)
    await ssh.run_command(host, port, username, key_path,
        "test -f /etc/systemd/system/sing-box.service || "
        "cat > /etc/systemd/system/sing-box.service << 'SVCEOF'\n"
        "[Unit]\nDescription=sing-box service\nAfter=network.target\n\n"
        "[Service]\nType=simple\nExecStart=/usr/bin/sing-box run -c /etc/sing-box/config.json\n"
        "Restart=on-failure\nRestartSec=10\n\n[Install]\nWantedBy=multi-user.target\nSVCEOF",
        timeout=10, known_host_key=hk,
    )
    await ssh.run_command(host, port, username, key_path, "systemctl daemon-reload", timeout=10, known_host_key=hk)

    # Install grpcurl for v2ray stats API queries
    grpcurl_script = (
        "if ! command -v grpcurl &>/dev/null; then "
        "curl -sSL https://github.com/fullstorydev/grpcurl/releases/download/v1.9.1/grpcurl_1.9.1_linux_x86_64.tar.gz "
        "| tar xz -C /usr/local/bin grpcurl && chmod +x /usr/local/bin/grpcurl; fi"
    )
    await ssh.run_command(host, port, username, key_path, grpcurl_script, timeout=60, known_host_key=hk)

    logger.info(f"[{server.name}] Step 3: Getting version + generating Reality keypair")
    await _set_progress(sid, "Generating Reality keypair…")
    stdout_ver, _, _ = await ssh.run_command(host, port, username, key_path, "sing-box version 2>/dev/null | head -1 || echo unknown", known_host_key=hk)
    sing_box_version = stdout_ver.strip()

    stdout, stderr, code = await ssh.run_command(host, port, username, key_path, "sing-box generate reality-keypair", known_host_key=hk)
    if code != 0:
        raise RuntimeError(f"Reality keypair generation failed: {stderr}")

    private_key = public_key = None
    for line in stdout.strip().splitlines():
        if "PrivateKey" in line:
            private_key = line.split(":", 1)[1].strip()
        elif "PublicKey" in line:
            public_key = line.split(":", 1)[1].strip()

    if not private_key or not public_key:
        raise RuntimeError(f"Could not parse Reality keypair: {stdout}")

    short_id = secrets.token_hex(8)

    logger.info(f"[{server.name}] Step 4: Creating Cloudflare DNS record")
    await _set_progress(sid, "Creating DNS record…")
    subdomain = _generate_subdomain(server.subdomain_prefix or "")
    fqdn = f"{subdomain}.{cf_config.base_domain}"
    cf_token = decrypt(cf_config.api_token)

    dns_record_id = await create_dns_record(
        api_token=cf_token, zone_id=cf_config.zone_id, name=fqdn, ip=server.ip,
    )

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.id == server.id))
        srv = result.scalar_one()
        srv.reality_private_key = encrypt(private_key)
        srv.reality_public_key = public_key
        srv.reality_short_id = short_id
        srv.subdomain = subdomain
        srv.fqdn = fqdn
        srv.cf_dns_record_id = dns_record_id
        srv.sing_box_version = sing_box_version
        await db.commit()
        await db.refresh(srv)
        server = srv

    logger.info(f"[{server.name}] Step 5: Pushing sing-box config")
    await _set_progress(sid, "Pushing config…")
    config_dict = generate_singbox_config(server, users, cf_token)
    config_json = config_to_json(config_dict)

    await ssh.run_command(host, port, username, key_path, "mkdir -p /etc/sing-box", known_host_key=hk)
    await ssh.write_file(host, port, username, key_path, "/etc/sing-box/config.json", config_json, known_host_key=hk)

    # systemd override - provide CF token via both env var names for compatibility
    override_content = f'[Service]\nEnvironment="CF_API_TOKEN={cf_token}"\nEnvironment="CF_DNS_API_TOKEN={cf_token}"\n'
    await ssh.run_command(host, port, username, key_path, "mkdir -p /etc/systemd/system/sing-box.service.d", known_host_key=hk)
    await ssh.write_file(host, port, username, key_path, "/etc/systemd/system/sing-box.service.d/override.conf", override_content, known_host_key=hk)
    await ssh.run_command(host, port, username, key_path, "systemctl daemon-reload", known_host_key=hk)

    logger.info(f"[{server.name}] Step 6: Configuring firewall")
    ufw_script = (
        f'if command -v ufw &>/dev/null && ufw status | grep -q "Status: active"; then '
        f"ufw allow {server.hysteria2_port}/udp && ufw allow {server.reality_port}/tcp; fi"
    )
    await ssh.run_command(host, port, username, key_path, ufw_script, known_host_key=hk)

    logger.info(f"[{server.name}] Step 7: Starting sing-box")
    await _set_progress(sid, "Starting sing-box…")
    await ssh.run_command(host, port, username, key_path, "systemctl enable sing-box && systemctl restart sing-box", timeout=30, known_host_key=hk)

    logger.info(f"[{server.name}] Step 8: Verifying")
    await _set_progress(sid, "Verifying sing-box…")
    # Poll a few times — sing-box may need time for ACME cert acquisition
    is_active = False
    for attempt in range(4):
        await asyncio.sleep(5)
        stdout, _, _ = await ssh.run_command(host, port, username, key_path, "systemctl is-active sing-box", known_host_key=hk)
        if stdout.strip() == "active":
            is_active = True
            break
        logger.info(f"[{server.name}] sing-box not active yet (attempt {attempt + 1}/4): {stdout.strip()}")

    # If not active, grab journal logs for diagnosis
    error_detail = None
    if not is_active:
        log_stdout, _, _ = await ssh.run_command(
            host, port, username, key_path,
            "journalctl -u sing-box --no-pager -n 40 --output=cat 2>/dev/null"
            " | grep -i -E 'fatal|error|fail'"
            " | grep -v 'did not closed properly'"
            " | tail -5",
            timeout=15, known_host_key=hk,
        )
        error_detail = log_stdout.strip() if log_stdout.strip() else "sing-box not active after start (no error in journal)"

    if not is_active:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Server).where(Server.id == server.id))
            srv = result.scalar_one()
            srv.status = "error"
            srv.status_message = error_detail
            await db.commit()
        logger.info(f"[{server.name}] Provisioning failed")
        return

    # sing-box is running — harden before going online
    logger.info(f"[{server.name}] sing-box verified, starting hardening")
    try:
        await _set_progress(sid, "Hardening VPS…")
        from app.services.hardener import harden_server
        await harden_server(str(server.id))
    except Exception as e:
        logger.error(f"[{server.name}] Hardening failed (sing-box still running): {e}")

    # Provisioning (+ hardening) complete — mark as online
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.id == server.id))
        srv = result.scalar_one()
        srv.status = "online"
        if not srv.status_message or srv.status_message.startswith("Hardening"):
            srv.status_message = None
        await db.commit()

    logger.info(f"[{server.name}] Provisioning complete")
