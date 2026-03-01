"""
Web 控制台 — 挂载 API 路由 + 静态文件到 NoneBot2 FastAPI
"""

from __future__ import annotations

from pathlib import Path

from nonebot.drivers import Driver

DIST_DIR = Path(__file__).parent / "frontend" / "dist"


def mount_web_app(driver: Driver) -> None:
    """在 NoneBot2 的 FastAPI 实例上挂载 Web 控制台"""
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    from .api import api_router

    app: FastAPI = driver.server_app  # type: ignore[attr-defined]

    # 挂载 API 路由
    app.include_router(api_router, prefix="/api")

    # 挂载前端静态文件（如果构建产物存在）
    if DIST_DIR.exists():
        # 静态资源（JS/CSS 等）— 路径必须与 vite base: '/web/' 匹配
        assets_dir = DIST_DIR / "assets"
        if assets_dir.exists():
            app.mount("/web/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        # SPA 回退：非资源的 /web/* 路径返回 index.html
        @app.get("/web/{full_path:path}")
        @app.get("/web")
        async def serve_spa(full_path: str = ""):
            index = DIST_DIR / "index.html"
            if index.exists():
                return FileResponse(str(index))
            return {"error": "前端未构建，请运行 cd frontend && npm run build"}
