# tests/test_api_keys.py

import subprocess
import time
import pytest
import asyncio
from aiohttp import ClientSession

@pytest.mark.asyncio
async def test_api_key_configuration():
    """
    Check that 'configure_api_key' saves a dummy key and returns success.
    """
    process = subprocess.Popen(
        ["python", "my_digital_being/server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    await asyncio.sleep(5)

    try:
        async with ClientSession() as session:
            # Onboard
            async with session.ws_connect("ws://localhost:8000/ws") as ws:
                await ws.send_json({
                    "type": "command",
                    "command": "save_onboarding_data",
                    "params": {
                        "character": {"setup_complete": True},
                        "skills": {},
                        "constraints": {}
                    }
                })
                await ws.receive_json()

            # Configure an API key
            async with session.ws_connect("ws://localhost:8000/ws") as ws:
                await ws.send_json({
                    "type": "command",
                    "command": "configure_api_key",
                    "params": {
                        "skill_name": "dummy_skill",
                        "key_name": "DUMMY_KEY",
                        "api_key": "sk-FAKE-123"
                    }
                })
                resp = await ws.receive_json()
                data = resp["response"]
                assert data["success"] is True, "API key configuration failed"

    finally:
        process.terminate()
        process.wait()
        stdout, stderr = process.communicate()
        print("STDOUT:", stdout.decode())
        print("STDERR:", stderr.decode())
