"""VPS hardening logic.

Applied after sing-box provisioning is verified online.
See SECURITY.md for full documentation.
"""
import asyncio
import logging
import random

from sqlalchemy import select

from app.models import Server, SSHKey
from app.services import ssh
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def _set_progress(server_id: str, message: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.id == server_id))
        srv = result.scalar_one_or_none()
        if srv:
            srv.status_message = message
            await db.commit()


async def harden_server(server_id: str) -> None:
    """Main entry point -- load server from DB and run hardening."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.id == server_id))
        server = result.scalar_one_or_none()
        if not server:
            logger.error(f"Server {server_id} not found")
            return

        if server.hardened:
            logger.info(f"[{server.name}] Already hardened, skipping")
            return

        if server.status not in ("online", "error"):
            logger.warning(f"[{server.name}] Status is {server.status}, skipping hardening")
            return

        ssh_result = await db.execute(
            select(SSHKey).where(SSHKey.id == server.ssh_key_id)
        )
        ssh_key = ssh_result.scalar_one_or_none()

    try:
        await _do_harden(server_id, server, ssh_key)
    except Exception as e:
        logger.exception(f"Hardening failed for server {server_id}: {e}")
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Server).where(Server.id == server_id))
            srv = result.scalar_one_or_none()
            if srv:
                srv.status_message = f"Hardening failed: {str(e)[:500]}"
                await db.commit()


async def _do_harden(server_id, server, ssh_key) -> None:
    host = server.ip
    port = server.ssh_port
    username = server.ssh_user
    key_path = ssh_key.private_key_path
    hk = server.host_key
    name = server.name

    new_ssh_port = random.randint(10000, 60000)

    logger.info(f"[{name}] Hardening step 1: Installing security packages")
    await _set_progress(server_id, "Hardening: installing packages…")
    await _install_security_packages(host, port, username, key_path, hk)

    logger.info(f"[{name}] Hardening step 2: Configuring automatic security updates")
    await _set_progress(server_id, "Hardening: auto-updates…")
    await _configure_auto_updates(host, port, username, key_path, hk)

    logger.info(f"[{name}] Hardening step 3: Applying kernel hardening")
    await _set_progress(server_id, "Hardening: kernel sysctl…")
    await _configure_sysctl(host, port, username, key_path, hk)

    logger.info(f"[{name}] Hardening step 4: Disabling unnecessary services")
    await _disable_unnecessary_services(host, port, username, key_path, hk)

    logger.info(f"[{name}] Hardening step 5: Hardening SSH auth (key-only, no password)")
    await _set_progress(server_id, "Hardening: SSH lockdown…")
    await _harden_ssh_auth(host, port, username, key_path, hk)

    # Attempt SSH port change — best-effort, cloud firewalls may block it
    logger.info(f"[{name}] Hardening step 6: Attempting SSH port change to {new_ssh_port}")
    await _set_progress(server_id, "Hardening: SSH port change…")
    active_ssh_port = await _try_ssh_port_change(
        name, host, port, username, key_path, hk, new_ssh_port,
    )

    if active_ssh_port != port:
        # Port change succeeded — persist to DB
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Server).where(Server.id == server_id))
            srv = result.scalar_one()
            srv.ssh_port = active_ssh_port
            await db.commit()

    logger.info(f"[{name}] Hardening step 7: Configuring UFW (SSH port: {active_ssh_port})")
    await _set_progress(server_id, "Hardening: firewall…")
    await _configure_ufw(
        host, active_ssh_port, username, key_path, hk,
        ssh_port=active_ssh_port,
        hysteria2_port=server.hysteria2_port,
        reality_port=server.reality_port,
    )

    logger.info(f"[{name}] Hardening step 8: Configuring fail2ban")
    await _set_progress(server_id, "Hardening: fail2ban…")
    await _configure_fail2ban(host, active_ssh_port, username, key_path, hk)

    # Mark as hardened
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.id == server_id))
        srv = result.scalar_one()
        srv.hardened = True
        srv.status_message = None
        await db.commit()

    logger.info(f"[{name}] Hardening complete (SSH port: {active_ssh_port})")


async def _install_security_packages(host, port, username, key_path, hk) -> None:
    stdout, stderr, code = await ssh.run_command(
        host, port, username, key_path,
        "export DEBIAN_FRONTEND=noninteractive && "
        "apt-get update -qq && "
        "apt-get install -y --no-install-recommends fail2ban unattended-upgrades",
        timeout=120, known_host_key=hk,
    )
    if code != 0:
        raise RuntimeError(f"Failed to install security packages: {stderr[:300]}")


async def _configure_auto_updates(host, port, username, key_path, hk) -> None:
    auto_upgrades = (
        'APT::Periodic::Update-Package-Lists "1";\n'
        'APT::Periodic::Unattended-Upgrade "1";\n'
        'APT::Periodic::AutocleanInterval "7";\n'
    )
    await ssh.write_file(
        host, port, username, key_path,
        "/etc/apt/apt.conf.d/20auto-upgrades", auto_upgrades,
        known_host_key=hk,
    )

    unattended_conf = (
        'Unattended-Upgrade::Allowed-Origins {\n'
        '    "${distro_id}:${distro_codename}-security";\n'
        '};\n'
        'Unattended-Upgrade::AutoFixInterruptedDpkg "true";\n'
        'Unattended-Upgrade::MinimalSteps "true";\n'
        'Unattended-Upgrade::Remove-Unused-Dependencies "true";\n'
        'Unattended-Upgrade::Automatic-Reboot "false";\n'
    )
    await ssh.write_file(
        host, port, username, key_path,
        "/etc/apt/apt.conf.d/50unattended-upgrades", unattended_conf,
        known_host_key=hk,
    )


async def _configure_sysctl(host, port, username, key_path, hk) -> None:
    sysctl_conf = (
        "# Z Panel VPS hardening\n"
        "\n"
        "# IP Spoofing protection\n"
        "net.ipv4.conf.all.rp_filter = 1\n"
        "net.ipv4.conf.default.rp_filter = 1\n"
        "\n"
        "# Ignore ICMP redirects\n"
        "net.ipv4.conf.all.accept_redirects = 0\n"
        "net.ipv6.conf.all.accept_redirects = 0\n"
        "net.ipv4.conf.all.send_redirects = 0\n"
        "\n"
        "# Ignore ICMP broadcast requests\n"
        "net.ipv4.icmp_echo_ignore_broadcasts = 1\n"
        "\n"
        "# SYN flood protection\n"
        "net.ipv4.tcp_syncookies = 1\n"
        "net.ipv4.tcp_max_syn_backlog = 2048\n"
        "net.ipv4.tcp_synack_retries = 2\n"
        "\n"
        "# Disable source routing\n"
        "net.ipv4.conf.all.accept_source_route = 0\n"
        "net.ipv6.conf.all.accept_source_route = 0\n"
        "\n"
        "# Log martian packets\n"
        "net.ipv4.conf.all.log_martians = 1\n"
    )
    await ssh.write_file(
        host, port, username, key_path,
        "/etc/sysctl.d/99-zpanel-hardening.conf", sysctl_conf,
        known_host_key=hk,
    )
    await ssh.run_command(
        host, port, username, key_path,
        "sysctl --system > /dev/null 2>&1",
        timeout=10, known_host_key=hk,
    )


async def _disable_unnecessary_services(host, port, username, key_path, hk) -> None:
    await ssh.run_command(
        host, port, username, key_path,
        "systemctl disable --now snapd.service 2>/dev/null; "
        "systemctl disable --now snapd.socket 2>/dev/null; "
        "systemctl disable --now apache2 2>/dev/null; "
        "systemctl disable --now cups 2>/dev/null; "
        "systemctl disable --now avahi-daemon 2>/dev/null; "
        "true",
        timeout=30, known_host_key=hk,
    )


async def _harden_ssh_auth(host, port, username, key_path, hk) -> None:
    """Disable password auth, enforce pubkey-only. Does NOT change the port."""
    ssh_script = (
        "sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config && "
        "sed -i 's/^#*ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' /etc/ssh/sshd_config && "
        "sed -i 's/^#*KbdInteractiveAuthentication.*/KbdInteractiveAuthentication no/' /etc/ssh/sshd_config && "
        "sed -i 's/^#*PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config && "
        "sed -i 's/^#*PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config && "
        "sshd -t && systemctl restart sshd"
    )
    stdout, stderr, code = await ssh.run_command(
        host, port, username, key_path,
        ssh_script,
        timeout=15, known_host_key=hk,
    )
    if code != 0:
        raise RuntimeError(f"sshd config validation failed: {stderr[:300]}")


async def _try_ssh_port_change(name, host, port, username, key_path, hk, new_ssh_port) -> int:
    """Attempt to change the SSH port. Returns the active port (new or original).

    Best-effort: if the VPS provider's cloud firewall blocks the new port,
    we revert gracefully and return the original port.
    """
    # Update sshd_config with the new port
    port_script = (
        f"sed -i 's/^#*Port .*/Port {new_ssh_port}/' /etc/ssh/sshd_config && "
        f"grep -q '^Port ' /etc/ssh/sshd_config || echo 'Port {new_ssh_port}' >> /etc/ssh/sshd_config && "
        "sshd -t"
    )
    stdout, stderr, code = await ssh.run_command(
        host, port, username, key_path,
        port_script, timeout=15, known_host_key=hk,
    )
    if code != 0:
        logger.warning(f"[{name}] sshd -t failed for port {new_ssh_port}, skipping port change: {stderr[:200]}")
        return port

    # Temporarily open the new port in UFW before restarting sshd
    await ssh.run_command(
        host, port, username, key_path,
        f"ufw allow {new_ssh_port}/tcp > /dev/null 2>&1; true",
        timeout=10, known_host_key=hk,
    )

    # Restart sshd, then verify it bound to the new port locally
    stdout, stderr, code = await ssh.run_command(
        host, port, username, key_path,
        f"systemctl restart sshd && sleep 2 && ss -tlnp | grep ':{new_ssh_port} '",
        timeout=20, known_host_key=hk,
    )

    if not stdout.strip():
        # sshd didn't bind — revert
        logger.warning(f"[{name}] sshd did not bind to port {new_ssh_port} locally, reverting")
        await ssh.run_command(
            host, port, username, key_path,
            f"sed -i 's/^Port {new_ssh_port}/Port {port}/' /etc/ssh/sshd_config && systemctl restart sshd",
            timeout=15, known_host_key=hk,
        )
        return port

    # sshd is listening locally — now test remote connectivity
    await asyncio.sleep(2)

    if await _verify_new_port(host, new_ssh_port, username, key_path, hk):
        logger.info(f"[{name}] SSH port change to {new_ssh_port} confirmed")
        return new_ssh_port

    # Listening locally but blocked remotely — cloud firewall
    logger.warning(
        f"[{name}] Port {new_ssh_port} listening locally but blocked remotely "
        f"(VPS provider firewall?). Reverting to port {port}."
    )
    await ssh.run_command(
        host, port, username, key_path,
        f"sed -i 's/^Port {new_ssh_port}/Port {port}/' /etc/ssh/sshd_config && "
        f"systemctl restart sshd && "
        f"ufw delete allow {new_ssh_port}/tcp > /dev/null 2>&1; true",
        timeout=15, known_host_key=hk,
    )
    return port


async def _configure_ufw(host, port, username, key_path, hk,
                          ssh_port: int, hysteria2_port: int, reality_port: int) -> None:
    ufw_script = (
        "ufw --force reset > /dev/null 2>&1 && "
        "ufw default deny incoming > /dev/null 2>&1 && "
        "ufw default allow outgoing > /dev/null 2>&1 && "
        f"ufw allow {ssh_port}/tcp comment 'SSH' > /dev/null 2>&1 && "
        f"ufw allow {hysteria2_port}/udp comment 'Hysteria2' > /dev/null 2>&1 && "
        f"ufw allow {reality_port}/tcp comment 'VLESS-Reality' > /dev/null 2>&1 && "
        "ufw --force enable > /dev/null 2>&1"
    )
    stdout, stderr, code = await ssh.run_command(
        host, port, username, key_path,
        ufw_script,
        timeout=30, known_host_key=hk,
    )
    if code != 0:
        raise RuntimeError(f"UFW configuration failed: {stderr[:300]}")


async def _configure_fail2ban(host, port, username, key_path, hk) -> None:
    jail_conf = (
        "[DEFAULT]\n"
        "bantime = 3600\n"
        "findtime = 600\n"
        "maxretry = 5\n"
        "backend = systemd\n"
        "\n"
        "[sshd]\n"
        "enabled = true\n"
        f"port = {port}\n"
        "filter = sshd\n"
        "maxretry = 3\n"
        "bantime = 3600\n"
    )
    await ssh.write_file(
        host, port, username, key_path,
        "/etc/fail2ban/jail.local", jail_conf,
        known_host_key=hk,
    )
    await ssh.run_command(
        host, port, username, key_path,
        "systemctl enable fail2ban && systemctl restart fail2ban",
        timeout=15, known_host_key=hk,
    )


async def _verify_new_port(host, new_port, username, key_path, hk) -> bool:
    """Test SSH connectivity on the new port."""
    try:
        conn, _ = await ssh.connect_and_pin(host, new_port, username, key_path, known_host_key=hk)
        async with conn:
            result = await asyncio.wait_for(conn.run("echo ok"), timeout=10)
            return "ok" in (result.stdout or "")
    except Exception as e:
        logger.error(f"SSH verification on port {new_port} failed: {e}")
        return False
