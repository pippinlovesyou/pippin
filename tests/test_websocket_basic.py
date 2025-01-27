# tests/test_websocket_basic.py

import subprocess
import time
import pytest
import asyncio
from aiohttp import ClientSession

@pytest.mark.asyncio
async def test_websocket_basic():
    """
    Start server, connect to /ws, send a dummy JSON, expect a JSON reply.
    """
    process = subprocess.Popen(
        ["python", "my_digital_being/server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    await asyncio.sleep(10)  # Wait for server readiness

    try:
        async with ClientSession() as session:
            async with session.ws_connect("ws://localhost:8000/ws") as ws:
                await ws.send_json({"type": "ping"})
                response = await ws.receive_json()
                assert isinstance(response, dict), "Expected JSON object from /ws"
    finally:
        process.terminate()
        process.wait()

        stdout, stderr = process.communicate()
        print("Server stdout:", stdout.decode())
        print("Server stderr:", stderr.decode())
