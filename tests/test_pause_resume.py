# tests/test_pause_resume.py

import subprocess
import time
import pytest
import asyncio
from aiohttp import ClientSession

@pytest.mark.asyncio
async def test_pause_resume():
    """
    Confirm that pausing stops new activities, resuming restarts them.
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
                        "skills": {"default_llm_skill": None},
                        "constraints": {}
                    }
                })
                await ws.receive_json()  # skip details

            # Wait 10 seconds => see some activity
            await asyncio.sleep(10)
            initial_count = await get_activity_count(session)

            # Pause
            await send_pause(session)
            # Wait 10s => no new activity
            await asyncio.sleep(10)
            paused_count = await get_activity_count(session)
            assert paused_count == initial_count, "Activity count changed while paused"

            # Resume
            await send_resume(session)
            await asyncio.sleep(10)
            resumed_count = await get_activity_count(session)
            assert resumed_count > paused_count, "No new activity after resuming"

    finally:
        process.terminate()
        process.wait()
        stdout, stderr = process.communicate()
        print("STDOUT:", stdout.decode())
        print("STDERR:", stderr.decode())


async def get_activity_count(session):
    async with session.ws_connect("ws://localhost:8000/ws") as ws:
        await ws.send_json({
            "type": "command",
            "command": "get_activity_history",
            "params": {"limit": 50, "offset": 0}
        })
        resp = await ws.receive_json()
        data = resp["response"]
        acts = data.get("activities", [])
        return len(acts)

async def send_pause(session):
    async with session.ws_connect("ws://localhost:8000/ws") as ws:
        await ws.send_json({"type": "command", "command": "pause"})
        await ws.receive_json()

async def send_resume(session):
    async with session.ws_connect("ws://localhost:8000/ws") as ws:
        await ws.send_json({"type": "command", "command": "resume"})
        await ws.receive_json()
