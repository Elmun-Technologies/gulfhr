"""Fly.io liveness endpoint testlari."""

from __future__ import annotations

import asyncio

import pytest

from app.health import start_health_server


@pytest.mark.asyncio
async def test_health_server_returns_ok() -> None:
    server = await start_health_server(host="127.0.0.1", port=0)
    try:
        assert server.sockets
        port = server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer.drain()
        response = await reader.read()
        writer.close()
        await writer.wait_closed()
    finally:
        server.close()
        await server.wait_closed()

    assert response.startswith(b"HTTP/1.1 200 OK")
    assert b'{"status":"ok"}' in response
