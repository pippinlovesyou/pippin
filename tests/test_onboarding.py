import subprocess
import time

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def test_onboarding_modal():
    """
    Simplified test to ensure the page actually loads in Selenium.
    """
    process = subprocess.Popen(
        ["python", "my_digital_being/server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Give the server time to start
    time.sleep(5)

    try:
        # Start the Selenium WebDriver
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)

        # Navigate to server's root URL
        driver.get("http://localhost:8000")

        # Wait for body to appear
        wait = WebDriverWait(driver, 10)  # Wait up to 10 seconds
        body = wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        assert body is not None, "Body did not load in the browser"

    finally:
        process.terminate()
        process.wait()

        stdout, stderr = process.communicate()
        print("Server stdout:")
        print(stdout.decode())
        print("Server stderr:")
        print(stderr.decode())

        if "driver" in locals():
            driver.quit()
