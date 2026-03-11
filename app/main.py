import uvicorn

from app.config import get_settings


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.asgi:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
    )


if __name__ == "__main__":
    run()
