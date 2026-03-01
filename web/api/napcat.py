"""NapCat 启停 / 二维码代理 API"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter

import httpx

router = APIRouter()

NAPCAT_WEBUI_URL = "http://127.0.0.1:6099"
QQ_APP_PATH = "/Applications/QQ.app/Contents/MacOS/QQ"
QQ_PACKAGE_JSON = Path("/Applications/QQ.app/Contents/Resources/app/package.json")
QQ_ACCOUNT = "3540159556"

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
NAPCAT_PACKAGE = PROJECT_DIR / "package.json.napcat"
ORIGINAL_PACKAGE = PROJECT_DIR / "package.json.original"


# ─── 工具函数 ───

def _is_napcat_mode() -> bool:
    """检查当前 QQ 的 package.json 是否已切换到 NapCat 模式"""
    try:
        data = json.loads(QQ_PACKAGE_JSON.read_text(encoding="utf-8"))
        return "napcat" in data.get("main", "").lower()
    except Exception:
        return False


def _switch_to_napcat() -> tuple[bool, str]:
    """切换 QQ 到 NapCat 模式：替换 package.json + 重签名"""
    if not NAPCAT_PACKAGE.exists():
        return False, f"NapCat package.json 不存在: {NAPCAT_PACKAGE}"

    try:
        shutil.copy2(NAPCAT_PACKAGE, QQ_PACKAGE_JSON)
        # macOS 重签名，忽略失败
        subprocess.run(
            ["codesign", "--force", "--deep", "--sign", "-", "/Applications/QQ.app"],
            capture_output=True, timeout=30,
        )
        subprocess.run(
            ["xattr", "-cr", "/Applications/QQ.app"],
            capture_output=True, timeout=10,
        )
        return True, "已切换到 NapCat 模式"
    except Exception as e:
        return False, f"切换失败: {e}"


def _switch_to_normal() -> tuple[bool, str]:
    """切换 QQ 回普通模式"""
    if not ORIGINAL_PACKAGE.exists():
        return False, f"原版 package.json 不存在: {ORIGINAL_PACKAGE}"

    try:
        shutil.copy2(ORIGINAL_PACKAGE, QQ_PACKAGE_JSON)
        subprocess.run(
            ["codesign", "--force", "--deep", "--sign", "-", "/Applications/QQ.app"],
            capture_output=True, timeout=30,
        )
        subprocess.run(
            ["xattr", "-cr", "/Applications/QQ.app"],
            capture_output=True, timeout=10,
        )
        return True, "已切换回普通模式"
    except Exception as e:
        return False, f"切换失败: {e}"


def _kill_all_qq() -> None:
    """杀掉所有 QQ 进程"""
    subprocess.run(["killall", "QQ"], capture_output=True, timeout=5)


def _find_napcat_pids() -> list[int]:
    """查找系统中所有 --no-sandbox 模式的 QQ 主进程 PID"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "QQ.app.*--no-sandbox"],
            capture_output=True, text=True, timeout=3,
        )
        return [int(p) for p in result.stdout.strip().split("\n") if p.strip()]
    except Exception:
        return []


async def _probe_webui() -> bool:
    """探测 NapCat WebUI 是否可达"""
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{NAPCAT_WEBUI_URL}/api/get/robot/status")
            return resp.status_code == 200
    except Exception:
        return False


# ─── API 路由 ───

@router.get("/status")
async def napcat_status():
    """获取 NapCat 状态"""
    pids = _find_napcat_pids()
    webui_reachable = await _probe_webui()

    return {
        "napcat_mode": _is_napcat_mode(),
        "process_running": len(pids) > 0,
        "webui_reachable": webui_reachable,
        "pids": pids,
    }


@router.post("/start")
async def start_napcat():
    """一键启动 NapCat：关旧 QQ → 切换模式 → 启动"""
    # 已经在跑且 WebUI 可达 → 不重复操作
    if _find_napcat_pids() and await _probe_webui():
        return {"ok": True, "message": "NapCat 已在运行且 WebUI 可达"}

    # Step 1: 关掉所有 QQ（普通模式或残留进程）
    _kill_all_qq()
    await asyncio.sleep(2)

    # Step 2: 切换到 NapCat 模式
    if not _is_napcat_mode():
        ok, msg = _switch_to_napcat()
        if not ok:
            return {"ok": False, "message": msg}

    # Step 3: 启动 QQ --no-sandbox
    try:
        subprocess.Popen(
            [QQ_APP_PATH, "--no-sandbox", "-q", QQ_ACCOUNT],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return {"ok": False, "message": f"QQ 未找到: {QQ_APP_PATH}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}

    # Step 4: 等待 WebUI 就绪
    for i in range(20):
        await asyncio.sleep(2)
        if await _probe_webui():
            return {"ok": True, "message": "NapCat 启动成功，WebUI 已就绪"}
        # 进程存在就继续等
        if _find_napcat_pids():
            continue
        # 进程都没了，可能还在 fork
        if i < 5:
            continue
        break

    pids = _find_napcat_pids()
    if pids:
        return {"ok": True, "message": "NapCat 进程已启动，WebUI 尚未就绪（可能需要手动确认登录）", "pids": pids}

    return {"ok": False, "message": "启动超时，请检查 QQ 是否弹出登录窗口"}


@router.post("/stop")
async def stop_napcat():
    """停止 NapCat 并切换回普通模式"""
    pids = _find_napcat_pids()
    if not pids and not await _probe_webui():
        return {"ok": True, "message": "NapCat 未在运行"}

    # 杀掉所有 QQ 进程
    _kill_all_qq()
    await asyncio.sleep(2)

    # 强制清理残留
    remaining = _find_napcat_pids()
    for pid in remaining:
        try:
            subprocess.run(["kill", "-9", str(pid)], timeout=3)
        except Exception:
            pass

    # 切换回普通模式
    ok, msg = _switch_to_normal()

    return {"ok": True, "message": f"NapCat 已停止。{msg}"}


@router.get("/qrcode")
async def proxy_qrcode():
    """代理 NapCat WebUI 的登录二维码"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{NAPCAT_WEBUI_URL}/api/get/robot/qrcode")
            if resp.status_code == 200:
                return resp.json()
            return {"ok": False, "message": f"NapCat 返回 {resp.status_code}"}
    except Exception as e:
        return {"ok": False, "message": f"无法连接 NapCat WebUI: {e}"}
