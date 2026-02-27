"""Health check logic for servers."""
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, delete

from app.models import Server, Jumphost, SSHKey, User, ServerTrafficSnapshot, ServerUserTraffic, JumphostTrafficSnapshot
from app.services import ssh
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def _collect_system_stats(host, port, username, key_path, known_host_key=None) -> dict:
    """Collect system stats via SSH."""
    stats = {}
    try:
        # Uptime + load + memory + disk in one SSH call, each on its own line
        stdout, _, _ = await ssh.run_command(
            host, port, username, key_path,
            (
                "cat /proc/uptime && "
                "cat /proc/loadavg && "
                "free -b | awk '/Mem:/{print $2,$3}' && "
                "df / -B1 --output=size,used | tail -1"
            ),
            timeout=10, known_host_key=known_host_key,
        )
        lines = stdout.strip().splitlines()
        # Line 0: uptime - "92220.27 183529.62"
        if len(lines) >= 1:
            parts = lines[0].split()
            if parts:
                stats['uptime_seconds'] = int(float(parts[0]))
        # Line 1: loadavg - "0.00 0.01 0.00 1/141 31513"
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 3:
                stats['load_avg'] = [float(parts[0]), float(parts[1]), float(parts[2])]
        # Line 2: memory - "4106113024 452595712"
        if len(lines) >= 3:
            parts = lines[2].split()
            if len(parts) >= 2:
                stats['memory_total'] = int(parts[0])
                stats['memory_used'] = int(parts[1])
        # Line 3: disk - "30083776512 1982345216"
        if len(lines) >= 4:
            parts = lines[3].split()
            if len(parts) >= 2:
                stats['disk_total'] = int(parts[0])
                stats['disk_used'] = int(parts[1])
    except Exception as e:
        logger.debug(f"System stats collection failed: {e}")
    return stats


STATS_PROTO = """\
syntax = "proto3";
package v2ray.core.app.stats.command;
message GetStatsRequest { string name = 1; bool reset = 2; }
message GetStatsResponse { Stat stat = 1; }
message QueryStatsRequest { string pattern = 1; bool reset = 2; }
message QueryStatsResponse { repeated Stat stat = 1; }
message Stat { string name = 1; int64 value = 2; }
service StatsService {
  rpc GetStats(GetStatsRequest) returns (GetStatsResponse);
  rpc QueryStats(QueryStatsRequest) returns (QueryStatsResponse);
}
"""


async def _ensure_stats_proto(host, port, username, key_path, known_host_key=None) -> None:
    """Ensure the correct stats.proto file exists on the remote server."""
    stdout, _, code = await ssh.run_command(
        host, port, username, key_path,
        "grep -q 'v2ray.core.app.stats.command' /etc/sing-box/stats.proto 2>/dev/null && echo ok || echo missing",
        timeout=5, known_host_key=known_host_key,
    )
    if stdout.strip() != "ok":
        await ssh.write_file(host, port, username, key_path, "/etc/sing-box/stats.proto", STATS_PROTO, known_host_key=known_host_key)


async def _collect_user_traffic(host, port, username, key_path, known_host_key=None) -> dict:
    """Collect per-user cumulative traffic from sing-box v2ray stats API via grpcurl.

    Returns {username: {up: int, down: int}} with cumulative byte counters.
    """
    per_user = {}
    try:
        await _ensure_stats_proto(host, port, username, key_path, known_host_key=known_host_key)
        stdout, _, code = await ssh.run_command(
            host, port, username, key_path,
            "grpcurl -plaintext -import-path /etc/sing-box -proto stats.proto "
            "-d '{}' 127.0.0.1:10085 v2ray.core.app.stats.command.StatsService/QueryStats 2>/dev/null",
            timeout=10, known_host_key=known_host_key,
        )
        if code != 0 or not stdout.strip():
            return {}
        data = json.loads(stdout.strip())
        for stat in data.get("stat", []):
            name = stat.get("name", "")
            value = int(stat.get("value", 0))
            # Format: "user>>>username>>>traffic>>>uplink" or "...>>>downlink"
            parts = name.split(">>>")
            if len(parts) == 4 and parts[0] == "user" and parts[2] == "traffic":
                uname = parts[1]
                if uname not in per_user:
                    per_user[uname] = {"up": 0, "down": 0}
                if parts[3] == "uplink":
                    per_user[uname]["up"] = value
                elif parts[3] == "downlink":
                    per_user[uname]["down"] = value
    except (json.JSONDecodeError, Exception) as e:
        logger.debug(f"v2ray stats query failed: {e}")
    return per_user


async def check_server_health(server_id: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.id == server_id))
        server = result.scalar_one_or_none()
        if not server or server.status == "provisioning":
            return

        ssh_result = await db.execute(
            select(SSHKey).where(SSHKey.id == server.ssh_key_id)
        )
        ssh_key = ssh_result.scalar_one_or_none()

    host = server.ip
    port = server.ssh_port
    username = server.ssh_user
    key_path = ssh_key.private_key_path
    hk = server.host_key  # pinned host key (may be None for legacy servers)

    new_status = "offline"
    status_message = None
    pinned_key = None  # will be set if we pin a new key

    try:
        # If no host key pinned yet, do TOFU via connect_and_pin
        if not hk:
            conn, pinned_key = await ssh.connect_and_pin(host, port, username, key_path)
            hk = pinned_key
            async with conn:
                result = await asyncio.wait_for(conn.run("systemctl is-active sing-box", check=False), timeout=15)
                stdout = result.stdout or ""
                code = result.exit_status or 0
        else:
            stdout, stderr, code = await ssh.run_command(
                host, port, username, key_path,
                "systemctl is-active sing-box",
                timeout=15, known_host_key=hk,
            )
        if stdout.strip() == "active":
            new_status = "online"
        else:
            new_status = "error"
            try:
                log_stdout, _, _ = await ssh.run_command(
                    host, port, username, key_path,
                    "journalctl -u sing-box --no-pager -n 20 --output=cat 2>/dev/null"
                    " | grep -i -E 'fatal|error|fail'"
                    " | grep -v 'did not closed properly'"
                    " | tail -3",
                    timeout=10, known_host_key=hk,
                )
                journal_errors = log_stdout.strip()
            except Exception:
                journal_errors = ""
            status_message = journal_errors if journal_errors else f"sing-box not active: {stdout.strip()}"
    except ConnectionError as e:
        new_status = "offline"
        status_message = str(e)[:500]
    except Exception as e:
        new_status = "error"
        status_message = f"Health check error: {str(e)[:500]}"

    # Collect additional data if server is reachable
    bytes_rx = bytes_tx = None
    system_stats = None
    user_traffic = {}
    if new_status == "online":
        try:
            stdout, _, code = await ssh.run_command(
                host, port, username, key_path,
                "cat /proc/net/dev | awk '/eth0|ens|enp/ {gsub(/:/, \"\"); print $2, $10}' | head -1",
                timeout=10, known_host_key=hk,
            )
            parts = stdout.strip().split()
            if len(parts) == 2:
                bytes_rx, bytes_tx = int(parts[0]), int(parts[1])
        except Exception:
            pass

        system_stats = await _collect_system_stats(host, port, username, key_path, known_host_key=hk)
        user_traffic = await _collect_user_traffic(host, port, username, key_path, known_host_key=hk)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.id == server_id))
        srv = result.scalar_one_or_none()
        if not srv:
            return

        srv.status = new_status
        srv.status_message = status_message
        srv.last_health_check = datetime.now(timezone.utc)

        # Save host key if pinned during TOFU
        if pinned_key and not srv.host_key:
            srv.host_key = pinned_key

        if system_stats:
            srv.system_stats = system_stats

        # Store network traffic snapshot
        if bytes_rx is not None:
            snapshot = ServerTrafficSnapshot(
                server_id=srv.id,
                bytes_rx=bytes_rx,
                bytes_tx=bytes_tx,
            )
            db.add(snapshot)

        # Process per-user traffic from v2ray stats API (cumulative counters)
        if user_traffic:
            prev_cache = srv.traffic_cache or {}

            # Build username → user_id map
            users_result = await db.execute(select(User))
            users = list(users_result.scalars().all())
            username_to_user = {u.username: u for u in users}

            for uname, current in user_traffic.items():
                user_obj = username_to_user.get(uname)
                if not user_obj:
                    continue

                prev = prev_cache.get(uname, {})
                prev_up = prev.get("up", 0)
                prev_down = prev.get("down", 0)
                curr_up = current["up"]
                curr_down = current["down"]

                # Compute deltas (handle counter reset on sing-box restart)
                delta_up = curr_up - prev_up if curr_up >= prev_up else curr_up
                delta_down = curr_down - prev_down if curr_down >= prev_down else curr_down

                if delta_up > 0 or delta_down > 0:
                    traffic_record = ServerUserTraffic(
                        server_id=srv.id,
                        user_id=user_obj.id,
                        bytes_up=delta_up,
                        bytes_down=delta_down,
                    )
                    db.add(traffic_record)

                    # Update global user traffic counter
                    user_obj.traffic_used_bytes += delta_up + delta_down

            # Save current cumulative counters as cache for next check
            srv.traffic_cache = user_traffic

        # Cleanup old network snapshots (keep last 24h)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        await db.execute(
            delete(ServerTrafficSnapshot).where(
                ServerTrafficSnapshot.server_id == server_id,
                ServerTrafficSnapshot.recorded_at < cutoff,
            )
        )

        await db.commit()


async def check_jumphost_health(jumphost_id: str) -> None:
    """Health check for a jumphost — same pattern as check_server_health."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
        jumphost = result.scalar_one_or_none()
        if not jumphost or jumphost.status == "provisioning":
            return

        ssh_result = await db.execute(
            select(SSHKey).where(SSHKey.id == jumphost.ssh_key_id)
        )
        ssh_key = ssh_result.scalar_one_or_none()

    host = jumphost.ip
    port = jumphost.ssh_port
    username = jumphost.ssh_user
    key_path = ssh_key.private_key_path
    hk = jumphost.host_key

    new_status = "offline"
    status_message = None
    pinned_key = None

    try:
        if not hk:
            conn, pinned_key = await ssh.connect_and_pin(host, port, username, key_path)
            hk = pinned_key
            async with conn:
                result = await asyncio.wait_for(conn.run("systemctl is-active sing-box", check=False), timeout=15)
                stdout = result.stdout or ""
        else:
            stdout, stderr, code = await ssh.run_command(
                host, port, username, key_path,
                "systemctl is-active sing-box",
                timeout=15, known_host_key=hk,
            )
        if stdout.strip() == "active":
            new_status = "online"
        else:
            new_status = "error"
            try:
                log_stdout, _, _ = await ssh.run_command(
                    host, port, username, key_path,
                    "journalctl -u sing-box --no-pager -n 20 --output=cat 2>/dev/null"
                    " | grep -i -E 'fatal|error|fail'"
                    " | grep -v 'did not closed properly'"
                    " | tail -3",
                    timeout=10, known_host_key=hk,
                )
                journal_errors = log_stdout.strip()
            except Exception:
                journal_errors = ""
            status_message = journal_errors if journal_errors else f"sing-box not active: {stdout.strip()}"
    except ConnectionError as e:
        new_status = "offline"
        status_message = str(e)[:500]
    except Exception as e:
        new_status = "error"
        status_message = f"Health check error: {str(e)[:500]}"

    # Collect stats if reachable
    bytes_rx = bytes_tx = None
    system_stats = None
    user_traffic = {}
    if new_status == "online":
        try:
            stdout, _, code = await ssh.run_command(
                host, port, username, key_path,
                "cat /proc/net/dev | awk '/eth0|ens|enp/ {gsub(/:/, \"\"); print $2, $10}' | head -1",
                timeout=10, known_host_key=hk,
            )
            parts = stdout.strip().split()
            if len(parts) == 2:
                bytes_rx, bytes_tx = int(parts[0]), int(parts[1])
        except Exception:
            pass

        system_stats = await _collect_system_stats(host, port, username, key_path, known_host_key=hk)
        user_traffic = await _collect_user_traffic(host, port, username, key_path, known_host_key=hk)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Jumphost).where(Jumphost.id == jumphost_id))
        jh = result.scalar_one_or_none()
        if not jh:
            return

        jh.status = new_status
        jh.status_message = status_message
        jh.last_health_check = datetime.now(timezone.utc)

        if pinned_key and not jh.host_key:
            jh.host_key = pinned_key

        if system_stats:
            jh.system_stats = system_stats

        if bytes_rx is not None:
            snapshot = JumphostTrafficSnapshot(
                jumphost_id=jh.id,
                bytes_rx=bytes_rx,
                bytes_tx=bytes_tx,
            )
            db.add(snapshot)

        # Process per-user traffic (same logic as servers)
        if user_traffic:
            prev_cache = jh.traffic_cache or {}
            users_result = await db.execute(select(User))
            users = list(users_result.scalars().all())
            username_to_user = {u.username: u for u in users}

            for uname, current in user_traffic.items():
                user_obj = username_to_user.get(uname)
                if not user_obj:
                    continue

                prev = prev_cache.get(uname, {})
                prev_up = prev.get("up", 0)
                prev_down = prev.get("down", 0)
                curr_up = current["up"]
                curr_down = current["down"]

                delta_up = curr_up - prev_up if curr_up >= prev_up else curr_up
                delta_down = curr_down - prev_down if curr_down >= prev_down else curr_down

                if delta_up > 0 or delta_down > 0:
                    user_obj.traffic_used_bytes += delta_up + delta_down

            jh.traffic_cache = user_traffic

        # Cleanup old snapshots
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        await db.execute(
            delete(JumphostTrafficSnapshot).where(
                JumphostTrafficSnapshot.jumphost_id == jumphost_id,
                JumphostTrafficSnapshot.recorded_at < cutoff,
            )
        )

        await db.commit()


async def run_health_checks() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Server).where(Server.status != "provisioning")
        )
        servers = list(result.scalars().all())

        jh_result = await db.execute(
            select(Jumphost).where(Jumphost.status != "provisioning")
        )
        jumphosts = list(jh_result.scalars().all())

    for server in servers:
        try:
            await check_server_health(str(server.id))
        except Exception as e:
            logger.error(f"Health check error for server {server.id}: {e}")

    for jh in jumphosts:
        try:
            await check_jumphost_health(str(jh.id))
        except Exception as e:
            logger.error(f"Health check error for jumphost {jh.id}: {e}")
