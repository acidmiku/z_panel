# Security

This document covers the security measures implemented in Z Panel, both for the admin panel itself and for the VPS servers it manages.

---

## VPN Traffic Security

Both protocols use TLS 1.3 encryption. An observer (ISP, network admin) can see that you're connecting to your VPS IP, but cannot read the traffic content.

### Hysteria2 (UDP/QUIC)

- TLS 1.3 over QUIC with a legitimate Let's Encrypt certificate (issued via Cloudflare DNS-01 challenge)
- An observer can detect QUIC-based traffic and may identify Hysteria2 through traffic analysis
- DNS subdomains use neutral names (e.g., `s8a2f1c3b4.example.com`) to avoid fingerprinting

### VLESS + XTLS-Reality (TCP)

- TLS 1.3 with the Reality protocol
- Active probing returns a genuine TLS response from the camouflage target (e.g., `dl.google.com`), making the server indistinguishable from a legitimate endpoint
- Only clients with the correct Reality private key and short_id receive proxy service
- The main detection vector is IP mismatch: the VPS IP doesn't belong to Google's ASN, which requires active analysis to discover

### DNS

- On VPS: DNS resolved via DNS-over-HTTPS (DoH) to Cloudflare 1.1.1.1 and Google 8.8.8.8
- On client: Clash Meta uses fake-ip mode -- local DNS queries return addresses from the 198.18.0.0/16 range, actual resolution happens through the tunnel

---

## Panel Security

### Encryption at Rest

- **Cloudflare API tokens** -- Encrypted with Fernet symmetric encryption before storage in PostgreSQL. The key is derived from `ENCRYPTION_KEY` in `.env`
- **Reality private keys** -- Encrypted with the same Fernet mechanism. Only decrypted when generating sing-box configs for push
- **Admin password** -- Hashed with bcrypt (not reversible)
- **VPN user credentials** -- UUIDs and Hysteria2 passwords are stored in plaintext (they need to be pushed to sing-box configs). Protected by database access controls

### Authentication

- Single admin user, seeded from environment variables on first startup
- JWT tokens signed with `SECRET_KEY`, 24-hour expiry
- Password change available via Settings page
- Token stored in localStorage (protected by CSP against XSS)

### CORS

- Restricted to explicit origins (`http://localhost:3000`, `http://127.0.0.1:3000`)
- No wildcard origins

### Rate Limiting (nginx)

Three tiers of rate limiting applied at the nginx reverse proxy level:

| Endpoint | Rate | Burst |
|----------|------|-------|
| `/api/auth/login` | 5 req/min | 3 |
| `/api/profiles/sub/` | 10 req/min | 5 |
| All other `/api/` | 30 req/s | 50 |

When deployed behind Caddy (production), rate limiting uses the `X-Real-IP` header to correctly identify clients. In dev mode, it falls back to the direct remote address.

### Security Headers

Applied by nginx on all responses:

- `X-Frame-Options: DENY` -- Prevents clickjacking
- `X-Content-Type-Options: nosniff` -- Prevents MIME sniffing
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self' data:; frame-ancestors 'none';`

### Input Validation

- **IP addresses** -- Validated with regex + octet range check (0-255)
- **Ports** -- Pydantic `Field(ge=1, le=65535)` on all port fields
- **String lengths** -- `max_length` constraints on names, paths, and other text fields
- **Subscription tokens** -- 256-bit random values via `secrets.token_urlsafe(32)`

### SSH Security

- **Host key pinning (TOFU)** -- On first connection to a VPS, the SSH host key is captured and stored in the database. All subsequent connections verify the key matches. A mismatch raises `ConnectionError` and aborts the operation, preventing MITM attacks
- **Strong algorithms only** -- SHA-1 based algorithms (`ssh-rsa`, `diffie-hellman-group14-sha1`) are excluded. Only ed25519, ECDSA, and RSA-SHA2 are used
- **Key-based auth only** -- SSH keys mounted read-only into containers. No passwords stored or transmitted
- **Retry with backoff** -- 3 attempts with exponential backoff for transient failures

### Redis Authentication

Redis requires a password (`REDIS_PASSWORD`) in both dev and production Docker Compose configurations. The connection URL includes the password.

### Production TLS

The `docker-compose.prod.yml` uses Caddy for automatic HTTPS:
- Automatic certificate issuance and renewal via ACME
- HTTP/3 (QUIC) support
- HTTP-to-HTTPS redirect
- Frontend nginx is not exposed directly -- only Caddy receives external traffic

---

## VPS Hardening

Applied automatically after sing-box provisioning is verified online. Each step runs over SSH and progress is shown in real time on the status pill.

### What Gets Applied

1. **Security packages** -- `fail2ban` and `unattended-upgrades` installed

2. **Automatic security updates** -- Configured to apply security-only patches daily. No feature upgrades, no automatic reboots

3. **Kernel hardening (sysctl)** -- Written to `/etc/sysctl.d/99-zpanel-hardening.conf`:

   | Parameter | Purpose |
   |-----------|---------|
   | `net.ipv4.conf.all.rp_filter = 1` | IP spoofing protection |
   | `net.ipv4.conf.all.accept_redirects = 0` | Ignore ICMP redirects |
   | `net.ipv4.conf.all.send_redirects = 0` | Don't send ICMP redirects |
   | `net.ipv4.icmp_echo_ignore_broadcasts = 1` | Ignore broadcast pings |
   | `net.ipv4.tcp_syncookies = 1` | SYN flood protection |
   | `net.ipv4.tcp_max_syn_backlog = 2048` | SYN queue size |
   | `net.ipv4.conf.all.accept_source_route = 0` | Disable source routing |
   | `net.ipv4.conf.all.log_martians = 1` | Log impossible addresses |

4. **Unnecessary services disabled** -- snapd, apache2, cups, avahi-daemon (best-effort, errors ignored)

5. **SSH authentication lockdown**:
   - `PasswordAuthentication no`
   - `ChallengeResponseAuthentication no`
   - `KbdInteractiveAuthentication no`
   - `PubkeyAuthentication yes`
   - `PermitRootLogin prohibit-password`

6. **SSH port change (best-effort)** -- A random port (10000-60000) is assigned. If the VPS provider's cloud firewall blocks the new port, the change is reverted and hardening continues with the original port. The active SSH port is stored in the database and used automatically for all subsequent operations

7. **UFW firewall** -- Complete reset, then:
   - Default deny incoming, allow outgoing
   - Allow SSH port (TCP)
   - Allow Hysteria2 port (UDP)
   - Allow VLESS-Reality port (TCP)
   - Everything else blocked

8. **fail2ban** -- SSH jail configured for the active SSH port: 3 retries, 1-hour ban, 10-minute find window

### Hardening Recovery

If SSH becomes unreachable after hardening (rare -- the panel verifies before committing):

1. Access VPS via hosting provider's web console (VNC/KVM)
2. Edit `/etc/ssh/sshd_config` -- change `Port` back to `22`
3. Run: `ufw allow 22/tcp && systemctl restart sshd`
4. Update the server's SSH port in the Z Panel UI

---

## Threat Model

### What's protected

| Scenario | Impact |
|----------|--------|
| ISP monitors traffic | Sees encrypted connection to VPS IP only. Content invisible |
| Public WiFi sniffing | Same as ISP -- TLS 1.3 protects content |
| DPI / censorship | Hysteria2: detectable via traffic patterns. Reality: very hard to detect |
| Panel brute force | Rate limited to 5 login attempts/min, bcrypt hashes |
| Subscription token guessing | 256-bit entropy, rate limited to 10 req/min |

### Residual risks

| Risk | Mitigation | Notes |
|------|-----------|-------|
| VPS compromise | Each VPS has the Cloudflare API token in a systemd override | Use scoped tokens (single zone, DNS:Edit only) to limit blast radius |
| Database dump | API tokens and Reality keys encrypted with Fernet | Security depends on `ENCRYPTION_KEY` strength |
| JWT theft via XSS | CSP restricts script sources to `'self'` | Consider httpOnly cookies for defense in depth |
| Admin panel on HTTP (dev) | Dev mode only, intended for local network | Use `docker-compose.prod.yml` for any non-local deployment |
| VPS IP attribution | VPS IP is visible to observers regardless of protocol | Use providers that accept anonymous payment if needed |

---

## Recommendations for Operators

1. **Use scoped Cloudflare API tokens** -- Create a token with only Zone:DNS:Edit permission for the specific zone. This limits damage if a VPS is compromised
2. **Generate a proper `ENCRYPTION_KEY`** -- Use `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` -- never use a guessable value
3. **Use production mode** for any non-localhost deployment -- `docker-compose.prod.yml` with Caddy provides automatic HTTPS
4. **Change the admin password** after first login via Settings
5. **Use ed25519 SSH keys** -- stronger and faster than RSA
6. **Back up your `.env` file** securely -- it contains all encryption keys and credentials
7. **Monitor worker logs** -- `docker compose logs -f worker` shows provisioning, health checks, and any errors
