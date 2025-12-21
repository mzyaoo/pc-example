from fastapi import FastAPI
from app.routers import health

import uvicorn


def create_app() -> FastAPI:
    app = FastAPI(
        title="FastAPI Demo",
        version="1.0.0",
        description="FastAPI 项目初始化示例"
    )

    # 注册路由
    app.include_router(health.router, prefix="/health", tags=["Health"])

    return app


app = create_app()


def main():
    """
    main 方法启动项目
    """
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式
        log_level="info"
    )


if __name__ == "__main__":
    main()
