"""arq worker settings and task definitions."""
import logging
from arq.connections import RedisSettings
from arq.cron import cron

from app.config import settings
from app.services.provisioner import provision_server
from app.services.config_pusher import push_config_to_server
from app.services.health import run_health_checks
logger = logging.getLogger(__name__)


async def task_provision_server(ctx, server_id: str):
    logger.info(f"Starting provisioning task for server {server_id}")
    await provision_server(server_id)


async def task_push_config(ctx, server_id: str):
    logger.info(f"Starting config push task for server {server_id}")
    await push_config_to_server(server_id)


async def task_health_checks(ctx):
    logger.info("Running scheduled health checks")
    await run_health_checks()


def _parse_redis_url(url: str) -> RedisSettings:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "redis",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or "0"),
        password=parsed.password,
    )


class WorkerSettings:
    functions = [task_provision_server, task_push_config, task_health_checks]
    cron_jobs = [
        cron(task_health_checks, second={0}, timeout=120),
    ]
    redis_settings = _parse_redis_url(settings.REDIS_URL)
    max_jobs = 10
    job_timeout = 600
