import subprocess
import time

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def test_onboarding_modal():
    """
    Test that clicking the button in the #overview-tab div triggers a modal
    with class 'modal-content' to appear.
    """

    # 1. Start the server in a subprocess
    process = subprocess.Popen(
        ["python", "my_digital_being/server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # 2. Give the server time to start
    time.sleep(5)

    try:
        # 3. Launch Selenium WebDriver
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=options)

        # 4. Navigate to the server's root URL
        driver.get("http://localhost:8000")

        # 5. Wait for the overview-tab button to be clickable
        wait = WebDriverWait(driver, 10)  # Wait up to 10 seconds
        button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#overview-tab button"))
        )
        button.click()

        # 6. Wait for the modal-content div to appear
        modal_content = wait.until(
            EC.visibility_of_element_located((By.CLASS_NAME, "modal-content"))
        )
        assert modal_content.is_displayed(), "Modal content is not displayed"

    finally:
        # 7. Terminate the server process and capture logs
        process.terminate()
        process.wait()

        stdout, stderr = process.communicate()
        print("Server stdout:")
        print(stdout.decode())
        print("Server stderr:")
        print(stderr.decode())

        # 8. Quit the WebDriver if initialized
        if "driver" in locals():
            driver.quit()
