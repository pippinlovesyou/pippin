# tests/test_websocket_basic.py

import subprocess
import time
import pytest
import asyncio
from aiohttp import ClientSession

@pytest.mark.asyncio
async def test_websocket_basic():
    """
    Start the server, then test the WebSocket in one go.
    """
    process = subprocess.Popen(
        ["python", "my_digital_being/server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for the server to be ready (increase if needed)
    await asyncio.sleep(10)

    try:
        async with ClientSession() as session:
            async with session.ws_connect("ws://localhost:8000/ws") as ws:
                # Send a JSON message (like a "ping" or minimal test)
                await ws.send_json({"type": "ping"})
                response = await ws.receive_json()

                # Assert we got a valid JSON response
                assert isinstance(response, dict), "Expected a JSON object from server"
    finally:
        process.terminate()
        process.wait()
        stdout, stderr = process.communicate()
        print("Server stdout:")
        print(stdout.decode())
        print("Server stderr:")
        print(stderr.decode())
