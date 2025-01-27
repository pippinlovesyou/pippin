# tests/test_http_server_loads.py

import subprocess
import time
import requests
import pytest

def test_http_server_loads():
    """
    Start the server, ensure it returns 200 OK at root.
    """
    process = subprocess.Popen(
        ["python", "my_digital_being/server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for server to spin up
    time.sleep(5)

    try:
        resp = requests.get("http://localhost:8000")
        assert resp.status_code == 200, "Server did not return 200 at /"
    finally:
        process.terminate()
        process.wait()

        stdout, stderr = process.communicate()
        print("Server stdout:", stdout.decode())
        print("Server stderr:", stderr.decode())
