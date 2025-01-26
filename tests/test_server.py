import subprocess
import time
import requests
import pytest
import asyncio
from aiohttp import ClientSession

def test_server_loads():
    """
    Test if server starts and serves the root page.
    """
    process = subprocess.Popen(
        ["python", "my_digital_being/server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    time.sleep(5)

    try:
        # Check if server responds at http://localhost:8000
        response = requests.get("http://localhost:8000")
        assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
        # Adjust string below to match your actual HTML content
        assert "Digital Being Monitor" in response.text, "Expected content not found in page"

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
    Test if WebSocket server is running at ws://localhost:8000/ws
    """
    # Increase the delay if server initialization is slower
    await asyncio.sleep(10)

    async with ClientSession() as session:
        try:
            async with session.ws_connect("ws://localhost:8000/ws") as ws:
                await ws.send_json({"type": "get_state"})
                response = await ws.receive_json()
                assert response["type"] == "state_update", "Unexpected WebSocket response type"
                assert "data" in response, "WebSocket response missing 'data' field"
        except Exception as e:
            pytest.fail(f"WebSocket connection failed: {e}")
