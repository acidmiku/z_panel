"""Jumphost provisioning logic."""
import asyncio
import base64
import logging
import random
import secrets

from sqlalchemy import select

from app.models import Jumphost, User, SSHKey
from app.services import ssh
from app.services.jumphost_singbox_config import generate_jumphost_singbox_config, config_to_json
from app.services.crypto import encrypt
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def _set_progress(jumphost_id: str, message: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
        jh = result.scalar_one_or_none()
        if jh:
            jh.status_message = message
            await db.commit()


async def provision_jumphost(jumphost_id: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
        jumphost = result.scalar_one_or_none()
        if not jumphost:
            logger.error(f"Jumphost {jumphost_id} not found")
            return

        ssh_result = await db.execute(
            select(SSHKey).where(SSHKey.id == jumphost.ssh_key_id)
        )
        ssh_key = ssh_result.scalar_one_or_none()

        users_result = await db.execute(select(User))
        users = list(users_result.scalars().all())

    try:
        await _do_provision(jumphost, ssh_key, users)
    except Exception as e:
        logger.exception(f"Jumphost provisioning failed for {jumphost_id}: {e}")
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
            jh = result.scalar_one_or_none()
            if jh:
                jh.status = "error"
                jh.status_message = str(e)[:1000]
                await db.commit()


async def _do_provision(jumphost, ssh_key, users):
    host = jumphost.ip
    port = jumphost.ssh_port
    username = jumphost.ssh_user
    key_path = ssh_key.private_key_path

    jid = str(jumphost.id)

    # Step 1: SSH connectivity + host key pin
    logger.info(f"[{jumphost.name}] Step 1: Testing SSH connectivity + pinning host key")
    await _set_progress(jid, "Connecting via SSH…")
    conn, host_key = await ssh.connect_and_pin(host, port, username, key_path)
    try:
        result = await asyncio.wait_for(conn.run("echo ok"), timeout=10)
        if "ok" not in (result.stdout or ""):
            raise ConnectionError("Cannot reach jumphost via SSH")
    finally:
        conn.close()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost.id))
        jh = result.scalar_one()
        jh.host_key = host_key
        await db.commit()
    hk = host_key

    # Step 2: Install sing-box + grpcurl
    logger.info(f"[{jumphost.name}] Step 2: Installing sing-box + grpcurl")
    await _set_progress(jid, "Installing sing-box…")
    cleanup_script = (
        "systemctl stop sing-box 2>/dev/null || true && "
        "systemctl disable sing-box 2>/dev/null || true && "
        "rm -f /etc/sing-box/config.json && "
        "rm -rf /etc/systemd/system/sing-box.service.d"
    )
    await ssh.run_command(host, port, username, key_path, cleanup_script, timeout=30, known_host_key=hk)

    import os
    singbox_binary = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "sing-box-binary")
    if os.path.isfile(singbox_binary):
        logger.info(f"[{jumphost.name}] Deploying pre-built sing-box binary")
        await ssh.upload_file(host, port, username, key_path, singbox_binary, "/usr/bin/sing-box", known_host_key=hk)
        await ssh.run_command(host, port, username, key_path, "chmod +x /usr/bin/sing-box", timeout=10, known_host_key=hk)
    else:
        logger.warning(f"[{jumphost.name}] Pre-built sing-box binary not found, falling back to apt install")
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

    # Ensure systemd service
    await ssh.run_command(host, port, username, key_path,
        "test -f /etc/systemd/system/sing-box.service || "
        "cat > /etc/systemd/system/sing-box.service << 'SVCEOF'\n"
        "[Unit]\nDescription=sing-box service\nAfter=network.target\n\n"
        "[Service]\nType=simple\nExecStart=/usr/bin/sing-box run -c /etc/sing-box/config.json\n"
        "Restart=on-failure\nRestartSec=10\n\n[Install]\nWantedBy=multi-user.target\nSVCEOF",
        timeout=10, known_host_key=hk,
    )
    await ssh.run_command(host, port, username, key_path, "systemctl daemon-reload", timeout=10, known_host_key=hk)

    # Install grpcurl
    grpcurl_script = (
        "if ! command -v grpcurl &>/dev/null; then "
        "curl -sSL https://github.com/fullstorydev/grpcurl/releases/download/v1.9.1/grpcurl_1.9.1_linux_x86_64.tar.gz "
        "| tar xz -C /usr/local/bin grpcurl && chmod +x /usr/local/bin/grpcurl; fi"
    )
    await ssh.run_command(host, port, username, key_path, grpcurl_script, timeout=60, known_host_key=hk)

    # Step 3: Generate SS server key + random port
    logger.info(f"[{jumphost.name}] Step 3: Generating SS credentials")
    await _set_progress(jid, "Generating Shadowsocks credentials…")
    stdout_ver, _, _ = await ssh.run_command(host, port, username, key_path, "sing-box version 2>/dev/null | head -1 || echo unknown", known_host_key=hk)
    sing_box_version = stdout_ver.strip()

    ss_server_key = base64.b64encode(secrets.token_bytes(16)).decode()
    ss_port = random.randint(10000, 60000)

    # Step 4: Generate SSH tunnel keypair on jumphost
    logger.info(f"[{jumphost.name}] Step 4: Generating SSH tunnel keypair")
    await _set_progress(jid, "Generating tunnel keypair…")
    keygen_script = (
        "(shred -vfz -n 3 /tmp/jh_tunnel_key /tmp/jh_tunnel_key.pub 2>/dev/null || rm -f /tmp/jh_tunnel_key /tmp/jh_tunnel_key.pub) && "
        "ssh-keygen -t ed25519 -f /tmp/jh_tunnel_key -N '' -q && "
        "mkdir -p ~/.ssh && "
        'cat /tmp/jh_tunnel_key.pub | while read key; do '
        'echo "command=\"/bin/false\",no-agent-forwarding,no-X11-forwarding,no-pty $key" >> ~/.ssh/authorized_keys; done && '
        "cat /tmp/jh_tunnel_key && echo '---PUBKEY---' && cat /tmp/jh_tunnel_key.pub && "
        "shred -vfz -n 3 /tmp/jh_tunnel_key /tmp/jh_tunnel_key.pub 2>/dev/null || rm -f /tmp/jh_tunnel_key /tmp/jh_tunnel_key.pub"
    )
    stdout, stderr, code = await ssh.run_command(host, port, username, key_path, keygen_script, timeout=15, known_host_key=hk, elevate=False)
    if code != 0:
        raise RuntimeError(f"SSH tunnel keypair generation failed: {stderr[:300]}")

    parts = stdout.split("---PUBKEY---")
    tunnel_private_key = parts[0].strip()

    # Store keys + config in DB
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost.id))
        jh = result.scalar_one()
        jh.shadowsocks_server_key = encrypt(ss_server_key)
        jh.shadowsocks_port = ss_port
        jh.tunnel_private_key = encrypt(tunnel_private_key)
        jh.sing_box_version = sing_box_version
        await db.commit()
        await db.refresh(jh)
        jumphost = jh

    # Step 5: Push sing-box config (no CF token, no systemd env override)
    logger.info(f"[{jumphost.name}] Step 5: Pushing sing-box config")
    await _set_progress(jid, "Pushing config…")
    config_dict = generate_jumphost_singbox_config(jumphost, users)
    config_json = config_to_json(config_dict)

    await ssh.run_command(host, port, username, key_path, "mkdir -p /etc/sing-box", known_host_key=hk)
    await ssh.write_file(host, port, username, key_path, "/etc/sing-box/config.json", config_json, known_host_key=hk)

    # Step 6: UFW — allow SS port (TCP) + SSH port (TCP)
    logger.info(f"[{jumphost.name}] Step 6: Configuring firewall")
    ufw_script = (
        f'if command -v ufw &>/dev/null && ufw status | grep -q "Status: active"; then '
        f"ufw allow {ss_port}/tcp && ufw allow {ss_port}/udp; fi"
    )
    await ssh.run_command(host, port, username, key_path, ufw_script, known_host_key=hk)

    # Step 7: Start sing-box
    logger.info(f"[{jumphost.name}] Step 7: Starting sing-box")
    await _set_progress(jid, "Starting sing-box…")
    await ssh.run_command(host, port, username, key_path, "systemctl enable sing-box && systemctl restart sing-box", timeout=30, known_host_key=hk)

    # Step 8: Verify
    logger.info(f"[{jumphost.name}] Step 8: Verifying")
    await _set_progress(jid, "Verifying sing-box…")
    is_active = False
    for attempt in range(4):
        await asyncio.sleep(5)
        stdout, _, _ = await ssh.run_command(host, port, username, key_path, "systemctl is-active sing-box", known_host_key=hk)
        if stdout.strip() == "active":
            is_active = True
            break
        logger.info(f"[{jumphost.name}] sing-box not active yet (attempt {attempt + 1}/4): {stdout.strip()}")

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
            result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost.id))
            jh = result.scalar_one()
            jh.status = "error"
            jh.status_message = error_detail
            await db.commit()
        logger.info(f"[{jumphost.name}] Provisioning failed")
        return

    # Step 9: Harden
    logger.info(f"[{jumphost.name}] sing-box verified, starting hardening")
    try:
        await _set_progress(jid, "Hardening VPS…")
        from app.services.hardener import harden_jumphost
        await harden_jumphost(str(jumphost.id))
    except Exception as e:
        logger.error(f"[{jumphost.name}] Hardening failed (sing-box still running): {e}")

    # Install MTProxy (telemt) if requested during creation
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost.id))
        jh = result.scalar_one()
        wants_mtproxy = jh.mtproxy_tls_domain and not jh.mtproxy_enabled

    if wants_mtproxy:
        try:
            await _set_progress(jid, "Installing MTProxy…")
            from app.services.telemt_installer import install_mtproxy_on_jumphost
            await install_mtproxy_on_jumphost(
                str(jumphost.id),
                mtproxy_port=jh.mtproxy_port or 443,
                tls_domain=jh.mtproxy_tls_domain,
            )
        except Exception as e:
            logger.error(f"[{jumphost.name}] MTProxy install failed (sing-box still running): {e}")

    # Mark as online
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost.id))
        jh = result.scalar_one()
        jh.status = "online"
        if not jh.status_message or jh.status_message.startswith(("Hardening", "MTProxy", "Installing")):
            jh.status_message = None
        await db.commit()

    logger.info(f"[{jumphost.name}] Provisioning complete")
