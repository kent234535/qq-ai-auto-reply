"""NapCat 启停 / 二维码代理 API"""

from __future__ import annotations

import asyncio
import glob as _glob
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

import httpx

router = APIRouter()


def _get_nonebot_ws() -> str:
    """从环境变量 / .env 读取 HOST 和 PORT，动态拼接 NoneBot2 WS 地址"""
    host = os.environ.get("HOST", "127.0.0.1") or "127.0.0.1"
    port = os.environ.get("PORT", "8080") or "8080"
    # 0.0.0.0 / :: 监听全接口时，NapCat 仍连 localhost
    if host in ("0.0.0.0", "::", "::0"):
        host = "127.0.0.1"
    return f"ws://{host}:{port}/onebot/v11/ws"

# ─── 平台检测 ───

_IS_WIN = sys.platform == "win32"
_IS_MAC = sys.platform == "darwin"

# NapCat loader 路径（由 NapCat 安装器写入）
_NAPCAT_LOADER_CANDIDATES: list[Path]
if _IS_MAC:
    _NAPCAT_LOADER_CANDIDATES = [
        Path.home() / "Library/Containers/com.tencent.qq/Data/Documents/loadNapCat.js",
        Path.home() / "Library/Application Support/QQ/loadNapCat.js",
        Path.home() / "Library/Application Support/NapCat/loadNapCat.js",
        Path("/opt/NapCat/loadNapCat.js"),
        Path("/usr/local/share/NapCat/loadNapCat.js"),
    ]
elif _IS_WIN:
    _NAPCAT_LOADER_CANDIDATES = [
        Path.home() / "Documents/loadNapCat.js",
        Path.home() / "AppData/Local/NapCat/loadNapCat.js",
        Path.home() / "AppData/Roaming/NapCat/loadNapCat.js",
        Path(os.path.expandvars(r"%ProgramFiles%\NapCat\loadNapCat.js")),
        Path(os.path.expandvars(r"%ProgramFiles(x86)%\NapCat\loadNapCat.js")),
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
    """返回 QQ 实际生效的 package.json 路径。
    QQ 有热更新机制，热更新后真正加载的代码在
    ~/Library/Application Support/QQ/versions/<ver>/QQUpdate.app/ 下，
    需要修改那里的 package.json 才能让 NapCat 生效。"""
    if _IS_MAC:
        hot = _find_hot_update_pkg()
        if hot:
            return hot
        return Path(f"{app_dir}/Contents/Resources/app/package.json")
    elif _IS_WIN:
        return Path(f"{app_dir}\\resources\\app\\package.json")
    return Path(f"{app_dir}/resources/app/package.json")


def _find_hot_update_pkg() -> Path | None:
    """macOS: 查找 QQ 热更新版本的 package.json"""
    if not _IS_MAC:
        return None
    versions_dir = Path.home() / "Library/Application Support/QQ/versions"
    config_file = versions_dir / "config.json"
    if not config_file.exists():
        return None
    try:
        config = json.loads(config_file.read_text(encoding="utf-8"))
        cur_version = config.get("curVersion", "")
        if not cur_version:
            return None
        hot_pkg = versions_dir / cur_version / "QQUpdate.app/Contents/Resources/app/package.json"
        if hot_pkg.exists():
            return hot_pkg
    except Exception:
        pass
    return None


def _check_napcat_mode(package_json: Path) -> bool:
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
        return "napcat" in data.get("main", "").lower()
    except Exception:
        return False


def _detect_qq_from_registry() -> list[str]:
    """Windows: 从注册表 Uninstall 项中查找 QQ 安装路径"""
    if not _IS_WIN:
        return []
    dirs: list[str] = []
    try:
        import winreg
        for root_key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for sub in (
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
            ):
                try:
                    key = winreg.OpenKey(root_key, sub)
                except OSError:
                    continue
                try:
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            i += 1
                        except OSError:
                            break
                        if "QQ" not in subkey_name.upper():
                            continue
                        try:
                            sk = winreg.OpenKey(key, subkey_name)
                            loc, _ = winreg.QueryValueEx(sk, "InstallLocation")
                            winreg.CloseKey(sk)
                            if loc and os.path.isdir(loc):
                                dirs.append(loc)
                        except OSError:
                            pass
                finally:
                    winreg.CloseKey(key)
    except Exception:
        pass
    return dirs


def _detect_all_qq_apps() -> list[dict]:
    """扫描本机所有 QQ 应用，返回列表。"""
    apps: list[dict] = []
    if _IS_MAC:
        # 扫描系统级和用户级应用目录
        _mac_dirs = ["/Applications", str(Path.home() / "Applications")]
        for base_dir in _mac_dirs:
            for app_path in sorted(_glob.glob(f"{base_dir}/QQ*.app")):
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
        _WIN_QQ_DIRS = [
            r"C:\Program Files\Tencent\QQNT",
            r"C:\Program Files (x86)\Tencent\QQNT",
            r"D:\Program Files\Tencent\QQNT",
            r"D:\Program Files (x86)\Tencent\QQNT",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tencent\QQNT"),
            os.path.expandvars(r"%LOCALAPPDATA%\Tencent\QQNT"),
        ]
        # 从 Windows 注册表探测 QQ 安装路径
        _WIN_QQ_DIRS.extend(_detect_qq_from_registry())
        seen: set[str] = set()
        for d in _WIN_QQ_DIRS:
            d = os.path.normpath(d)
            if d in seen:
                continue
            seen.add(d)
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


_active_exe: str = ""
# 记住被修改过的 package.json 的原始 main 值，断开时恢复
_ORIGINAL_MAIN_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "napcat_original_main.json"


def _load_original_main() -> dict[str, str]:
    """从磁盘加载 _original_main"""
    try:
        if _ORIGINAL_MAIN_FILE.exists():
            return json.loads(_ORIGINAL_MAIN_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_original_main() -> None:
    """将 _original_main 持久化到磁盘"""
    try:
        _ORIGINAL_MAIN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _ORIGINAL_MAIN_FILE.write_text(
            json.dumps(_original_main, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


_original_main: dict[str, str] = _load_original_main()

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


async def _enable_onebot11_ws_via_api() -> bool:
    """通过 NapCat WebUI API 动态配置 OneBot11 WebSocket 连接。
    NapCat 启动后不会重新读取配置文件，必须通过 API 设置才能立即生效。"""
    config = _load_webui_config()
    base_url = _get_webui_base(config)
    token = str(config.get("token", "") or "")
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            credential, err = await _get_credential(client, base_url, token)
            if not credential:
                return False

            # 先获取当前配置
            get_resp = await _napcat_api(client, base_url, "/api/OB11Config/GetConfig", credential)
            if get_resp.get("code") != 0:
                return False
            cfg = get_resp.get("data") or {}

            # 确保 WebSocket 客户端配置存在
            network = cfg.get("network", {})
            ws_clients = network.get("websocketClients", [])
            nonebot_ws = _get_nonebot_ws()
            has_nonebot = any(
                c.get("url") == nonebot_ws and c.get("enable")
                for c in ws_clients
            )
            if not has_nonebot:
                ws_clients.append({
                    "enable": True,
                    "url": nonebot_ws,
                    "reconnectIntervalMs": 5000,
                    "heartIntervalMs": 30000,
                    "accessToken": "",
                })
                network["websocketClients"] = ws_clients
                cfg["network"] = network

            # SetConfig 要求 {"config": "<JSON字符串>"}
            resp = await client.post(
                f"{base_url}/api/OB11Config/SetConfig",
                json={"config": json.dumps(cfg)},
                headers={"Authorization": f"Bearer {credential}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("code") == 0
    except Exception:
        pass
    return False


def _enable_onebot11_ws() -> str:
    """为所有 onebot11 配置写入 WebSocket 客户端，指向 NoneBot2。
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

            has_nonebot = any(
                c.get("url") == _get_nonebot_ws() and c.get("enable")
                for c in ws_clients
            )
            if has_nonebot:
                continue

            ws_clients.append({
                "enable": True,
                "url": _get_nonebot_ws(),
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


def _disable_onebot11_ws() -> None:
    """断开时只移除本项目注入的 WebSocket 客户端条目，保留用户原有配置。"""
    nonebot_ws = _get_nonebot_ws()
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
            if not ws_clients:
                continue
            filtered = [c for c in ws_clients if c.get("url") != nonebot_ws]
            if len(filtered) == len(ws_clients):
                continue  # 没有我们注入的条目，跳过
            network["websocketClients"] = filtered
            data["network"] = network
            try:
                f.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception:
                pass


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


def _patch_loader_for_app(loader: Path, app_dir: str) -> Path | None:
    """如果 loadNapCat.js 中硬编码了其他 QQ.app 路径，生成修正副本。
    返回修正后的 loader 路径；不需要修正则返回 None。"""
    if not _IS_MAC:
        return None
    try:
        content = loader.read_text(encoding="utf-8")
    except Exception:
        return None
    default_app = "/Applications/QQ.app"
    target_app = app_dir.rstrip("/")
    if target_app == default_app:
        return None
    if default_app not in content:
        return None
    patched_content = content.replace(default_app, target_app)
    data_dir = Path(__file__).resolve().parent.parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    app_name = Path(target_app).stem
    patched_path = data_dir / f"loadNapCat_{app_name}.js"
    try:
        patched_path.write_text(patched_content, encoding="utf-8")
        return patched_path
    except Exception:
        return None


def _enable_napcat(pkg_path: Path, qq_app_dir: str = "") -> tuple[bool, str]:
    """将目标 QQ 的 package.json 切换到 NapCat 模式，返回 (成功, 消息)。
    qq_app_dir: 实际 QQ app 路径（如 /Applications/QQ.app），用于 loader 路径修正。"""
    loader = _find_napcat_loader()
    if not loader:
        return False, "未找到 NapCat loader 脚本（loadNapCat.js），请先安装 NapCat"

    try:
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"读取 package.json 失败: {e}"

    # 为非默认 QQ 副本生成修正后的 loader
    actual_loader = loader
    if qq_app_dir:
        patched = _patch_loader_for_app(loader, qq_app_dir)
        if patched:
            actual_loader = patched

    current_main = data.get("main", "")
    napcat_main = _calc_napcat_main(pkg_path, actual_loader)

    if "napcat" in current_main.lower():
        # 已处于 NapCat 模式，但要确保 loader 指向正确
        if current_main != napcat_main:
            data["main"] = napcat_main
            try:
                pkg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
        return True, "已处于 NapCat 模式"

    # 保存原始 main
    _original_main[str(pkg_path)] = current_main
    _save_original_main()

    # 替换 main
    data["main"] = napcat_main
    try:
        pkg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except PermissionError:
        hint = "请以管理员身份运行" if _IS_WIN else "请检查文件权限"
        return False, f"没有权限修改 {pkg_path}，{hint}"
    except Exception as e:
        return False, f"写入 package.json 失败: {e}"

    return True, "已切换到 NapCat 模式"


def _disable_napcat(pkg_path: Path) -> tuple[bool, str]:
    """将目标 QQ 的 package.json 恢复为正常模式"""
    key = str(pkg_path)
    original = _original_main.pop(key, None)
    _save_original_main()

    try:
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"读取 package.json 失败: {e}"

    current_main = data.get("main", "")
    if "napcat" not in current_main.lower():
        return True, "已处于正常模式"

    if not original:
        # 没有备份，根据路径判断默认值
        if "QQUpdate.app" in str(pkg_path):
            original = "./application.asar/app_launcher/index.js"
        else:
            original = "./app_launcher/index.js"

    data["main"] = original
    try:
        pkg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        return False, f"恢复 package.json 失败: {e}"

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
        async with httpx.AsyncClient(timeout=4) as client:
            resp = await client.post(f"{base_url}/api/auth/login", json={})
            if resp.status_code == 200:
                data = resp.json()
                return isinstance(data, dict) and "code" in data
    except Exception:
        pass
    return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(f"{token}.napcat".encode("utf-8")).hexdigest()


# ─── Credential 缓存，避免每次轮询都重新认证 ───
_cached_credential: str = ""
_cached_credential_token: str = ""  # 对应的 token，token 变化时失效
_onebot11_ws_configured: bool = False  # 标记本次连接是否已配置过 OneBot11 WS


async def _get_credential(
    client: httpx.AsyncClient, base_url: str, token: str
) -> tuple[str | None, str]:
    global _cached_credential, _cached_credential_token  # noqa: PLW0603
    if not token:
        return None, "NapCat WebUI 未配置 token，请检查 webui.json"

    # 使用缓存的 credential（同一 token 下有效）
    if _cached_credential and _cached_credential_token == token:
        # 验证缓存是否仍然有效（轻量级请求）
        try:
            resp = await client.post(
                f"{base_url}/api/QQLogin/CheckLoginStatus",
                json={},
                headers={"Authorization": f"Bearer {_cached_credential}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return _cached_credential, ""
        except Exception:
            pass
        # 缓存失效，重新认证
        _cached_credential = ""

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
                _cached_credential = str(credential)
                _cached_credential_token = token
                return _cached_credential, ""
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
            # 优先 PowerShell Get-CimInstance（wmic 在新版 Windows 可能不可用）
            escaped = _active_exe.replace("\\", "\\\\").replace("'", "''")
            try:
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     f"Get-CimInstance Win32_Process -Filter \"ExecutablePath='{escaped}'\" "
                     "| Select-Object -ExpandProperty ProcessId"],
                    capture_output=True, text=True, timeout=5,
                )
                pids = [int(p) for p in result.stdout.strip().split() if p.strip().isdigit()]
                if pids or result.returncode == 0:
                    return pids
            except Exception:
                pass
            # fallback: wmic
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
    for a in _detect_all_qq_apps():
        if a["exe"] == _active_exe:
            return Path(a["package_json"])
    return None


# ─── API 路由 ───

@router.get("/status")
async def napcat_status():
    global _active_exe, _onebot11_ws_configured  # noqa: PLW0603

    apps = _detect_all_qq_apps()

    # 如果 _active_exe 尚未设置或已失效，自动选择第一个
    if not _active_exe or not any(a["exe"] == _active_exe for a in apps):
        _active_exe = apps[0]["exe"] if apps else ""

    config = _load_webui_config()
    base_url = _get_webui_base(config)
    token = str(config.get("token", "") or "")

    webui_reachable = False
    qq_login = False
    login_error = ""

    # 用一个 client 完成可达性检查 + 登录状态查询，减少连接开销
    if token:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                credential, _ = await _get_credential(client, base_url, token)
                if credential:
                    webui_reachable = True
                    resp = await _napcat_api(
                        client, base_url,
                        "/api/QQLogin/CheckLoginStatus", credential,
                    )
                    if resp.get("code") == 0:
                        d = resp.get("data") or {}
                        qq_login = _parse_bool(d.get("isLogin"))
                        login_error = str(d.get("loginError") or "")
        except Exception:
            pass
    else:
        webui_reachable = await _check_webui_reachable(base_url)

    connected = webui_reachable and qq_login

    # QQ 登录后仅首次自动配置 OneBot11 WS，避免每次轮询都发请求
    if qq_login and not _onebot11_ws_configured:
        if await _enable_onebot11_ws_via_api():
            _onebot11_ws_configured = True

    return {
        "connected": connected,
        "webui_reachable": webui_reachable,
        "qq_login": qq_login,
        "qq_running": _is_qq_running(),
        "login_error": login_error,
        "active_exe": _active_exe,
        "apps": apps,
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

    valid = any(a["exe"] == exe for a in _detect_all_qq_apps())
    if not valid:
        return {"ok": False, "message": f"无效的 QQ 路径: {exe}"}

    global _onebot11_ws_configured, _cached_credential  # noqa: PLW0603
    _onebot11_ws_configured = False
    _cached_credential = ""
    # 如果当前有连接，自动断开再切换
    if _is_qq_running() or await _check_webui_reachable():
        old_pkg = _get_active_pkg()
        if old_pkg:
            _disable_napcat(old_pkg)
        _disable_onebot11_ws()
        await _ensure_qq_killed()

    _active_exe = exe
    return {"ok": True, "message": f"已切换到: {exe}"}


@router.post("/connect")
async def connect_napcat():
    """一键连接：配置 NapCat → 启动 QQ → 等待 WebUI → 获取二维码"""
    global _onebot11_ws_configured, _cached_credential  # noqa: PLW0603
    _onebot11_ws_configured = False
    _cached_credential = ""
    if not _active_exe:
        return {"ok": False, "message": "未检测到 QQ 应用，请先安装 QQ"}

    # 已连接则直接返回
    base_url = _get_webui_base()
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

    # 获取实际 QQ app 目录（用于 loader 路径修正）
    qq_app_dir = ""
    for a in _detect_all_qq_apps():
        if a["exe"] == _active_exe:
            qq_app_dir = a["app_dir"]
            break

    ok, msg = _enable_napcat(pkg, qq_app_dir)
    if not ok:
        return {"ok": False, "message": msg}

    # 启动 QQ
    try:
        qq_cmd = [_active_exe]
        if not _IS_WIN:
            qq_cmd.append("--no-sandbox")
        subprocess.Popen(
            qq_cmd,
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
    # 每轮重新读取 webui.json，因为 NapCat 启动后可能才写入/更新配置
    for _ in range(20):
        await asyncio.sleep(2)
        cur_base = _get_webui_base()
        if await _check_webui_reachable(cur_base):
            # 通过 API 动态配置 OneBot11 WebSocket 连接
            await _enable_onebot11_ws_via_api()
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
    """断开连接：停止 QQ → 恢复 package.json → 清空 OneBot11 配置"""
    global _onebot11_ws_configured, _cached_credential  # noqa: PLW0603
    _onebot11_ws_configured = False
    _cached_credential = ""
    if not _is_qq_running() and not await _check_webui_reachable():
        # 即使未连接也尝试恢复，确保不残留配置
        pkg = _get_active_pkg()
        if pkg:
            _disable_napcat(pkg)
        _disable_onebot11_ws()
        return {"ok": True, "message": "当前未连接"}

    killed = await _ensure_qq_killed()
    if not killed:
        return {"ok": False, "message": f"无法关闭 QQ 进程，请手动退出\n进程路径: {_active_exe}"}

    # 恢复 package.json + 清空 OneBot11 配置
    pkg = _get_active_pkg()
    if pkg:
        ok, msg = _disable_napcat(pkg)
        if not ok:
            return {"ok": False, "message": f"已断开连接，但恢复配置失败: {msg}"}
    _disable_onebot11_ws()

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
