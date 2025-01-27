import subprocess
import time
import requests
import pytest
import asyncio
from aiohttp import ClientSession

def test_server_loads():
    """
    Start the server, check if HTTP is available, then stop.
    """
    process = subprocess.Popen(
        ["python", "my_digital_being/server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(5)  # allow server to start

    try:
        response = requests.get("http://localhost:8000")
        assert response.status_code == 200, "Server didn't return 200 on /"
    finally:
        process.terminate()
        process.wait()
        stdout, stderr = process.communicate()
        print("Server stdout:", stdout.decode())
        print("Server stderr:", stderr.decode())

@pytest.mark.asyncio
async def test_websocket():
    """
    Start the server, then test the WebSocket in one go.
    """
    process = subprocess.Popen(
        ["python", "my_digital_being/server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    # wait for server to be ready
    await asyncio.sleep(10)

    try:
        async with ClientSession() as session:
            async with session.ws_connect("ws://localhost:8000/ws") as ws:
                await ws.send_json({"type": "ping"})
                response = await ws.receive_json()
                assert isinstance(response, dict), "Expected a JSON object"
    finally:
        process.terminate()
        process.wait()
        stdout, stderr = process.communicate()
        print("Server stdout:", stdout.decode())
        print("Server stderr:", stderr.decode())
