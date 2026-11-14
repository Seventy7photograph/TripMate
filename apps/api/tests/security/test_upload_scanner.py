# 文件说明：ClamAV INSTREAM 协议回归测试。

import asyncio
import struct

import pytest

from app.services.upload_scanner import (
    ClamAVScanner,
    MalwareDetectedError,
)


@pytest.mark.parametrize(
    ("response", "expected_error"),
    [
        (b"stream: OK\0", None),
        (b"stream: Eicar-Test-Signature FOUND\0", MalwareDetectedError),
    ],
)
async def test_clamav_instream_protocol(
    response: bytes,
    expected_error: type[Exception] | None,
) -> None:
    async def handle(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        assert await reader.readuntil(b"\0") == b"zINSTREAM\0"
        while True:
            length = struct.unpack("!I", await reader.readexactly(4))[0]
            if length == 0:
                break
            await reader.readexactly(length)
        writer.write(response)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    scanner = ClamAVScanner(
        host="127.0.0.1",
        port=port,
        timeout_seconds=2,
    )
    try:
        if expected_error is None:
            await scanner.scan(b"trip notes")
        else:
            with pytest.raises(expected_error):
                await scanner.scan(b"EICAR")
    finally:
        server.close()
        await server.wait_closed()
