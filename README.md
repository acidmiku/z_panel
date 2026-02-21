# Z Panel

A self-hosted web panel for managing multiple VPN servers running [sing-box](https://sing-box.sagernet.org/) with **Hysteria2** and **VLESS + XTLS-Reality** protocols.

Provision VPS servers over SSH, manage users with traffic limits and expiry, generate subscription URLs for client apps, and monitor everything from a single dashboard. The panel runs on your local network via Docker Compose and connects to remote VPS instances automatically.

---

## Features

- **Multi-server provisioning** -- Add a VPS IP, and the panel handles everything: sing-box installation, Reality keypair generation, DNS record creation, firewall configuration, and automatic VPS hardening
- **Batch provisioning** -- Add multiple servers at once with a shared configuration
- **Real-time provisioning progress** -- Status pill shows the current step (e.g., "Installing sing-box...", "Hardening: firewall...")
- **Automatic VPS hardening** -- After provisioning, each server gets: key-only SSH, fail2ban, UFW lockdown, automatic security updates, kernel hardening, best-effort SSH port randomization
- **Multi-user management** -- Create users with individual credentials, traffic limits, and expiry dates
- **Dual protocol** -- Each server runs both Hysteria2 (UDP, QUIC-based) and VLESS + XTLS-Reality (TCP)
- **Subscription URLs** -- Each user gets a token-based subscription URL compatible with Clash Meta and v2rayN/v2rayNG clients
- **Cloudflare DNS integration** -- Automatically creates DNS A records for Hysteria2 ACME certificate issuance
- **Health monitoring** -- Periodic SSH checks (every 60s) with system stats: uptime, load, RAM, disk usage, and network I/O sparklines
- **Config auto-push** -- User or server changes automatically regenerate and push sing-box configs to all online servers
- **SSH host key pinning** -- Trust-on-first-use (TOFU) model prevents MITM attacks on subsequent connections
- **Production deployment** -- Caddy reverse proxy with automatic HTTPS and HTTP/3

---

## Architecture

```
                          Dev                              Prod
                      :3000 (HTTP)                  :443 (HTTPS, auto-cert)
                          |                                |
                      frontend                          Caddy
                    (nginx + React)                       |
                          |                           frontend
                     proxy /api/*                    (nginx + React)
                          |                               |
                  api (FastAPI :8000)              proxy /api/*
                          |                               |
                      enqueue tasks               api (FastAPI :8000)
                          |                               |
                  worker (arq)  ------- SSH -------> VPS 1, VPS 2, ... VPS N
                  - provisioning + hardening
                  - config push
                  - health checks
                  - traffic collection
```

### Containers

| Container | Image | Purpose |
|-----------|-------|---------|
| `postgres` | PostgreSQL 16 Alpine | Primary data store with health checks |
| `redis` | Redis 7 Alpine | Authenticated task queue broker (arq) |
| `api` | Python 3.12 slim | FastAPI backend, runs Alembic migrations on startup |
| `worker` | Python 3.12 slim | arq worker: provisioning, config push, health checks, traffic collection |
| `frontend` | nginx Alpine | Serves React SPA, proxies `/api/*`, rate limiting, security headers |
| `caddy` | Caddy 2 Alpine | *(prod only)* TLS termination, automatic certificates, HTTP/3 |

---

## Quick Start

### Prerequisites

- Docker and Docker Compose v2
- One or more VPS servers with root SSH access (Ubuntu/Debian)
- A Cloudflare account with a domain (for Hysteria2 ACME certificates via DNS-01)
- An SSH key pair (ed25519 recommended)

### 1. Clone and configure

```bash
cd vpn-panel
cp .env.example .env
```

Edit `.env`:

```bash
# Generate a strong random password
POSTGRES_PASSWORD=<strong_random_password>
DATABASE_URL=postgresql+asyncpg://vpnpanel:<same_password>@postgres:5432/vpnpanel

# Generate: openssl rand -hex 32
SECRET_KEY=<random_64_char_hex_string>

# Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=<fernet_key>

# Generate a strong random password
REDIS_PASSWORD=<redis_password>
REDIS_URL=redis://:<redis_password>@redis:6379/0

# Admin credentials for first login
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<your_admin_password>
```

### 2. Add your SSH key

Place your private SSH key in the `ssh_keys/` directory:

```bash
cp ~/.ssh/id_ed25519 ssh_keys/
chmod 600 ssh_keys/id_ed25519
```

### 3. Start the stack

**Development (HTTP, localhost):**

```bash
docker compose up --build -d
```

Access at `http://localhost:3000`.

**Production (HTTPS, public domain):**

```bash
# Set your domain in .env
echo 'PANEL_DOMAIN=panel.example.com' >> .env

# Point DNS to your server, then:
docker compose -f docker-compose.prod.yml up --build -d
```

Caddy automatically obtains a TLS certificate. Access at `https://panel.example.com`.

### 4. Initial setup

1. **Settings > SSH Keys** -- Register your SSH key (container path: `/app/ssh_keys/id_ed25519`)
2. **Settings > Cloudflare Configs** -- Add your Cloudflare API token (scoped to Zone:DNS:Edit), zone ID, and base domain
3. **Servers > Add Server** -- Enter a VPS IP and select the SSH key and Cloudflare config
4. **Users > Add User** -- Create VPN users (UUID and Hysteria2 password are auto-generated)

The server will be provisioned and hardened automatically. The status pill shows real-time progress.

---

## Provisioning Pipeline

When you add a server, the worker runs these steps automatically:

1. **SSH connectivity** -- Connects and pins the host key (TOFU)
2. **sing-box installation** -- Deploys pre-built binary (with v2ray stats API) or installs from apt
3. **Reality keypair** -- Generates on the server, stores encrypted in database
4. **DNS record** -- Creates Cloudflare A record with a neutral subdomain (e.g., `s8a2f1c3b4.example.com`)
5. **Configuration** -- Generates and pushes sing-box config with all active users
6. **Firewall** -- Opens Hysteria2 (UDP) and Reality (TCP) ports via UFW
7. **Service start** -- Enables and starts sing-box systemd service
8. **Verification** -- Polls `systemctl is-active` with retries (4 attempts, 5s apart)
9. **VPS hardening** -- Applies full security hardening (see [SECURITY.md](SECURITY.md#vps-hardening))

Each step is reflected in the UI status pill in real time.

---

## Subscription URLs

Each user gets a subscription token for auto-updating proxy configs in client apps.

### Clash Meta (Mihomo)

```
https://panel.example.com/api/profiles/sub/<token>?strategy=url-test
```

Compatible with: [Clash Verge](https://github.com/clash-verge-rev/clash-verge-rev), ClashX Meta, [Stash](https://stash.ws/), [FlClash](https://github.com/chen08209/FlClash)

Supported strategies: `url-test` (auto-select fastest), `fallback`, `load-balance`

### v2rayN / v2rayNG

```
https://panel.example.com/api/profiles/sub/<token>/v2ray
```

Returns base64-encoded URI list with Hysteria2 and VLESS-Reality entries for all online servers.

Both endpoints are public (no auth header needed) but protected by a 256-bit random token and rate-limited to 10 requests/minute per IP.

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_USER` | PostgreSQL username | `vpnpanel` |
| `POSTGRES_PASSWORD` | PostgreSQL password | *(required)* |
| `POSTGRES_DB` | PostgreSQL database name | `vpnpanel` |
| `DATABASE_URL` | Full async database URL | *(required)* |
| `REDIS_PASSWORD` | Redis authentication password | *(required)* |
| `REDIS_URL` | Redis connection URL (include password) | *(required)* |
| `SECRET_KEY` | JWT signing secret | *(required)* |
| `ENCRYPTION_KEY` | Fernet key for encrypting secrets at rest | *(required)* |
| `ADMIN_USERNAME` | Initial admin username | `admin` |
| `ADMIN_PASSWORD` | Initial admin password | *(required)* |
| `SSH_KEYS_DIR` | Path to SSH keys inside container | `/app/ssh_keys` |
| `HEALTH_CHECK_INTERVAL` | Seconds between health checks | `60` |
| `PANEL_DOMAIN` | Domain for production HTTPS (prod only) | -- |

### Port Defaults

| Protocol | Default Port | Transport |
|----------|-------------|-----------|
| Hysteria2 | 443 | UDP |
| VLESS + Reality | 443 | TCP |

Since Hysteria2 uses UDP and VLESS uses TCP, they can share port 443. You can configure different ports per server.

---

## Usage

### Managing Servers

- **Add** -- Enter VPS details, provisioning starts automatically
- **Batch Add** -- Provision multiple VPS servers with shared settings
- **Sync** -- Force re-push sing-box config to a server
- **Reinstall** -- Full re-provisioning of an existing server
- **Delete** -- Stops sing-box, removes DNS record, deletes from database
- **Logs** -- View sing-box journal logs from the server

### Managing Users

- **Create** -- Provide username; UUID, Hysteria2 password, and subscription token are auto-generated
- **Traffic Limit** -- Set in GB, or leave unlimited. Tracked per-server via v2ray stats API
- **Expiry** -- Set a date, or leave as never
- **Enable/Disable** -- Toggle access without deleting
- **Subscription URL** -- Copy the auto-updating config URL for client apps

Changes to users automatically trigger config push to all online servers.

### Dashboard

- Server count and status breakdown
- Total traffic across all servers and users
- Per-server system stats: uptime, load average, RAM/disk usage
- Network I/O sparklines (last 60 minutes)

### Health Monitoring

The worker checks all servers every 60 seconds via SSH:
- Verifies `systemctl is-active sing-box`
- Collects system stats (uptime, load, memory, disk)
- Collects per-user traffic via v2ray gRPC stats API
- Updates server status: `online`, `offline`, or `error`

The frontend polls every 30s (3s during provisioning).

---

## API Reference

All endpoints except login and subscription require `Authorization: Bearer <token>`.

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login, returns JWT (rate limited: 5/min) |
| POST | `/api/auth/change-password` | Change admin password |

### Servers
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/servers` | List all servers with system stats |
| POST | `/api/servers` | Add and provision a new server |
| POST | `/api/servers/batch` | Batch-add multiple servers |
| GET | `/api/servers/{id}` | Server details |
| PATCH | `/api/servers/{id}` | Update server settings |
| DELETE | `/api/servers/{id}` | Stop sing-box, remove DNS, delete |
| POST | `/api/servers/{id}/sync` | Force config re-push |
| POST | `/api/servers/{id}/reinstall` | Full re-provisioning |
| GET | `/api/servers/{id}/logs` | Fetch sing-box journal logs |
| GET | `/api/servers/{id}/traffic-history` | Network I/O rate history |

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users` | List all users |
| POST | `/api/users` | Create user (auto-generates credentials) |
| GET | `/api/users/{id}` | User details with per-server traffic |
| PATCH | `/api/users/{id}` | Update user settings |
| DELETE | `/api/users/{id}` | Delete user, push configs |

### Profiles (Subscriptions)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/profiles/sub/{token}` | Clash Meta subscription (public, rate limited) |
| GET | `/api/profiles/sub/{token}/v2ray` | v2rayN/v2rayNG subscription (public, rate limited) |
| GET | `/api/profiles/{user_id}/clash` | Admin download of Clash profile |

### Settings
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cloudflare-configs` | List Cloudflare configs |
| POST | `/api/cloudflare-configs` | Add config |
| DELETE | `/api/cloudflare-configs/{id}` | Delete config |
| GET | `/api/ssh-keys` | List registered keys |
| POST | `/api/ssh-keys` | Register a key by path |
| DELETE | `/api/ssh-keys/{id}` | Delete key |

### Stats
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stats/summary` | Dashboard summary |
| GET | `/api/stats/traffic` | Traffic records (filterable) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, arq, asyncssh, httpx |
| Database | PostgreSQL 16 |
| Queue | Redis 7 (authenticated) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, react-router-dom v6, Lucide icons |
| Reverse Proxy | Caddy 2 (prod), nginx (dev) |
| Infrastructure | Docker, Docker Compose |
| VPS Software | sing-box (with v2ray stats API) |
| DNS | Cloudflare API |
| Protocols | Hysteria2, VLESS + XTLS-Reality |

---

## Project Structure

```
vpn-panel/
├── docker-compose.yml              # Dev: HTTP on :3000
├── docker-compose.prod.yml         # Prod: HTTPS via Caddy
├── Caddyfile                       # Caddy reverse proxy config
├── .env.example
├── ssh_keys/                       # Mounted read-only into containers
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/versions/           # 001-007 migrations
│   └── app/
│       ├── main.py                 # FastAPI app, CORS config
│       ├── config.py               # pydantic-settings
│       ├── database.py             # Async SQLAlchemy engine
│       ├── models.py               # ORM models (7 tables)
│       ├── schemas.py              # Pydantic schemas with validation
│       ├── auth.py                 # JWT + bcrypt
│       ├── deps.py                 # FastAPI dependencies
│       ├── seed.py                 # Admin user seeding
│       ├── worker.py               # arq worker with cron tasks
│       ├── routers/                # API route handlers
│       └── services/
│           ├── ssh.py              # asyncssh with host key pinning
│           ├── provisioner.py      # Full provisioning pipeline
│           ├── hardener.py         # VPS hardening (post-provision)
│           ├── config_pusher.py    # Config regeneration + push
│           ├── singbox_config.py   # sing-box JSON generator
│           ├── clash_config.py     # Clash Meta YAML generator
│           ├── cloudflare.py       # Cloudflare DNS API client
│           ├── health.py           # Health checks + stats collection
│           └── crypto.py           # Fernet encryption for secrets
└── frontend/
    ├── Dockerfile
    ├── nginx.conf                  # Rate limiting, security headers, CSP
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    └── src/
        ├── App.tsx                 # Router setup
        ├── index.css               # Theme variables, animations
        ├── api/                    # Axios client + TanStack Query hooks
        ├── components/             # StatusBadge, ServerCard, Sparkline, etc.
        ├── pages/                  # Dashboard, Servers, Users, Settings, Login
        ├── hooks/                  # useAuth, useMaskIPs, useTheme
        └── lib/                    # Utility functions
```

---

## Security

See [SECURITY.md](SECURITY.md) for a detailed breakdown of all security measures, including:
- Encryption at rest (Fernet for API tokens and Reality private keys)
- SSH host key pinning (TOFU model)
- VPS hardening details (UFW, fail2ban, sysctl, SSH lockdown)
- Rate limiting and security headers
- Input validation
- Known limitations and threat model

---

## Troubleshooting

### Server stuck in "provisioning"
```bash
docker compose logs worker
```
Common causes: SSH key permissions (must be `chmod 600`), VPS not reachable, cloud firewall blocking SSH port.

### sing-box not starting on VPS
```bash
systemctl status sing-box
journalctl -u sing-box -n 50
cat /etc/sing-box/config.json
```

### Hysteria2 certificate issues
sing-box needs the Cloudflare API token for ACME DNS-01 challenges. Verify:
```bash
systemctl cat sing-box  # Check Environment= in override
```
Ensure the DNS A record exists and points to the correct IP.

### SSH port changed during hardening
The panel automatically tracks the new SSH port in the database. If manually locked out:
1. Access VPS via provider's web console (VNC/KVM)
2. Edit `/etc/ssh/sshd_config` -- change Port back to 22
3. Run `ufw allow 22/tcp && systemctl restart sshd`
4. Update the server's SSH port in the panel

### Frontend not loading
```bash
docker compose logs frontend
docker compose logs api
curl http://localhost:3000/api/health
```

### Database migration errors
```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic current
```

---

## License

This project is provided as-is for personal use. Use responsibly and in accordance with applicable laws.
