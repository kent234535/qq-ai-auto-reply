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

# NapCat loader 路径（由 NapCat 安装器写入）
_NAPCAT_LOADER_CANDIDATES: list[Path]
if _IS_MAC:
    _NAPCAT_LOADER_CANDIDATES = [
        Path.home() / "Library/Containers/com.tencent.qq/Data/Documents/loadNapCat.js",
        Path.home() / "Library/Application Support/QQ/loadNapCat.js",
    ]
elif _IS_WIN:
    _NAPCAT_LOADER_CANDIDATES = [
        Path.home() / "Documents/loadNapCat.js",
        Path.home() / "AppData/Local/NapCat/loadNapCat.js",
    ]
else:
    _NAPCAT_LOADER_CANDIDATES = [
        Path.home() / ".config/NapCat/loadNapCat.js",
    ]


def _find_napcat_loader() -> Path | None:
    """查找 NapCat loader 脚本"""
    for p in _NAPCAT_LOADER_CANDIDATES:
        if p.exists():
            return p
    return None


def _app_exe(app_dir: str) -> str:
    if _IS_MAC:
        return f"{app_dir}/Contents/MacOS/QQ"
    elif _IS_WIN:
        return f"{app_dir}\\QQ.exe"
    return f"{app_dir}/qq"


def _app_pkg(app_dir: str) -> Path:
    if _IS_MAC:
        return Path(f"{app_dir}/Contents/Resources/app/package.json")
    elif _IS_WIN:
        return Path(f"{app_dir}\\resources\\app\\package.json")
    return Path(f"{app_dir}/resources/app/package.json")


def _check_napcat_mode(package_json: Path) -> bool:
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
        return "napcat" in data.get("main", "").lower()
    except Exception:
        return False


def _detect_all_qq_apps() -> list[dict]:
    """扫描本机所有 QQ 应用，返回列表。"""
    apps: list[dict] = []
    if _IS_MAC:
        for app_path in sorted(_glob.glob("/Applications/QQ*.app")):
            name = Path(app_path).name
            if "Browser" in name:
                continue
            pkg = _app_pkg(app_path)
            if pkg.exists():
                apps.append({
                    "app_dir": app_path,
                    "exe": _app_exe(app_path),
                    "package_json": str(pkg),
                    "name": name,
                })
    elif _IS_WIN:
        for d in [r"C:\Program Files\Tencent\QQNT"]:
            pkg = _app_pkg(d)
            if pkg.exists():
                apps.append({
                    "app_dir": d,
                    "exe": _app_exe(d),
                    "package_json": str(pkg),
                    "name": Path(d).name,
                })
    else:
        for d in ["/opt/QQ"]:
            pkg = _app_pkg(d)
            if pkg.exists():
                apps.append({
                    "app_dir": d,
                    "exe": _app_exe(d),
                    "package_json": str(pkg),
                    "name": Path(d).name,
                })
    return apps


_all_qq_apps = _detect_all_qq_apps()
_active_exe: str = _all_qq_apps[0]["exe"] if _all_qq_apps else ""
# 记住被修改过的 package.json 的原始 main 值，断开时恢复
_original_main: dict[str, str] = {}
# NoneBot2 的 WebSocket 地址（NapCat 需要连接到这里）
_NONEBOT_WS = "ws://127.0.0.1:8080/onebot/v11/ws"

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


# ─── NapCat OneBot11 配置自动修复 ───

_NAPCAT_CONFIG_DIRS: list[Path] = []
if _IS_MAC:
    _NAPCAT_CONFIG_DIRS = [
        Path.home() / "Library/Application Support/QQ/NapCat/config",
        Path.home() / "Library/Containers/com.tencent.qq/Data/Library/Application Support/QQ/NapCat/config",
    ]
elif _IS_WIN:
    _NAPCAT_CONFIG_DIRS = [
        Path.home() / "AppData/Local/NapCat/config",
        Path.home() / "AppData/Roaming/NapCat/config",
    ]
else:
    _NAPCAT_CONFIG_DIRS = [
        Path.home() / ".config/NapCat/config",
    ]


def _ensure_onebot11_config() -> str:
    """检查所有 NapCat onebot11 配置文件，确保 WebSocket 客户端指向 NoneBot2。
    返回修复信息（空字符串表示无需修复）。"""
    fixed: list[str] = []
    for config_dir in _NAPCAT_CONFIG_DIRS:
        if not config_dir.exists():
            continue
        for f in config_dir.glob("onebot11_*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            network = data.get("network", {})
            ws_clients = network.get("websocketClients", [])

            # 检查是否已有指向 NoneBot2 的配置
            has_nonebot = any(
                c.get("url") == _NONEBOT_WS and c.get("enable")
                for c in ws_clients
            )
            if has_nonebot:
                continue

            # 添加 WebSocket 客户端配置
            ws_clients.append({
                "enable": True,
                "url": _NONEBOT_WS,
                "reconnectIntervalMs": 5000,
                "heartIntervalMs": 30000,
                "accessToken": "",
            })
            network["websocketClients"] = ws_clients
            data["network"] = network
            try:
                f.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                qq_num = f.stem.replace("onebot11_", "")
                fixed.append(qq_num)
            except Exception:
                pass
    return f"已为账号 {', '.join(fixed)} 配置消息转发" if fixed else ""


# ─── NapCat 模式切换（修改 package.json 的 main 字段） ───

def _calc_napcat_main(package_json: Path, loader: Path) -> str:
    """计算从 package.json 所在目录到 NapCat loader 的相对路径"""
    try:
        return str(loader.resolve().relative_to(package_json.parent.resolve()))
    except ValueError:
        # 不在同一棵树下，用 ../ 相对路径
        pkg_parts = package_json.parent.resolve().parts
        loader_parts = loader.resolve().parts
        # 找公共前缀
        common = 0
        for a, b in zip(pkg_parts, loader_parts):
            if a == b:
                common += 1
            else:
                break
        ups = len(pkg_parts) - common
        remainder = loader_parts[common:]
        return "/".join([".."] * ups + list(remainder))


def _enable_napcat(pkg_path: Path) -> tuple[bool, str]:
    """将目标 QQ 的 package.json 切换到 NapCat 模式，返回 (成功, 消息)"""
    loader = _find_napcat_loader()
    if not loader:
        return False, "未找到 NapCat loader 脚本（loadNapCat.js），请先安装 NapCat"

    try:
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"读取 package.json 失败: {e}"

    current_main = data.get("main", "")
    if "napcat" in current_main.lower():
        return True, "已处于 NapCat 模式"

    # 保存原始 main
    _original_main[str(pkg_path)] = current_main

    # 替换 main
    napcat_main = _calc_napcat_main(pkg_path, loader)
    data["main"] = napcat_main
    try:
        pkg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except PermissionError:
        return False, f"没有权限修改 {pkg_path}，请检查文件权限"
    except Exception as e:
        return False, f"写入 package.json 失败: {e}"

    # macOS 需要重新签名
    if _IS_MAC:
        app_dir = str(pkg_path).split("/Contents/")[0]
        _codesign(app_dir)

    return True, "已切换到 NapCat 模式"


def _disable_napcat(pkg_path: Path) -> tuple[bool, str]:
    """将目标 QQ 的 package.json 恢复为正常模式"""
    key = str(pkg_path)
    original = _original_main.pop(key, None)

    try:
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"读取 package.json 失败: {e}"

    current_main = data.get("main", "")
    if "napcat" not in current_main.lower():
        return True, "已处于正常模式"

    if not original:
        # 没有备份，使用默认值
        original = "./app_launcher/index.js"

    data["main"] = original
    try:
        pkg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        return False, f"恢复 package.json 失败: {e}"

    if _IS_MAC:
        app_dir = str(pkg_path).split("/Contents/")[0]
        _codesign(app_dir)

    return True, "已恢复正常模式"


def _codesign(app_dir: str) -> None:
    """macOS: 重新签名 + 清除扩展属性"""
    if not _IS_MAC:
        return
    try:
        subprocess.run(
            ["codesign", "--force", "--deep", "--sign", "-", app_dir],
            capture_output=True, timeout=30,
        )
        subprocess.run(
            ["xattr", "-cr", app_dir],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass


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


# ─── 进程管理（精确匹配 _active_exe） ───

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
    for pid in _get_qq_pids():
        try:
            if _IS_WIN:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                               capture_output=True, timeout=5)
            else:
                subprocess.run(["kill", str(pid)], capture_output=True, timeout=3)
        except Exception:
            pass


def _force_kill_qq() -> None:
    for pid in _get_qq_pids():
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


def _get_active_pkg() -> Path | None:
    """获取当前选中 QQ 的 package.json 路径"""
    for a in _all_qq_apps:
        if a["exe"] == _active_exe:
            return Path(a["package_json"])
    return None


# ─── API 路由 ───

@router.get("/status")
async def napcat_status():
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

    connected = webui_reachable and qq_login

    # QQ 登录后自动确保 OneBot11 配置正确
    if qq_login:
        _ensure_onebot11_config()

    return {
        "connected": connected,
        "webui_reachable": webui_reachable,
        "qq_login": qq_login,
        "qq_running": _is_qq_running(),
        "login_error": login_error,
        "active_exe": _active_exe,
        "apps": _all_qq_apps,
        "napcat_installed": _find_napcat_loader() is not None,
    }


class SetAppRequest(BaseModel):
    exe: str


@router.post("/set-app")
async def set_active_app(body: SetAppRequest):
    global _active_exe  # noqa: PLW0603
    exe = body.exe.strip()
    if not exe:
        return {"ok": False, "message": "请选择一个 QQ 应用"}

    valid = any(a["exe"] == exe for a in _all_qq_apps)
    if not valid:
        return {"ok": False, "message": f"无效的 QQ 路径: {exe}"}

    # 如果当前有连接，自动断开再切换
    if _is_qq_running() or await _check_webui_reachable():
        # 恢复当前 App 的 package.json
        old_pkg = _get_active_pkg()
        if old_pkg:
            _disable_napcat(old_pkg)
        await _ensure_qq_killed()

    _active_exe = exe
    return {"ok": True, "message": f"已切换到: {exe}"}


@router.post("/connect")
async def connect_napcat():
    """一键连接：配置 NapCat → 启动 QQ → 等待 WebUI → 获取二维码"""
    if not _active_exe:
        return {"ok": False, "message": "未检测到 QQ 应用，请先安装 QQ"}

    base_url = _get_webui_base()

    # 已连接则直接返回
    if await _check_webui_reachable(base_url):
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
        return await _fetch_qrcode_result()

    # 杀掉已有进程
    if _is_qq_running():
        killed = await _ensure_qq_killed()
        if not killed:
            return {
                "ok": False,
                "message": f"无法关闭目标 QQ 进程，请手动退出后重试\n进程路径: {_active_exe}",
            }

    # 配置 NapCat 模式
    pkg = _get_active_pkg()
    if not pkg:
        return {"ok": False, "message": f"未找到 package.json: {_active_exe}"}

    ok, msg = _enable_napcat(pkg)
    if not ok:
        return {"ok": False, "message": msg}

    # 启动 QQ
    try:
        subprocess.Popen(
            [_active_exe, "--no-sandbox"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        _disable_napcat(pkg)
        return {"ok": False, "message": f"QQ 可执行文件未找到: {_active_exe}"}
    except PermissionError:
        _disable_napcat(pkg)
        return {"ok": False, "message": f"没有权限启动 QQ: {_active_exe}"}
    except Exception as e:
        _disable_napcat(pkg)
        return {"ok": False, "message": f"启动 QQ 失败: {e}"}

    # 等待 WebUI 就绪（最多 40 秒）
    for _ in range(20):
        await asyncio.sleep(2)
        if await _check_webui_reachable(base_url):
            # 确保 OneBot11 配置正确（自动为所有账号配置消息转发）
            _ensure_onebot11_config()
            return await _fetch_qrcode_result()

    if _is_qq_running():
        return {
            "ok": False,
            "message": "QQ 已启动但 NapCat WebUI 未就绪，可能 NapCat 未正确安装，请检查配置后重试",
        }
    _disable_napcat(pkg)
    return {
        "ok": False,
        "message": f"启动超时，QQ 进程未检测到\n可执行路径: {_active_exe}",
    }


async def _fetch_qrcode_result() -> dict:
    config = _load_webui_config()
    base_url = _get_webui_base(config)
    token = str(config.get("token", "") or "")

    async with httpx.AsyncClient(timeout=8) as client:
        credential, err = await _get_credential(client, base_url, token)
        if not credential:
            return {"ok": False, "message": err}

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

        qr_resp = await _napcat_api(
            client, base_url, "/api/QQLogin/GetQQLoginQrcode", credential,
        )
        if qr_resp.get("code") == 0:
            qrcode_url = str((qr_resp.get("data") or {}).get("qrcode") or "")
            if qrcode_url:
                return _build_qrcode_payload(qrcode_url, "请使用手机 QQ 扫码登录")
            return {"ok": False, "message": "NapCat 未返回二维码数据，请稍后重试"}

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
    """断开连接：停止 QQ → 恢复 package.json"""
    if not _is_qq_running() and not await _check_webui_reachable():
        # 即使未连接也尝试恢复，确保不残留 NapCat 配置
        pkg = _get_active_pkg()
        if pkg:
            _disable_napcat(pkg)
        return {"ok": True, "message": "当前未连接"}

    killed = await _ensure_qq_killed()
    if not killed:
        return {"ok": False, "message": f"无法关闭 QQ 进程，请手动退出\n进程路径: {_active_exe}"}

    # 恢复 package.json
    pkg = _get_active_pkg()
    if pkg:
        ok, msg = _disable_napcat(pkg)
        if not ok:
            return {"ok": False, "message": f"已断开连接，但恢复配置失败: {msg}"}

    return {"ok": True, "message": "已断开连接"}


@router.get("/qrcode")
async def proxy_qrcode():
    if not await _check_webui_reachable():
        return {"ok": False, "message": "QQ 消息代理未运行，请先点击连接"}
    return await _fetch_qrcode_result()


@router.get("/qrcode_image")
async def get_qrcode_image():
    p = _find_qrcode_image()
    if not p:
        return {"ok": False, "message": "二维码图片不存在，请先点击连接"}
    return FileResponse(str(p), media_type="image/png", filename="qrcode.png")
