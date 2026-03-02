"""SSH operations using asyncssh with host key pinning."""
import asyncio
import logging
import shlex
import uuid as _uuid
from typing import Optional, Tuple

import asyncssh

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
CONNECT_TIMEOUT = 30

# Strong algorithms only — no SHA-1 (ssh-rsa, diffie-hellman-group14-sha1)
_HOST_KEY_ALGS = [
    "ssh-ed25519",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
    "rsa-sha2-512",
    "rsa-sha2-256",
]
_KEX_ALGS = [
    "curve25519-sha256",
    "curve25519-sha256@libssh.org",
    "ecdh-sha2-nistp256",
    "ecdh-sha2-nistp384",
    "ecdh-sha2-nistp521",
    "diffie-hellman-group-exchange-sha256",
    "diffie-hellman-group14-sha256",
]
_SIG_ALGS = [
    "ssh-ed25519",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
    "rsa-sha2-512",
    "rsa-sha2-256",
]


def _encode_host_key(key: asyncssh.SSHKey) -> str:
    """Encode an SSH public key to a storable string: 'algorithm base64data'."""
    key_data = key.export_public_key("openssh").decode().strip()
    # openssh format: "algo base64 comment" — take first two parts
    parts = key_data.split(None, 2)
    return f"{parts[0]} {parts[1]}"


async def _connect(
    host: str,
    port: int,
    username: str,
    private_key_path: str,
) -> asyncssh.SSHClientConnection:
    """Low-level connect with known_hosts disabled (verification done post-connect)."""
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            conn = await asyncio.wait_for(
                asyncssh.connect(
                    host,
                    port=port,
                    username=username,
                    client_keys=[private_key_path],
                    known_hosts=None,
                    server_host_key_algs=_HOST_KEY_ALGS,
                    kex_algs=_KEX_ALGS,
                    signature_algs=_SIG_ALGS,
                ),
                timeout=CONNECT_TIMEOUT,
            )
            return conn
        except (asyncssh.Error, OSError, asyncio.TimeoutError) as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
    raise ConnectionError(f"SSH connection failed after {MAX_RETRIES} attempts: {last_error}")


async def connect_and_pin(
    host: str,
    port: int,
    username: str,
    private_key_path: str,
    known_host_key: Optional[str] = None,
) -> Tuple[asyncssh.SSHClientConnection, str]:
    """Connect and return (connection, host_key_string).

    On first connect (known_host_key=None), captures the host key (TOFU).
    On subsequent connects, verifies against known_host_key and raises
    ConnectionError on mismatch before any commands are sent.
    """
    conn = await _connect(host, port, username, private_key_path)
    peer_key = conn.get_server_host_key()
    current_key = _encode_host_key(peer_key)

    if known_host_key and current_key != known_host_key:
        conn.close()
        raise ConnectionError(
            f"SSH host key mismatch for {host}:{port} — possible MITM attack. "
            f"Expected: {known_host_key[:40]}..., got: {current_key[:40]}..."
        )

    return conn, current_key


async def run_command(
    host: str,
    port: int,
    username: str,
    private_key_path: str,
    command: str,
    timeout: int = 120,
    known_host_key: Optional[str] = None,
    elevate: bool = True,
) -> Tuple[str, str, int]:
    if elevate and username != "root":
        command = f"sudo -n sh -c {shlex.quote(command)}"
    conn, _ = await connect_and_pin(host, port, username, private_key_path, known_host_key)
    async with conn:
        result = await asyncio.wait_for(
            conn.run(command, check=False),
            timeout=timeout,
        )
        return result.stdout or "", result.stderr or "", result.exit_status or 0


async def write_file(
    host: str,
    port: int,
    username: str,
    private_key_path: str,
    remote_path: str,
    content: str,
    known_host_key: Optional[str] = None,
    elevate: bool = True,
) -> None:
    conn, _ = await connect_and_pin(host, port, username, private_key_path, known_host_key)
    async with conn:
        if elevate and username != "root":
            # Non-root: SFTP to /tmp (writable), then sudo mv to target
            tmp = f"/tmp/_zpanel_{_uuid.uuid4().hex[:8]}"
            async with conn.start_sftp_client() as sftp:
                async with sftp.open(tmp, "w") as f:
                    await f.write(content)
            result = await asyncio.wait_for(
                conn.run(
                    f"sudo -n mkdir -p $(dirname {shlex.quote(remote_path)}) && "
                    f"sudo -n mv {tmp} {shlex.quote(remote_path)}",
                    check=False,
                ),
                timeout=15,
            )
            if (result.exit_status or 0) != 0:
                raise RuntimeError(
                    f"Elevated write to {remote_path} failed: "
                    f"{(result.stderr or '')[:200]}"
                )
        else:
            async with conn.start_sftp_client() as sftp:
                async with sftp.open(remote_path, "w") as f:
                    await f.write(content)


async def upload_file(
    host: str,
    port: int,
    username: str,
    private_key_path: str,
    local_path: str,
    remote_path: str,
    known_host_key: Optional[str] = None,
    elevate: bool = True,
) -> None:
    conn, _ = await connect_and_pin(host, port, username, private_key_path, known_host_key)
    async with conn:
        if elevate and username != "root":
            # Non-root: SCP to /tmp, then sudo mv to target
            tmp = f"/tmp/_zpanel_{_uuid.uuid4().hex[:8]}"
            await asyncssh.scp(local_path, (conn, tmp))
            result = await asyncio.wait_for(
                conn.run(
                    f"sudo -n mv {tmp} {shlex.quote(remote_path)}",
                    check=False,
                ),
                timeout=15,
            )
            if (result.exit_status or 0) != 0:
                raise RuntimeError(
                    f"Elevated upload to {remote_path} failed: "
                    f"{(result.stderr or '')[:200]}"
                )
        else:
            await asyncssh.scp(local_path, (conn, remote_path))


async def test_connectivity(
    host: str,
    port: int,
    username: str,
    private_key_path: str,
    known_host_key: Optional[str] = None,
) -> bool:
    try:
        conn, _ = await connect_and_pin(host, port, username, private_key_path, known_host_key)
        async with conn:
            result = await asyncio.wait_for(conn.run("echo ok"), timeout=10)
            return "ok" in (result.stdout or "")
    except Exception as e:
        logger.error(f"SSH connectivity test failed for {host}: {e}")
        return False
