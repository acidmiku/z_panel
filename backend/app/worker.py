"""arq worker settings and task definitions."""
import logging
from arq.connections import RedisSettings
from arq.cron import cron

from app.config import settings
from app.services.provisioner import provision_server
from app.services.config_pusher import push_config_to_server
from app.services.jumphost_provisioner import provision_jumphost
from app.services.jumphost_config_pusher import push_config_to_jumphost
from app.services.health import run_health_checks
from app.services.telemt_installer import (
    install_mtproxy_on_server, uninstall_mtproxy_from_server,
    install_mtproxy_on_jumphost, uninstall_mtproxy_from_jumphost,
    install_mtproxy_relay, uninstall_mtproxy_relay,
)
logger = logging.getLogger(__name__)


async def task_provision_server(ctx, server_id: str):
    logger.info(f"Starting provisioning task for server {server_id}")
    await provision_server(server_id)


async def task_push_config(ctx, server_id: str):
    logger.info(f"Starting config push task for server {server_id}")
    await push_config_to_server(server_id)


async def task_provision_jumphost(ctx, jumphost_id: str):
    logger.info(f"Starting provisioning task for jumphost {jumphost_id}")
    await provision_jumphost(jumphost_id)


async def task_push_jumphost_config(ctx, jumphost_id: str):
    logger.info(f"Starting config push task for jumphost {jumphost_id}")
    await push_config_to_jumphost(jumphost_id)


async def task_install_mtproxy_server(ctx, server_id: str, port: int = 443, tls_domain: str = "www.google.com"):
    logger.info(f"Starting MTProxy install for server {server_id}")
    await install_mtproxy_on_server(server_id, port, tls_domain)


async def task_uninstall_mtproxy_server(ctx, server_id: str):
    logger.info(f"Starting MTProxy uninstall for server {server_id}")
    await uninstall_mtproxy_from_server(server_id)


async def task_install_mtproxy_jumphost(ctx, jumphost_id: str, port: int = 443, tls_domain: str = "www.google.com"):
    logger.info(f"Starting MTProxy install for jumphost {jumphost_id}")
    await install_mtproxy_on_jumphost(jumphost_id, port, tls_domain)


async def task_uninstall_mtproxy_jumphost(ctx, jumphost_id: str):
    logger.info(f"Starting MTProxy uninstall for jumphost {jumphost_id}")
    await uninstall_mtproxy_from_jumphost(jumphost_id)


async def task_install_mtproxy_relay(ctx, jumphost_id: str, server_id: str, port: int = 443, tls_domain: str = "www.google.com"):
    logger.info(f"Setting up MTProxy relay on jumphost {jumphost_id} → server {server_id}")
    await install_mtproxy_relay(jumphost_id, server_id, port, tls_domain)


async def task_uninstall_mtproxy_relay(ctx, jumphost_id: str):
    logger.info(f"Removing MTProxy relay from jumphost {jumphost_id}")
    await uninstall_mtproxy_relay(jumphost_id)


async def task_health_checks(ctx):
    logger.info("Running scheduled health checks")
    await run_health_checks()


def _parse_redis_url(url: str) -> RedisSettings:
    from urllib.parse import urlparse, unquote
    parsed = urlparse(url)
    # Support both redis://:password@host and redis://password@host (common mistake)
    password = unquote(parsed.password) if parsed.password else (unquote(parsed.username) if parsed.username else None)
    return RedisSettings(
        host=parsed.hostname or "redis",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or "0"),
        password=password,
    )


class WorkerSettings:
    functions = [
        task_provision_server, task_push_config,
        task_provision_jumphost, task_push_jumphost_config,
        task_install_mtproxy_server, task_uninstall_mtproxy_server,
        task_install_mtproxy_jumphost, task_uninstall_mtproxy_jumphost,
        task_install_mtproxy_relay, task_uninstall_mtproxy_relay,
        task_health_checks,
    ]
    cron_jobs = [
        cron(task_health_checks, second={0}, timeout=120),
    ]
    redis_settings = _parse_redis_url(settings.REDIS_URL)
    max_jobs = 10
    job_timeout = 600
