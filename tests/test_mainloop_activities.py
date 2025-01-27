# tests/test_main_loop_activities.py

import subprocess
import time
import pytest
import asyncio
from aiohttp import ClientSession

@pytest.mark.asyncio
async def test_main_loop_activities():
    """
    After setting up onboarding (setup_complete=true), 
    confirm at least one activity is executed and logged.
    """
    process = subprocess.Popen(
        ["python", "my_digital_being/server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    # Wait for server to come up
    await asyncio.sleep(5)

    try:
        async with ClientSession() as session:
            # 1) Connect WebSocket
            async with session.ws_connect("ws://localhost:8000/ws") as ws:
                # 2) Save onboarding data w/ 'setup_complete' = true
                await ws.send_json({
                    "type": "command",
                    "command": "save_onboarding_data",
                    "params": {
                        "character": {
                            "name": "Test Being",
                            "objectives": {"primary": "Test Automation"},
                            "setup_complete": True
                        },
                        "skills": {
                            # Minimal skill to enable, or just "default_llm_skill": null
                            "default_llm_skill": None
                        },
                        "constraints": {
                            # minimal constraints if needed
                            "global_constraints": "",
                            "activities_config": {}
                        }
                    }
                })

                # Wait for response
                resp = await ws.receive_json()
                assert resp["type"] == "command_response"
                assert resp["command"] == "save_onboarding_data"
                assert resp["response"].get("success") is True

            # 3) Wait for the loop to pick an activity
            #   For safety, wait ~10-15 seconds
            await asyncio.sleep(15)

            # 4) Connect again and check activity history
            async with session.ws_connect("ws://localhost:8000/ws") as ws:
                await ws.send_json({
                    "type": "command",
                    "command": "get_activity_history",
                    "params": {"limit": 5, "offset": 0}
                })
                resp = await ws.receive_json()
                assert resp["type"] == "command_response"
                assert resp["command"] == "get_activity_history"
                data = resp["response"]
                assert data["success"] is True

                activities = data.get("activities", [])
                # We expect at least 1 activity
                assert len(activities) > 0, "No activities were executed after onboarding"
                print("Activities found:", activities)

    finally:
        process.terminate()
        process.wait()
        stdout, stderr = process.communicate()
        print("STDOUT:", stdout.decode())
        print("STDERR:", stderr.decode())
