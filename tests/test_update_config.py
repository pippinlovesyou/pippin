# tests/test_update_config.py

import subprocess
import time
import pytest
import asyncio
from aiohttp import ClientSession

@pytest.mark.asyncio
async def test_update_config():
    """
    Confirm that calling 'update_config' changes the in-memory config.
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

            # Update config e.g. character_config "my_custom_flag"
            async with session.ws_connect("ws://localhost:8000/ws") as ws:
                await ws.send_json({
                    "type": "command",
                    "command": "update_config",
                    "params": {
                        "section": "character_config",
                        "key": "my_custom_flag",
                        "value": True
                    }
                })
                resp = await ws.receive_json()
                data = resp["response"]
                assert data["success"] is True

            # Confirm via get_config
            async with session.ws_connect("ws://localhost:8000/ws") as ws:
                await ws.send_json({
                    "type": "command",
                    "command": "get_config"
                })
                resp = await ws.receive_json()
                data = resp["response"]
                cfg = data.get("config", {})
                char_cfg = cfg.get("character_config", {})
                assert char_cfg.get("my_custom_flag") is True, "Updated config not reflected"

    finally:
        process.terminate()
        process.wait()
        stdout, stderr = process.communicate()
        print("STDOUT:", stdout.decode())
        print("STDERR:", stderr.decode())
