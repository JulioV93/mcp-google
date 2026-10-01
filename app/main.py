import uvicorn

from app.config import get_settings


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.asgi:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
        # OAuth callbacks contain one-time credentials in their query string.
        access_log=False,
    )


if __name__ == "__main__":
    run()
