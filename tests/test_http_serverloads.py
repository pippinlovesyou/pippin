# tests/test_http_server_loads.py

import subprocess
import time
import requests
import pytest

def test_http_server_loads():
    """
    Start the server, check if HTTP is available, then stop.
    """
    process = subprocess.Popen(
        ["python", "my_digital_being/server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Give the server time to start (increase if needed)
    time.sleep(5)

    try:
        response = requests.get("http://localhost:8000")
        assert response.status_code == 200, "Server didn't return 200 on /"
    finally:
        process.terminate()
        process.wait()

        stdout, stderr = process.communicate()
        print("Server stdout:")
        print(stdout.decode())
        print("Server stderr:")
        print(stderr.decode())
