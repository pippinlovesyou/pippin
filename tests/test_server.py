import subprocess
import time
import requests
import pytest
import asyncio
from aiohttp import ClientSession

def test_server_loads():
    """
    Test if server starts and serves any root page content.
    """
    process = subprocess.Popen(
        ["python", "my_digital_being/server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Increase the sleep if the server is slow to start
    time.sleep(5)

    try:
        # Check if server responds at http://localhost:8000
        response = requests.get("http://localhost:8000")
        assert response.status_code == 200, f"Unexpected status code: {response.status_code}"

        # Simple check: ensure the response body has content
        assert len(response.text) > 0, "Expected non-empty body content"

    finally:
        process.terminate()
        process.wait()

        # Capture server output for debugging
        stdout, stderr = process.communicate()
        print("Server stdout:")
        print(stdout.decode())
        print("Server stderr:")
        print(stderr.decode())


@pytest.mark.asyncio
async def test_websocket():
    """
    Test if the WebSocket server is listening at ws://localhost:8000/ws.
    """
    # Wait longer if the server needs more time to initialize
    await asyncio.sleep(10)

    async with ClientSession() as session:
        try:
            async with session.ws_connect("ws://localhost:8000/ws") as ws:
                # Send a dummy message
                await ws.send_json({"type": "ping"})
                response = await ws.receive_json()

                # Simple check for some JSON response
                assert isinstance(response, dict), "Expected a JSON object"
        except Exception as e:
            pytest.fail(f"WebSocket connection failed: {e}")
