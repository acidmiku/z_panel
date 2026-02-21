"""Push updated sing-box config to servers."""
import logging

from sqlalchemy import select

from app.models import Server, User, CloudflareConfig, SSHKey
from app.services import ssh
from app.services.singbox_config import generate_singbox_config, config_to_json
from app.services.crypto import decrypt
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def push_config_to_server(server_id: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.id == server_id))
        server = result.scalar_one_or_none()
        if not server or server.status not in ("online", "error"):
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
        cf_token = decrypt(cf_config.api_token)
        config_dict = generate_singbox_config(server, users, cf_token)
        config_json = config_to_json(config_dict)

        host = server.ip
        port = server.ssh_port
        username = server.ssh_user
        key_path = ssh_key.private_key_path
        hk = server.host_key

        # Deploy pre-built sing-box binary if available (includes v2ray_api)
        import os
        singbox_binary = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "sing-box-binary")
        if os.path.isfile(singbox_binary):
            # Check if server has v2ray_api support; if not, upgrade
            check_stdout, _, _ = await ssh.run_command(
                host, port, username, key_path,
                "sing-box version 2>&1 | grep -q with_v2ray_api && echo yes || echo no",
                timeout=10, known_host_key=hk,
            )
            if check_stdout.strip() != "yes":
                logger.info(f"Upgrading sing-box on {server.name} to include v2ray_api")
                await ssh.run_command(host, port, username, key_path, "systemctl stop sing-box", timeout=10, known_host_key=hk)
                await ssh.upload_file(host, port, username, key_path, singbox_binary, "/usr/bin/sing-box", known_host_key=hk)
                await ssh.run_command(host, port, username, key_path, "chmod +x /usr/bin/sing-box", timeout=10, known_host_key=hk)

        # Ensure grpcurl is installed for v2ray stats API
        await ssh.run_command(
            host, port, username, key_path,
            "if ! command -v grpcurl &>/dev/null; then "
            "curl -sSL https://github.com/fullstorydev/grpcurl/releases/download/v1.9.1/grpcurl_1.9.1_linux_x86_64.tar.gz "
            "| tar xz -C /usr/local/bin grpcurl && chmod +x /usr/local/bin/grpcurl; fi",
            timeout=60, known_host_key=hk,
        )

        await ssh.write_file(host, port, username, key_path, "/etc/sing-box/config.json", config_json, known_host_key=hk)
        stdout, stderr, code = await ssh.run_command(
            host, port, username, key_path,
            "systemctl restart sing-box && sleep 2 && systemctl is-active sing-box",
            known_host_key=hk,
        )
        is_active = stdout.strip().splitlines()[-1].strip() == "active" if stdout.strip() else False

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Server).where(Server.id == server_id))
            srv = result.scalar_one()
            srv.status = "online" if is_active else "error"
            srv.status_message = None if is_active else f"sing-box not active after config push: {stderr[:300]}"
            await db.commit()

        logger.info(f"Config pushed to {server.name}: {'ok' if is_active else 'failed'}")
    except Exception as e:
        logger.exception(f"Config push failed for server {server_id}: {e}")
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Server).where(Server.id == server_id))
            srv = result.scalar_one_or_none()
            if srv:
                srv.status = "error"
                srv.status_message = f"Config push error: {str(e)[:500]}"
                await db.commit()
