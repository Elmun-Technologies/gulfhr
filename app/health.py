"""Fly.io health endpoint for the long-polling bot.

Telegram updates are received through long polling, so the bot does not need a
public web API. Fly.io may nevertheless have an HTTP service configured for an
existing app, and a service without a listener can stop or mark the machine as
unhealthy. This tiny dependency-free server gives Fly a stable liveness
endpoint while the Telegram polling task runs in the same event loop.
"""

from __future__ import annotations

import asyncio

_HEALTH_RESPONSE = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: application/json; charset=utf-8\r\n"
    b"Content-Length: 15\r\n"
    b"Connection: close\r\n"
    b"\r\n"
    b'{"status":"ok"}'
)


async def _handle_health_request(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    """Return a small HTTP response and close the connection.

    The request body is irrelevant for a liveness check. Reading a bounded
    amount first prevents a client from receiving a response before the HTTP
    request arrives, while the timeout prevents abandoned connections from
    accumulating forever.
    """
    try:
        await asyncio.wait_for(reader.read(4096), timeout=5)
        writer.write(_HEALTH_RESPONSE)
        await writer.drain()
    except (TimeoutError, ConnectionError):
        # A health-check client disappearing is not an application error.
        pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, asyncio.CancelledError):
            pass


async def start_health_server(*, host: str = "0.0.0.0", port: int = 8080) -> asyncio.Server:
    """Start the internal liveness server used by Fly.io."""
    return await asyncio.start_server(_handle_health_request, host=host, port=port)


__all__ = ["start_health_server"]
