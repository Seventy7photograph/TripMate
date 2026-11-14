# 文件说明：业务服务：上传文件恶意内容扫描。
import asyncio
import struct
from contextlib import suppress
from typing import Protocol

from app.core.config import Settings


class ScannerError(Exception):
    pass


class MalwareDetectedError(ScannerError):
    def __init__(self, signature: str) -> None:
        super().__init__(signature)
        self.signature = signature


class ScannerUnavailableError(ScannerError):
    pass


class UploadScanner(Protocol):
    async def scan(self, data: bytes) -> None: ...


class NoopUploadScanner:
    async def scan(self, data: bytes) -> None:
        del data


class ClamAVScanner:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        timeout_seconds: float,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout_seconds = timeout_seconds

    async def scan(self, data: bytes) -> None:
        try:
            async with asyncio.timeout(self._timeout_seconds):
                reader, writer = await asyncio.open_connection(
                    self._host,
                    self._port,
                )
                try:
                    writer.write(b"zINSTREAM\0")
                    for offset in range(0, len(data), 64 * 1024):
                        chunk = data[offset:offset + 64 * 1024]
                        writer.write(struct.pack("!I", len(chunk)))
                        writer.write(chunk)
                    writer.write(struct.pack("!I", 0))
                    await writer.drain()
                    response = await reader.readuntil(b"\0")
                finally:
                    writer.close()
                    with suppress(Exception):
                        await writer.wait_closed()
        except TimeoutError as exc:
            raise ScannerUnavailableError("ClamAV scan timed out") from exc
        except (
            OSError,
            asyncio.IncompleteReadError,
            asyncio.LimitOverrunError,
        ) as exc:
            raise ScannerUnavailableError("ClamAV is unavailable") from exc

        normalized = response.rstrip(b"\0").decode("utf-8", errors="replace")
        if normalized.endswith("OK"):
            return
        if "FOUND" in normalized:
            raise MalwareDetectedError(normalized)
        raise ScannerUnavailableError("ClamAV returned an invalid response")


def create_upload_scanner(settings: Settings) -> UploadScanner:
    host = (settings.clamav_host or "").strip()
    if not host:
        if settings.app_env == "production":
            raise ValueError("CLAMAV_HOST is required in production")
        return NoopUploadScanner()
    return ClamAVScanner(
        host=host,
        port=settings.clamav_port,
        timeout_seconds=settings.clamav_timeout_seconds,
    )
