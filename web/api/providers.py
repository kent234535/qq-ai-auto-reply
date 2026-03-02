"""模型 CRUD API"""

from __future__ import annotations

import re
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import config

router = APIRouter()


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


def _safe_provider(p: dict) -> dict:
    safe = dict(p)
    safe["api_key"] = _mask_key(safe.get("api_key", ""))
    return safe


class ProviderCreate(BaseModel):
    name: str
    type: str = "openai_compat"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    enabled: bool = True
    id: str | None = None


class ProviderUpdate(BaseModel):
    name: str
    type: str = "openai_compat"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    enabled: bool = True


class ProviderModelKeyUpdate(BaseModel):
    model: str | None = None
    api_key: str | None = None


class ListModelsRequest(BaseModel):
    type: str = "openai_compat"
    base_url: str = ""
    api_key: str = ""


def _slug(text: str, fallback: str = "provider") -> str:
    value = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    value = value[:24]
    return value or fallback


def _generate_provider_id(name: str) -> str:
    existing = {p.get("id", "") for p in config.providers}
    base = _slug(name, "provider")
    for _ in range(8):
        candidate = f"{base}-{uuid4().hex[:6]}"
        if candidate not in existing:
            return candidate
    return f"provider-{uuid4().hex}"


@router.get("")
async def list_providers():
    return [_safe_provider(p) for p in config.providers]


@router.post("")
async def create_provider(body: ProviderCreate):
    data = body.model_dump()
    data["id"] = _generate_provider_id(body.name)
    config.add_provider(data)
    return {"ok": True, "id": data["id"]}


@router.post("/list-models")
async def list_available_models(body: ListModelsRequest):
    if not body.base_url or not body.api_key:
        raise HTTPException(400, "please fill Base URL and API Key")

    try:
        if body.type == "claude":
            base = body.base_url.rstrip("/") if body.base_url else "https://api.anthropic.com"
            url = f"{base}/v1/models"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers={
                    "x-api-key": body.api_key,
                    "anthropic-version": "2023-06-01",
                })
                resp.raise_for_status()
                data = resp.json()
                models = sorted([m["id"] for m in data.get("data", [])])
        else:
            url = f"{body.base_url.rstrip('/')}/models"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers={
                    "Authorization": f"Bearer {body.api_key}",
                })
                resp.raise_for_status()
                data = resp.json()
                models = sorted([m["id"] for m in data.get("data", [])])
        return {"ok": True, "models": models}
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, f"API error: {e.response.status_code}")
    except httpx.RequestError as e:
        raise HTTPException(502, f"Connection failed: {e}")


@router.get("/{provider_id}/raw-key")
async def get_provider_raw_key(provider_id: str):
    """Return the unmasked API key for editing."""
    p = config.get_provider(provider_id)
    if not p:
        raise HTTPException(404, "provider not found")
    return {"api_key": p.get("api_key", "")}


@router.get("/{provider_id}/models")
async def list_provider_models(provider_id: str):
    """Use stored credentials to list available models for an existing provider."""
    p = config.get_provider(provider_id)
    if not p:
        raise HTTPException(404, "provider not found")
    if not p.get("base_url") or not p.get("api_key"):
        raise HTTPException(400, "provider missing base_url or api_key")

    try:
        if p.get("type") == "claude":
            base = p["base_url"].rstrip("/") if p.get("base_url") else "https://api.anthropic.com"
            url = f"{base}/v1/models"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers={
                    "x-api-key": p["api_key"],
                    "anthropic-version": "2023-06-01",
                })
                resp.raise_for_status()
                data = resp.json()
                models = sorted([m["id"] for m in data.get("data", [])])
        else:
            url = f"{p['base_url'].rstrip('/')}/models"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers={
                    "Authorization": f"Bearer {p['api_key']}",
                })
                resp.raise_for_status()
                data = resp.json()
                models = sorted([m["id"] for m in data.get("data", [])])
        return {"ok": True, "models": models}
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, f"API error: {e.response.status_code}")
    except httpx.RequestError as e:
        raise HTTPException(502, f"Connection failed: {e}")


class TestModelRequest(BaseModel):
    type: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None


@router.post("/{provider_id}/test")
async def test_provider_model(provider_id: str, body: TestModelRequest | None = None):
    """Send a minimal chat request to verify the model works.
    Body fields override stored values (useful for testing unsaved edits).
    """
    stored = config.get_provider(provider_id)
    if not stored:
        raise HTTPException(404, "provider not found")

    # Merge: body overrides stored, but skip masked/empty api_key
    p_type = (body and body.type) or stored.get("type", "openai_compat")
    p_base = (body and body.base_url) or stored.get("base_url", "")
    p_model = (body and body.model) or stored.get("model", "")
    p_key = stored.get("api_key", "")
    if body and body.api_key and "****" not in body.api_key:
        p_key = body.api_key

    if not p_base or not p_key or not p_model:
        raise HTTPException(400, "missing base_url, api_key, or model")

    try:
        if p_type == "claude":
            base = p_base.rstrip("/") if p_base else "https://api.anthropic.com"
            url = f"{base}/v1/messages"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, headers={
                    "x-api-key": p_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                }, json={
                    "model": p_model,
                    "max_tokens": 5,
                    "messages": [{"role": "user", "content": "hi"}],
                })
                resp.raise_for_status()
        else:
            url = f"{p_base.rstrip('/')}/chat/completions"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, headers={
                    "Authorization": f"Bearer {p_key}",
                    "Content-Type": "application/json",
                }, json={
                    "model": p_model,
                    "max_tokens": 5,
                    "messages": [{"role": "user", "content": "hi"}],
                })
                resp.raise_for_status()
        return {"ok": True}
    except httpx.HTTPStatusError as e:
        detail = ""
        try:
            err_body = e.response.json()
            detail = err_body.get("error", {}).get("message", "") or str(err_body)
        except Exception:
            detail = e.response.text[:200]
        raise HTTPException(e.response.status_code, detail or f"HTTP {e.response.status_code}")
    except httpx.RequestError as e:
        raise HTTPException(502, f"Connection failed: {e}")


@router.get("/{provider_id}")
async def get_provider(provider_id: str):
    p = config.get_provider(provider_id)
    if not p:
        raise HTTPException(404, "provider not found")
    return _safe_provider(p)


@router.put("/{provider_id}")
async def update_provider(provider_id: str, body: ProviderUpdate):
    data = body.model_dump()
    data["id"] = provider_id
    if not data.get("api_key") or "****" in data.get("api_key", ""):
        existing = config.get_provider(provider_id)
        if existing:
            data["api_key"] = existing["api_key"]
    config.add_provider(data)
    return {"ok": True}


@router.patch("/{provider_id}/model-key")
async def update_provider_model_key(provider_id: str, body: ProviderModelKeyUpdate):
    existing = config.get_provider(provider_id)
    if not existing:
        raise HTTPException(404, "provider not found")

    data = dict(existing)

    if body.model is not None:
        data["model"] = body.model

    if body.api_key is not None:
        if "****" not in body.api_key and body.api_key.strip() != "":
            data["api_key"] = body.api_key

    config.add_provider(data)
    return {"ok": True}


@router.delete("/{provider_id}")
async def delete_provider(provider_id: str):
    if config.delete_provider(provider_id):
        return {"ok": True}
    raise HTTPException(404, "provider not found")
