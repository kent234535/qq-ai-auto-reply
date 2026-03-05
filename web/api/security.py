"""API access controls."""

from __future__ import annotations

import ipaddress
import os

from fastapi import HTTPException, Request


def _allow_remote_web() -> bool:
    return os.environ.get("ALLOW_REMOTE_WEB", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _is_loopback_host(host: str) -> bool:
    if not host:
        return False
    h = host.strip().lower()
    if h in {"localhost", "127.0.0.1", "::1"}:
        return True
    if h.startswith("::ffff:"):
        h = h.split("::ffff:", 1)[1]
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False


async def require_local_request(request: Request) -> None:
    """By default, only allow local API access to avoid accidental exposure."""
    if _allow_remote_web():
        return
    client_host = request.client.host if request.client else ""
    if _is_loopback_host(client_host):
        return
    raise HTTPException(
        status_code=403,
        detail="默认仅允许本机访问 API。若需远程访问，请设置 ALLOW_REMOTE_WEB=1 并自行配置鉴权。",
    )
