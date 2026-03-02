"""FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, servers, users, profiles, stats, cloudflare_configs, ssh_keys, jumphosts, routing, chain_configs


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(title="VPN Panel API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(servers.router, prefix="/api/servers", tags=["servers"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(profiles.router, prefix="/api/profiles", tags=["profiles"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(cloudflare_configs.router, prefix="/api/cloudflare-configs", tags=["cloudflare"])
app.include_router(ssh_keys.router, prefix="/api/ssh-keys", tags=["ssh-keys"])
app.include_router(jumphosts.router, prefix="/api/jumphosts", tags=["jumphosts"])
app.include_router(routing.router, prefix="/api/routing", tags=["routing"])
app.include_router(chain_configs.router, prefix="/api/chain-configs", tags=["chain-configs"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
