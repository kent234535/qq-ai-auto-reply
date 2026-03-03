"""NapCat 启停 / 二维码代理 API"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

import httpx

router = APIRouter()

# ─── 平台常量 ───

_IS_WIN = sys.platform == "win32"
_IS_MAC = sys.platform == "darwin"

if _IS_WIN:
    _QQ_INSTALL_DIR = Path(r"C:\Program Files\Tencent\QQNT")
    QQ_APP_PATH = str(_QQ_INSTALL_DIR / "QQ.exe")
    QQ_PACKAGE_JSON = _QQ_INSTALL_DIR / "resources" / "app" / "package.json"
    _QQ_EXE_NAME = "QQ.exe"
    _WEBUI_CONFIG_CANDIDATES = [
        Path.home() / "AppData/Local/NapCat/config/webui.json",
        Path.home() / "AppData/Roaming/NapCat/config/webui.json",
    ]
    _QRCODE_IMAGE_CANDIDATES = [
        Path.home() / "AppData/Local/NapCat/cache/qrcode.png",
        Path.home() / "AppData/Roaming/NapCat/cache/qrcode.png",
    ]
elif _IS_MAC:
    QQ_APP_PATH = "/Applications/QQ.app/Contents/MacOS/QQ"
    QQ_PACKAGE_JSON = Path("/Applications/QQ.app/Contents/Resources/app/package.json")
    _QQ_EXE_NAME = ""  # macOS 用路径匹配
    _WEBUI_CONFIG_CANDIDATES = [
        Path.home() / "Library/Application Support/QQ/NapCat/config/webui.json",
        Path.home() / "Library/Containers/com.tencent.qq/Data/Library/Application Support/QQ/NapCat/config/webui.json",
    ]
    _QRCODE_IMAGE_CANDIDATES = [
        Path.home() / "Library/Application Support/QQ/NapCat/cache/qrcode.png",
        Path.home() / "Library/Containers/com.tencent.qq/Data/Library/Application Support/QQ/NapCat/cache/qrcode.png",
    ]
else:
    QQ_APP_PATH = "/opt/QQ/qq"
    QQ_PACKAGE_JSON = Path("/opt/QQ/resources/app/package.json")
    _QQ_EXE_NAME = ""
    _WEBUI_CONFIG_CANDIDATES = [
        Path.home() / ".config/NapCat/config/webui.json",
    ]
    _QRCODE_IMAGE_CANDIDATES = [
        Path.home() / ".config/NapCat/cache/qrcode.png",
    ]

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
NAPCAT_PACKAGE = PROJECT_DIR / "package.json.napcat"
ORIGINAL_PACKAGE = PROJECT_DIR / "package.json.original"


def _parse_bool(value: object) -> bool:
    """将上游可能返回的各种布尔值统一解析为 Python bool。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() not in ("false", "0", "no", "")
    if isinstance(value, (int, float)):
        return value != 0
    return value is not None


# ─── 工具函数 ───

def _is_napcat_mode() -> bool:
    """检查当前 QQ 的 package.json 是否已切换到 NapCat 模式"""
    try:
        data = json.loads(QQ_PACKAGE_JSON.read_text(encoding="utf-8"))
        return "napcat" in data.get("main", "").lower()
    except Exception:
        return False


def _switch_to_napcat() -> tuple[bool, str]:
    """切换 QQ 到 NapCat 模式"""
    if not NAPCAT_PACKAGE.exists():
        return False, f"NapCat package.json 不存在: {NAPCAT_PACKAGE}"
    try:
        shutil.copy2(NAPCAT_PACKAGE, QQ_PACKAGE_JSON)
        if _IS_MAC:
            errors = _codesign_and_xattr()
            if errors:
                return False, f"package.json 已替换，但签名失败: {errors}"
        return True, "已切换到 NapCat 模式"
    except Exception as e:
        return False, f"切换失败: {e}"


def _switch_to_normal() -> tuple[bool, str]:
    """切换 QQ 回普通模式"""
    if not ORIGINAL_PACKAGE.exists():
        return False, f"原版 package.json 不存在: {ORIGINAL_PACKAGE}"
    try:
        shutil.copy2(ORIGINAL_PACKAGE, QQ_PACKAGE_JSON)
        if _IS_MAC:
            errors = _codesign_and_xattr()
            if errors:
                return False, f"package.json 已恢复，但签名失败: {errors}"
        return True, "已切换回普通模式"
    except Exception as e:
        return False, f"切换失败: {e}"


def _codesign_and_xattr() -> str:
    """macOS: 执行 codesign + xattr"""
    if not _IS_MAC:
        return ""
    errors = []
    r1 = subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", "/Applications/QQ.app"],
        capture_output=True, text=True, timeout=30,
    )
    if r1.returncode != 0:
        errors.append(f"codesign 退出码 {r1.returncode}: {r1.stderr.strip()}")
    r2 = subprocess.run(
        ["xattr", "-cr", "/Applications/QQ.app"],
        capture_output=True, text=True, timeout=10,
    )
    if r2.returncode != 0:
        errors.append(f"xattr 退出码 {r2.returncode}: {r2.stderr.strip()}")
    return "; ".join(errors)


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
        return None, "webui.json 中未配置 token"
    try:
        resp = await client.post(
            f"{base_url}/api/auth/login",
            json={"hash": _token_hash(token)},
        )
        if resp.status_code != 200:
            return None, f"认证失败: HTTP {resp.status_code}"
        data = resp.json()
        if data.get("code") == 0:
            credential = (data.get("data") or {}).get("Credential")
            if credential:
                return str(credential), ""
            return None, "认证返回为空"
        return None, f"认证失败: {data.get('message', '未知错误')}"
    except Exception as e:
        return None, f"认证异常: {e}"


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
        return data if isinstance(data, dict) else {"code": -1, "message": "格式异常"}
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


# ─── 进程管理（精确匹配 QQ_APP_PATH，不误杀其他进程） ───

def _get_qq_pids() -> list[int]:
    """获取由 QQ_APP_PATH 启动的进程 PID 列表（精确匹配，不误杀其他 QQ）"""
    try:
        if _IS_WIN:
            # wmic 精确匹配可执行路径
            result = subprocess.run(
                ["wmic", "process", "where",
                 f"name='{_QQ_EXE_NAME}'",
                 "get", "ProcessId", "/format:list"],
                capture_output=True, text=True, timeout=5,
            )
            return [int(x.split("=")[1]) for x in result.stdout.strip().splitlines()
                    if x.startswith("ProcessId=")]
        else:
            # macOS/Linux: 用完整可执行路径精确匹配
            result = subprocess.run(
                ["pgrep", "-f", QQ_APP_PATH],
                capture_output=True, text=True, timeout=3,
            )
            return [int(p) for p in result.stdout.strip().split("\n") if p.strip()]
    except Exception:
        return []


def _is_qq_running() -> bool:
    """检查目标 QQ 是否在运行"""
    return len(_get_qq_pids()) > 0


def _kill_qq() -> None:
    """杀掉目标 QQ 进程（精确匹配）"""
    pids = _get_qq_pids()
    if not pids:
        return
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
    """强制杀掉目标 QQ 进程"""
    pids = _get_qq_pids()
    if not pids:
        return
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
    """确保目标 QQ 进程已退出，最多等 10 秒"""
    _kill_qq()
    for _ in range(5):
        await asyncio.sleep(2)
        if not _is_qq_running():
            return True
    _force_kill_qq()
    await asyncio.sleep(1)
    return not _is_qq_running()


# ─── API 路由 ───

class StartRequest(BaseModel):
    qq_account: str


@router.get("/status")
async def napcat_status():
    """获取消息代理状态"""
    napcat_mode = _is_napcat_mode()
    qq_running = _is_qq_running()

    config = _load_webui_config()
    base_url = _get_webui_base(config)
    webui_reachable = await _check_webui_reachable(base_url)

    token = str(config.get("token", "") or "")
    qq_login = None
    qq_offline = None
    login_error = ""

    if webui_reachable and token:
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
                    qq_offline = _parse_bool(d.get("isOffline"))
                    login_error = str(d.get("loginError") or "")

    return {
        "napcat_mode": napcat_mode,
        "qq_running": qq_running,
        "webui_reachable": webui_reachable,
        "qq_login": qq_login,
        "qq_offline": qq_offline,
        "login_error": login_error,
    }


@router.post("/start")
async def start_napcat(body: StartRequest):
    """启动 QQ 消息代理：杀目标 QQ → 切换模式 → 启动 → 等待 WebUI"""
    qq_account = body.qq_account.strip()
    if not qq_account:
        return {"ok": False, "message": "请填写 QQ 账号"}

    base_url = _get_webui_base()

    if await _check_webui_reachable(base_url):
        return {"ok": True, "message": "QQ 消息代理已在运行"}

    # Step 1: 杀掉目标 QQ 进程
    if _is_qq_running():
        killed = await _ensure_qq_killed()
        if not killed:
            return {"ok": False, "message": "无法关闭 QQ 进程，请手动退出后重试"}

    # Step 2: 切换到 NapCat 模式
    if not _is_napcat_mode():
        ok, msg = _switch_to_napcat()
        if not ok:
            return {"ok": False, "message": msg}

    # Step 3: 启动 QQ（不传 -q，不自动登录）
    try:
        subprocess.Popen(
            [QQ_APP_PATH, "--no-sandbox"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return {"ok": False, "message": f"QQ 未找到: {QQ_APP_PATH}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}

    # Step 4: 等待 WebUI 就绪（最多 40 秒）
    for _ in range(20):
        await asyncio.sleep(2)
        if await _check_webui_reachable(base_url):
            return {"ok": True, "message": "QQ 消息代理启动成功，请点击「登录 QQ」扫码登录"}

    if _is_qq_running():
        return {"ok": True, "message": "QQ 已启动，WebUI 尚未就绪（请稍后刷新）"}
    return {"ok": False, "message": "启动超时，QQ 进程未检测到"}


@router.post("/stop")
async def stop_napcat():
    """停止 QQ 消息代理"""
    if not _is_qq_running() and not await _check_webui_reachable():
        return {"ok": True, "message": "QQ 消息代理未在运行"}

    killed = await _ensure_qq_killed()
    if not killed:
        return {"ok": False, "message": "无法关闭 QQ 进程"}

    ok, msg = _switch_to_normal()
    return {"ok": ok, "message": f"QQ 消息代理已停止。{msg}"}


@router.get("/qrcode")
async def proxy_qrcode():
    """通过 NapCat WebUI API 获取 QQ 登录二维码"""
    config = _load_webui_config()
    base_url = _get_webui_base(config)

    if not await _check_webui_reachable(base_url):
        return {"ok": False, "message": "请先启动 QQ 消息代理"}

    token = str(config.get("token", "") or "")
    async with httpx.AsyncClient(timeout=8) as client:
        credential, err = await _get_credential(client, base_url, token)
        if not credential:
            return {"ok": False, "message": err}

        # 先检查登录状态
        status_resp = await _napcat_api(
            client, base_url, "/api/QQLogin/CheckLoginStatus", credential,
        )
        if status_resp.get("code") == 0:
            d = status_resp.get("data") or {}
            if _parse_bool(d.get("isLogin")):
                return {"ok": True, "is_login": True, "message": "QQ 已登录"}
            qrcode_url = str(d.get("qrcodeurl") or "")
            if qrcode_url:
                return _build_qrcode_payload(qrcode_url)

        # 主动获取二维码
        qr_resp = await _napcat_api(
            client, base_url, "/api/QQLogin/GetQQLoginQrcode", credential,
        )
        if qr_resp.get("code") == 0:
            qrcode_url = str((qr_resp.get("data") or {}).get("qrcode") or "")
            if qrcode_url:
                return _build_qrcode_payload(qrcode_url)
            return {"ok": False, "message": "NapCat 未返回二维码，请稍后重试"}

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
                return _build_qrcode_payload(qrcode_url)

        local_payload = _build_qrcode_payload(message="二维码已刷新，请扫描下方图片")
        if local_payload.get("qrcode_image_api"):
            return local_payload

        return {"ok": False, "message": qr_resp.get("message", "获取二维码失败")}


@router.get("/qrcode_image")
async def get_qrcode_image():
    p = _find_qrcode_image()
    if not p:
        return {"ok": False, "message": "二维码图片不存在，请先点击登录 QQ"}
    return FileResponse(str(p), media_type="image/png", filename="qrcode.png")
