"""NapCat 启停 / 二维码代理 API"""

from __future__ import annotations

import asyncio
import subprocess

from fastapi import APIRouter

import httpx

router = APIRouter()

# 通过本 API 启动的 NapCat 进程引用
_napcat_proc: subprocess.Popen | None = None

NAPCAT_WEBUI_URL = "http://127.0.0.1:6099"
QQ_APP_PATH = "/Applications/QQ.app/Contents/MacOS/QQ"
QQ_ACCOUNT = "3540159556"


def _is_proc_alive() -> tuple[bool, int | None]:
    """检查内部管理的进程是否存活"""
    global _napcat_proc
    if _napcat_proc is not None and _napcat_proc.poll() is None:
        return True, _napcat_proc.pid
    _napcat_proc = None
    return False, None


def _find_external_qq_pid() -> int | None:
    """检测系统中是否有 --no-sandbox 模式的 QQ 进程（非本 API 启动的）"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "QQ.app.*--no-sandbox"],
            capture_output=True, text=True, timeout=3,
        )
        pids = result.stdout.strip().split("\n")
        if pids and pids[0]:
            return int(pids[0])
    except Exception:
        pass
    return None


@router.get("/status")
async def napcat_status():
    """获取 NapCat 状态"""
    # 先检查内部进程，再检查系统进程
    managed, pid = _is_proc_alive()
    if not managed:
        pid = _find_external_qq_pid()

    process_running = pid is not None

    # 始终探测 WebUI，不论进程由谁启动
    webui_reachable = False
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{NAPCAT_WEBUI_URL}/api/get/robot/status")
            webui_reachable = resp.status_code == 200
    except Exception:
        pass

    return {
        "process_running": process_running,
        "webui_reachable": webui_reachable,
        "pid": pid,
        "managed": managed,
    }


@router.post("/start")
async def start_napcat():
    """启动 NapCat（QQ --no-sandbox 模式）"""
    global _napcat_proc

    # 检查是否已有进程在跑
    managed, pid = _is_proc_alive()
    if managed:
        return {"ok": True, "message": "NapCat 已在运行", "pid": pid}

    ext_pid = _find_external_qq_pid()
    if ext_pid:
        return {"ok": True, "message": f"检测到外部 NapCat 进程（PID: {ext_pid}）", "pid": ext_pid}

    try:
        _napcat_proc = subprocess.Popen(
            [QQ_APP_PATH, "--no-sandbox", "-q", QQ_ACCOUNT],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await asyncio.sleep(2)

        if _napcat_proc.poll() is not None:
            return {"ok": False, "message": "NapCat 启动失败（进程已退出）"}

        return {"ok": True, "pid": _napcat_proc.pid}
    except FileNotFoundError:
        return {"ok": False, "message": f"QQ 未找到: {QQ_APP_PATH}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@router.post("/stop")
async def stop_napcat():
    """停止 NapCat"""
    global _napcat_proc

    managed, pid = _is_proc_alive()
    if managed:
        _napcat_proc.terminate()
        try:
            _napcat_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _napcat_proc.kill()
        _napcat_proc = None
        return {"ok": True, "message": "NapCat 已停止"}

    # 尝试停止外部进程
    ext_pid = _find_external_qq_pid()
    if ext_pid:
        try:
            subprocess.run(["kill", str(ext_pid)], timeout=5)
            return {"ok": True, "message": f"已终止外部 NapCat 进程（PID: {ext_pid}）"}
        except Exception as e:
            return {"ok": False, "message": f"终止失败: {e}"}

    return {"ok": True, "message": "NapCat 未在运行"}


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
