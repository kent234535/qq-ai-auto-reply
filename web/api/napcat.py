"""NapCat 启停 / 二维码代理 API"""

from __future__ import annotations

import asyncio
import glob as _glob
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

import httpx

router = APIRouter()

# ─── 平台检测 ───

_IS_WIN = sys.platform == "win32"
_IS_MAC = sys.platform == "darwin"


def _check_napcat_mode(package_json: Path) -> bool:
    """检查某个 package.json 是否已配置 NapCat"""
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
        return "napcat" in data.get("main", "").lower()
    except Exception:
        return False


def _app_exe(app_dir: str) -> str:
    """从 .app 目录推导可执行文件路径"""
    if _IS_MAC:
        return f"{app_dir}/Contents/MacOS/QQ"
    elif _IS_WIN:
        return f"{app_dir}\\QQ.exe"
    return f"{app_dir}/qq"


def _app_pkg(app_dir: str) -> Path:
    """从 .app 目录推导 package.json 路径"""
    if _IS_MAC:
        return Path(f"{app_dir}/Contents/Resources/app/package.json")
    elif _IS_WIN:
        return Path(f"{app_dir}\\resources\\app\\package.json")
    return Path(f"{app_dir}/resources/app/package.json")


def _detect_napcat_apps() -> list[dict]:
    """扫描本机所有已配置 NapCat 的 QQ 应用，返回列表。"""
    apps: list[dict] = []
    if _IS_MAC:
        for app_path in sorted(_glob.glob("/Applications/QQ*.app")):
            name = Path(app_path).name
            if "Browser" in name:
                continue
            pkg = _app_pkg(app_path)
            if pkg.exists() and _check_napcat_mode(pkg):
                apps.append({
                    "app_dir": app_path,
                    "exe": _app_exe(app_path),
                    "package_json": str(pkg),
                    "name": name,
                })
    elif _IS_WIN:
        for d in [r"C:\Program Files\Tencent\QQNT"]:
            pkg = _app_pkg(d)
            if pkg.exists() and _check_napcat_mode(pkg):
                apps.append({
                    "app_dir": d,
                    "exe": _app_exe(d),
                    "package_json": str(pkg),
                    "name": Path(d).name,
                })
    else:
        for d in ["/opt/QQ"]:
            pkg = _app_pkg(d)
            if pkg.exists() and _check_napcat_mode(pkg):
                apps.append({
                    "app_dir": d,
                    "exe": _app_exe(d),
                    "package_json": str(pkg),
                    "name": Path(d).name,
                })
    return apps


# 当前使用的 QQ 路径（可通过 API 切换）
_napcat_apps = _detect_napcat_apps()
_active_exe: str = _napcat_apps[0]["exe"] if _napcat_apps else ""

_WEBUI_CONFIG_CANDIDATES: list[Path]
_QRCODE_IMAGE_CANDIDATES: list[Path]

if _IS_WIN:
    _WEBUI_CONFIG_CANDIDATES = [
        Path.home() / "AppData/Local/NapCat/config/webui.json",
        Path.home() / "AppData/Roaming/NapCat/config/webui.json",
    ]
    _QRCODE_IMAGE_CANDIDATES = [
        Path.home() / "AppData/Local/NapCat/cache/qrcode.png",
        Path.home() / "AppData/Roaming/NapCat/cache/qrcode.png",
    ]
elif _IS_MAC:
    _WEBUI_CONFIG_CANDIDATES = [
        Path.home() / "Library/Application Support/QQ/NapCat/config/webui.json",
        Path.home() / "Library/Containers/com.tencent.qq/Data/Library/Application Support/QQ/NapCat/config/webui.json",
    ]
    _QRCODE_IMAGE_CANDIDATES = [
        Path.home() / "Library/Application Support/QQ/NapCat/cache/qrcode.png",
        Path.home() / "Library/Containers/com.tencent.qq/Data/Library/Application Support/QQ/NapCat/cache/qrcode.png",
    ]
else:
    _WEBUI_CONFIG_CANDIDATES = [
        Path.home() / ".config/NapCat/config/webui.json",
    ]
    _QRCODE_IMAGE_CANDIDATES = [
        Path.home() / ".config/NapCat/cache/qrcode.png",
    ]


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() not in ("false", "0", "no", "")
    if isinstance(value, (int, float)):
        return value != 0
    return value is not None


# ─── WebUI 工具函数 ───

def _load_webui_config() -> dict:
    for p in _WEBUI_CONFIG_CANDIDATES:
        try:
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
    return {}


def _get_webui_base(config: dict | None = None) -> str:
    if config is None:
        config = _load_webui_config()
    host = (config.get("host") or "").strip().strip("[]")
    if host in ("", "::", "0.0.0.0", "::0"):
        host = "127.0.0.1"
    port = 6099
    try:
        port = int(config.get("port", 6099))
    except (ValueError, TypeError):
        pass
    return f"http://{host}:{port}"


async def _check_webui_reachable(base_url: str | None = None) -> bool:
    if base_url is None:
        base_url = _get_webui_base()
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            resp = await client.post(f"{base_url}/api/auth/login", json={})
            if resp.status_code == 200:
                data = resp.json()
                return isinstance(data, dict) and "code" in data
    except Exception:
        pass
    return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(f"{token}.napcat".encode("utf-8")).hexdigest()


async def _get_credential(
    client: httpx.AsyncClient, base_url: str, token: str
) -> tuple[str | None, str]:
    if not token:
        return None, "NapCat WebUI 未配置 token，请检查 webui.json"
    try:
        resp = await client.post(
            f"{base_url}/api/auth/login",
            json={"hash": _token_hash(token)},
        )
        if resp.status_code != 200:
            return None, f"NapCat WebUI 认证失败（HTTP {resp.status_code}）"
        data = resp.json()
        if data.get("code") == 0:
            credential = (data.get("data") or {}).get("Credential")
            if credential:
                return str(credential), ""
            return None, "NapCat WebUI 认证返回为空"
        return None, f"NapCat WebUI 认证失败: {data.get('message', '未知错误')}"
    except Exception as e:
        return None, f"NapCat WebUI 认证异常: {e}"


async def _napcat_api(
    client: httpx.AsyncClient, base_url: str, path: str, credential: str,
) -> dict:
    try:
        resp = await client.post(
            f"{base_url}{path}", json={},
            headers={"Authorization": f"Bearer {credential}"},
        )
        if resp.status_code != 200:
            return {"code": -1, "message": f"HTTP {resp.status_code}"}
        data = resp.json()
        return data if isinstance(data, dict) else {"code": -1, "message": "返回格式异常"}
    except Exception as e:
        return {"code": -1, "message": str(e)}


def _find_qrcode_image() -> Path | None:
    files: list[Path] = []
    for p in _QRCODE_IMAGE_CANDIDATES:
        try:
            if p.exists() and p.is_file() and p.stat().st_size > 0:
                files.append(p)
        except Exception:
            continue
    if not files:
        return None
    return max(files, key=lambda x: x.stat().st_mtime)


def _build_qrcode_payload(qrcode_url: str = "", message: str = "") -> dict:
    payload: dict = {"ok": True}
    if qrcode_url:
        payload["qrcode_url"] = qrcode_url
    p = _find_qrcode_image()
    if p:
        try:
            ts = int(p.stat().st_mtime)
        except Exception:
            ts = 0
        payload["qrcode_image_api"] = f"/api/napcat/qrcode_image?ts={ts}"
    if message:
        payload["message"] = message
    return payload


# ─── 进程管理（精确匹配 _active_exe，不误杀其他 QQ） ───

def _get_qq_pids() -> list[int]:
    if not _active_exe:
        return []
    try:
        if _IS_WIN:
            result = subprocess.run(
                ["wmic", "process", "where",
                 f"ExecutablePath='{_active_exe.replace(chr(92), chr(92)*2)}'",
                 "get", "ProcessId", "/format:list"],
                capture_output=True, text=True, timeout=5,
            )
            return [int(x.split("=")[1]) for x in result.stdout.strip().splitlines()
                    if x.startswith("ProcessId=")]
        else:
            result = subprocess.run(
                ["pgrep", "-f", _active_exe],
                capture_output=True, text=True, timeout=3,
            )
            return [int(p) for p in result.stdout.strip().split("\n") if p.strip()]
    except Exception:
        return []


def _is_qq_running() -> bool:
    return len(_get_qq_pids()) > 0


def _kill_qq() -> None:
    pids = _get_qq_pids()
    for pid in pids:
        try:
            if _IS_WIN:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                               capture_output=True, timeout=5)
            else:
                subprocess.run(["kill", str(pid)], capture_output=True, timeout=3)
        except Exception:
            pass


def _force_kill_qq() -> None:
    pids = _get_qq_pids()
    for pid in pids:
        try:
            if _IS_WIN:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                               capture_output=True, timeout=5)
            else:
                subprocess.run(["kill", "-9", str(pid)], capture_output=True, timeout=3)
        except Exception:
            pass


async def _ensure_qq_killed() -> bool:
    _kill_qq()
    for _ in range(5):
        await asyncio.sleep(2)
        if not _is_qq_running():
            return True
    _force_kill_qq()
    await asyncio.sleep(1)
    return not _is_qq_running()


# ─── API 路由 ───

@router.get("/status")
async def napcat_status():
    """获取连接状态（前端轮询）"""
    config = _load_webui_config()
    base_url = _get_webui_base(config)
    webui_reachable = await _check_webui_reachable(base_url)

    qq_login = False
    login_error = ""

    if webui_reachable:
        token = str(config.get("token", "") or "")
        if token:
            async with httpx.AsyncClient(timeout=5) as client:
                credential, _ = await _get_credential(client, base_url, token)
                if credential:
                    resp = await _napcat_api(
                        client, base_url,
                        "/api/QQLogin/CheckLoginStatus", credential,
                    )
                    if resp.get("code") == 0:
                        d = resp.get("data") or {}
                        qq_login = _parse_bool(d.get("isLogin"))
                        login_error = str(d.get("loginError") or "")

    # 综合状态: 已连接 = WebUI 可达 + QQ 已登录
    connected = webui_reachable and qq_login

    return {
        "connected": connected,
        "webui_reachable": webui_reachable,
        "qq_login": qq_login,
        "qq_running": _is_qq_running(),
        "login_error": login_error,
        "active_exe": _active_exe,
        "apps": _napcat_apps,
        "mode": "single" if len(_napcat_apps) <= 1 else "multi",
    }


class SetAppRequest(BaseModel):
    exe: str


@router.post("/set-app")
async def set_active_app(body: SetAppRequest):
    """多 App 模式下切换目标 QQ（仅在未连接时允许）"""
    global _active_exe  # noqa: PLW0603
    exe = body.exe.strip()
    if not exe:
        return {"ok": False, "message": "请选择一个 QQ 应用"}

    # 校验是否在已检测列表中
    valid = any(a["exe"] == exe for a in _napcat_apps)
    if not valid:
        return {"ok": False, "message": f"无效的 QQ 路径: {exe}"}

    if _is_qq_running() or await _check_webui_reachable():
        return {"ok": False, "message": "请先断开当前连接再切换"}

    _active_exe = exe
    return {"ok": True, "message": f"已切换到: {exe}"}


@router.post("/connect")
async def connect_napcat():
    """一键连接：启动 QQ → 等待 WebUI → 获取二维码"""
    if not _active_exe:
        return {
            "ok": False,
            "message": "未检测到已配置 NapCat 的 QQ 应用，请先安装 NapCat",
        }

    base_url = _get_webui_base()

    # 已连接则直接返回
    if await _check_webui_reachable(base_url):
        # 检查是否已登录
        config = _load_webui_config()
        token = str(config.get("token", "") or "")
        if token:
            async with httpx.AsyncClient(timeout=5) as client:
                credential, _ = await _get_credential(client, base_url, token)
                if credential:
                    resp = await _napcat_api(
                        client, base_url,
                        "/api/QQLogin/CheckLoginStatus", credential,
                    )
                    if resp.get("code") == 0:
                        d = resp.get("data") or {}
                        if _parse_bool(d.get("isLogin")):
                            return {"ok": True, "message": "QQ 已连接并登录"}
        # WebUI 在但未登录，直接返回二维码
        return await _fetch_qrcode_result()

    # 确认 NapCat 已配置
    pkg = None
    for a in _napcat_apps:
        if a["exe"] == _active_exe:
            pkg = Path(a["package_json"])
            break
    if not pkg or not _check_napcat_mode(pkg):
        return {
            "ok": False,
            "message": f"目标 QQ 未配置 NapCat 模式，请先安装 NapCat\n检测路径: {_active_exe}",
        }

    # 杀掉已有进程
    if _is_qq_running():
        killed = await _ensure_qq_killed()
        if not killed:
            return {
                "ok": False,
                "message": f"无法关闭目标 QQ 进程，请手动退出后重试\n进程路径: {_active_exe}",
            }

    # 启动 QQ
    try:
        subprocess.Popen(
            [_active_exe, "--no-sandbox"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return {"ok": False, "message": f"QQ 可执行文件未找到: {_active_exe}"}
    except PermissionError:
        return {"ok": False, "message": f"没有权限启动 QQ: {_active_exe}"}
    except Exception as e:
        return {"ok": False, "message": f"启动 QQ 失败: {e}"}

    # 等待 WebUI 就绪（最多 40 秒）
    for _ in range(20):
        await asyncio.sleep(2)
        if await _check_webui_reachable(base_url):
            # WebUI 就绪，获取二维码
            return await _fetch_qrcode_result()

    if _is_qq_running():
        return {
            "ok": False,
            "message": "QQ 已启动但 NapCat WebUI 未就绪，可能 NapCat 未正确安装，请检查配置后重试",
        }
    return {
        "ok": False,
        "message": f"启动超时，QQ 进程未检测到\n可执行路径: {_active_exe}",
    }


async def _fetch_qrcode_result() -> dict:
    """内部: 获取二维码并返回给前端"""
    config = _load_webui_config()
    base_url = _get_webui_base(config)
    token = str(config.get("token", "") or "")

    async with httpx.AsyncClient(timeout=8) as client:
        credential, err = await _get_credential(client, base_url, token)
        if not credential:
            return {"ok": False, "message": err}

        # 检查是否已登录
        status_resp = await _napcat_api(
            client, base_url, "/api/QQLogin/CheckLoginStatus", credential,
        )
        if status_resp.get("code") == 0:
            d = status_resp.get("data") or {}
            if _parse_bool(d.get("isLogin")):
                return {"ok": True, "is_login": True, "message": "QQ 已登录"}
            qrcode_url = str(d.get("qrcodeurl") or "")
            if qrcode_url:
                return _build_qrcode_payload(qrcode_url, "请使用手机 QQ 扫码登录")

        # 主动获取二维码
        qr_resp = await _napcat_api(
            client, base_url, "/api/QQLogin/GetQQLoginQrcode", credential,
        )
        if qr_resp.get("code") == 0:
            qrcode_url = str((qr_resp.get("data") or {}).get("qrcode") or "")
            if qrcode_url:
                return _build_qrcode_payload(qrcode_url, "请使用手机 QQ 扫码登录")
            return {"ok": False, "message": "NapCat 未返回二维码数据，请稍后重试"}

        # 刷新并重试
        await _napcat_api(client, base_url, "/api/QQLogin/RefreshQRcode", credential)
        for _ in range(6):
            await asyncio.sleep(1)
            retry = await _napcat_api(
                client, base_url, "/api/QQLogin/CheckLoginStatus", credential,
            )
            if retry.get("code") != 0:
                continue
            rd = retry.get("data") or {}
            if _parse_bool(rd.get("isLogin")):
                return {"ok": True, "is_login": True, "message": "QQ 已登录"}
            qrcode_url = str(rd.get("qrcodeurl") or "")
            if qrcode_url:
                return _build_qrcode_payload(qrcode_url, "请使用手机 QQ 扫码登录")

        local_payload = _build_qrcode_payload(message="请扫描下方二维码登录")
        if local_payload.get("qrcode_image_api"):
            return local_payload

        return {"ok": False, "message": qr_resp.get("message", "获取二维码失败，请稍后重试")}


@router.post("/disconnect")
async def disconnect_napcat():
    """断开连接：停止 QQ 进程"""
    if not _is_qq_running() and not await _check_webui_reachable():
        return {"ok": True, "message": "当前未连接"}

    killed = await _ensure_qq_killed()
    if not killed:
        return {"ok": False, "message": f"无法关闭 QQ 进程，请手动退出\n进程路径: {_active_exe}"}

    return {"ok": True, "message": "已断开连接"}


@router.get("/qrcode")
async def proxy_qrcode():
    """获取二维码（供前端刷新使用）"""
    if not await _check_webui_reachable():
        return {"ok": False, "message": "QQ 消息代理未运行，请先点击连接"}
    return await _fetch_qrcode_result()


@router.get("/qrcode_image")
async def get_qrcode_image():
    p = _find_qrcode_image()
    if not p:
        return {"ok": False, "message": "二维码图片不存在，请先点击连接"}
    return FileResponse(str(p), media_type="image/png", filename="qrcode.png")
