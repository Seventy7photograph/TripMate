# 文件说明：FastAPI 本地启动入口。
import argparse
import asyncio
import sys
from pathlib import Path

import uvicorn

API_ROOT = Path(__file__).resolve().parent

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the TripMate API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        loop=asyncio.SelectorEventLoop,
        reload=args.reload,
        app_dir=str(API_ROOT),
    )


if __name__ == "__main__":
    main()
