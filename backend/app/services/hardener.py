"""VPS hardening logic.

Applied after sing-box provisioning is verified online.
See SECURITY.md for full documentation.
"""
import asyncio
import logging
import random

from sqlalchemy import select

from app.models import Server, Jumphost, SSHKey
from app.services import ssh
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


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


async def _harden_common(
    target_id: str,
    name: str,
    host: str,
    port: int,
    username: str,
    key_path: str,
    hk: str,
    tcp_ports: list[int],
    udp_ports: list[int],
    set_progress,
    model_class,
    ss_port: int | None = None,
) -> int:
    """Shared hardening logic for servers and jumphosts.

    Returns the active SSH port after hardening.
    """
    new_ssh_port = random.randint(10000, 60000)

    logger.info(f"[{name}] Hardening step 1: Installing security packages")
    await set_progress(target_id, "Hardening: installing packages…")
    await _install_security_packages(host, port, username, key_path, hk)

    logger.info(f"[{name}] Hardening step 2: Configuring automatic security updates")
    await set_progress(target_id, "Hardening: auto-updates…")
    await _configure_auto_updates(host, port, username, key_path, hk)

    logger.info(f"[{name}] Hardening step 3: Applying kernel hardening")
    await set_progress(target_id, "Hardening: kernel sysctl…")
    await _configure_sysctl(host, port, username, key_path, hk)

    logger.info(f"[{name}] Hardening step 4: Disabling unnecessary services")
    await _disable_unnecessary_services(host, port, username, key_path, hk)

    logger.info(f"[{name}] Hardening step 5: Hardening SSH auth (key-only, no password)")
    await set_progress(target_id, "Hardening: SSH lockdown…")
    await _harden_ssh_auth(host, port, username, key_path, hk)

    # Attempt SSH port change
    logger.info(f"[{name}] Hardening step 6: Attempting SSH port change to {new_ssh_port}")
    await set_progress(target_id, "Hardening: SSH port change…")
    active_ssh_port = await _try_ssh_port_change(
        name, host, port, username, key_path, hk, new_ssh_port,
    )

    if active_ssh_port != port:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(model_class).where(model_class.id == target_id))
            obj = result.scalar_one()
            obj.ssh_port = active_ssh_port
            await db.commit()

    logger.info(f"[{name}] Hardening step 7: Configuring UFW (SSH port: {active_ssh_port})")
    await set_progress(target_id, "Hardening: firewall…")
    await _configure_ufw_generic(
        host, active_ssh_port, username, key_path, hk,
        ssh_port=active_ssh_port,
        tcp_ports=tcp_ports,
        udp_ports=udp_ports,
    )

    logger.info(f"[{name}] Hardening step 8: Configuring fail2ban")
    await set_progress(target_id, "Hardening: fail2ban…")
    await _configure_fail2ban(host, active_ssh_port, username, key_path, hk, ss_port=ss_port)

    # Mark as hardened
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(model_class).where(model_class.id == target_id))
        obj = result.scalar_one()
        obj.hardened = True
        obj.status_message = None
        await db.commit()

    logger.info(f"[{name}] Hardening complete (SSH port: {active_ssh_port})")
    return active_ssh_port


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

        if server.status not in ("online", "error", "provisioning"):
            logger.warning(f"[{server.name}] Status is {server.status}, skipping hardening")
            return

        ssh_result = await db.execute(
            select(SSHKey).where(SSHKey.id == server.ssh_key_id)
        )
        ssh_key = ssh_result.scalar_one_or_none()

    try:
        await _harden_common(
            target_id=server_id,
            name=server.name,
            host=server.ip,
            port=server.ssh_port,
            username=server.ssh_user,
            key_path=ssh_key.private_key_path,
            hk=server.host_key,
            tcp_ports=[server.reality_port],
            udp_ports=[server.hysteria2_port],
            set_progress=_set_server_progress,
            model_class=Server,
        )
    except Exception as e:
        logger.exception(f"Hardening failed for server {server_id}: {e}")
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Server).where(Server.id == server_id))
            srv = result.scalar_one_or_none()
            if srv:
                srv.status_message = f"Hardening failed: {str(e)[:500]}"
                await db.commit()


async def harden_jumphost(jumphost_id: str) -> None:
    """Harden a jumphost — same flow but opens SS port (TCP) instead of Hy2/Reality."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
        jumphost = result.scalar_one_or_none()
        if not jumphost:
            logger.error(f"Jumphost {jumphost_id} not found")
            return

        if jumphost.hardened:
            logger.info(f"[{jumphost.name}] Already hardened, skipping")
            return

        if jumphost.status not in ("online", "error", "provisioning"):
            logger.warning(f"[{jumphost.name}] Status is {jumphost.status}, skipping hardening")
            return

        ssh_result = await db.execute(
            select(SSHKey).where(SSHKey.id == jumphost.ssh_key_id)
        )
        ssh_key = ssh_result.scalar_one_or_none()

    try:
        await _harden_common(
            target_id=jumphost_id,
            name=jumphost.name,
            host=jumphost.ip,
            port=jumphost.ssh_port,
            username=jumphost.ssh_user,
            key_path=ssh_key.private_key_path,
            hk=jumphost.host_key,
            tcp_ports=[jumphost.shadowsocks_port],
            udp_ports=[jumphost.shadowsocks_port],
            set_progress=_set_jumphost_progress,
            model_class=Jumphost,
            ss_port=jumphost.shadowsocks_port,
        )
    except Exception as e:
        logger.exception(f"Hardening failed for jumphost {jumphost_id}: {e}")
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
            jh = result.scalar_one_or_none()
            if jh:
                jh.status_message = f"Hardening failed: {str(e)[:500]}"
                await db.commit()


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


async def _configure_ufw_generic(host, port, username, key_path, hk,
                                  ssh_port: int,
                                  tcp_ports: list[int] | None = None,
                                  udp_ports: list[int] | None = None) -> None:
    """Configure UFW with the given SSH port and arbitrary TCP/UDP ports."""
    parts = [
        "ufw --force reset > /dev/null 2>&1",
        "ufw default deny incoming > /dev/null 2>&1",
        "ufw default allow outgoing > /dev/null 2>&1",
        f"ufw allow {ssh_port}/tcp comment 'SSH' > /dev/null 2>&1",
    ]
    for p in (tcp_ports or []):
        parts.append(f"ufw allow {p}/tcp > /dev/null 2>&1")
    for p in (udp_ports or []):
        parts.append(f"ufw allow {p}/udp > /dev/null 2>&1")
    parts.append("ufw --force enable > /dev/null 2>&1")

    ufw_script = " && ".join(parts)
    stdout, stderr, code = await ssh.run_command(
        host, port, username, key_path,
        ufw_script,
        timeout=30, known_host_key=hk,
    )
    if code != 0:
        raise RuntimeError(f"UFW configuration failed: {stderr[:300]}")


async def _configure_ufw(host, port, username, key_path, hk,
                          ssh_port: int, hysteria2_port: int, reality_port: int) -> None:
    """Legacy wrapper for server hardening."""
    await _configure_ufw_generic(
        host, port, username, key_path, hk,
        ssh_port=ssh_port,
        tcp_ports=[reality_port],
        udp_ports=[hysteria2_port],
    )


async def _configure_fail2ban(host, port, username, key_path, hk, ss_port: int | None = None) -> None:
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

    if ss_port:
        ss_filter = (
            "[Definition]\n"
            "failregex = ^.*inbound/shadowsocks.*authentication failed from <HOST>:\\d+.*$\n"
            "            ^.*inbound/shadowsocks.*process connection from <HOST>:\\d+.*authentication failed.*$\n"
            "ignoreregex =\n"
        )
        await ssh.write_file(
            host, port, username, key_path,
            "/etc/fail2ban/filter.d/sing-box-ss.conf", ss_filter,
            known_host_key=hk,
        )

        ss_jail = (
            "[sing-box-ss]\n"
            "enabled = true\n"
            f"port = {ss_port}\n"
            "filter = sing-box-ss\n"
            "backend = systemd\n"
            "journalmatch = _SYSTEMD_UNIT=sing-box.service\n"
            "maxretry = 5\n"
            "findtime = 600\n"
            "bantime = 3600\n"
        )
        await ssh.write_file(
            host, port, username, key_path,
            "/etc/fail2ban/jail.d/sing-box-ss.conf", ss_jail,
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
