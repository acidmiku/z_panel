# Stage 1: Build sing-box with v2ray_api support
FROM golang:1.23-alpine AS singbox-builder
RUN CGO_ENABLED=0 go install -v -tags "with_v2ray_api,with_gvisor,with_quic,with_dhcp,with_wireguard,with_utls,with_acme,with_clash_api" \
    github.com/sagernet/sing-box/cmd/sing-box@v1.12.22

# Stage 2: Python backend
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-built sing-box binary with v2ray_api for deployment to servers
COPY --from=singbox-builder /go/bin/sing-box /app/sing-box-binary

# Run as non-root user
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser && \
    mkdir -p /app/ssh_keys && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
