import subprocess
import time
import requests
import pytest
import asyncio
from aiohttp import ClientSession

# Test to check if the server loads and serves the root page
def test_server_loads():
    # Start the server in a subprocess
    process = subprocess.Popen(
        ["python", "my_digital_being/server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Give the server time to start
    time.sleep(5)

    try:
        # Test if the server responds at the root endpoint
        response = requests.get("http://localhost:8000")
        assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
        assert "Digital Being Monitor" in response.text, "Expected content not found in page"
    finally:
        # Stop the server
        process.terminate()
        process.wait()

        # Capture server output for debugging
        stdout, stderr = process.communicate()
        print("Server stdout:")
        print(stdout.decode())
        print("Server stderr:")
        print(stderr.decode())

# Test WebSocket communication
@pytest.mark.asyncio
async def test_websocket():
    # Wait for the server to be ready
    await asyncio.sleep(5)

    # Connect to the WebSocket and send a test message
    async with ClientSession() as session:
        async with session.ws_connect("ws://localhost:8000/ws") as ws:
            # Send a "get_state" message
            await ws.send_json({"type": "get_state"})

            # Receive the response
            response = await ws.receive_json()

            # Assert the expected response
            assert response["type"] == "state_update", "Unexpected WebSocket response type"
            assert "data" in response, "WebSocket response missing 'data' field"
