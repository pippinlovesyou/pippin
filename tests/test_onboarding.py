import subprocess
import time
from selenium import webdriver
from selenium.webdriver.common.by import By

def test_onboarding_modal():
    # Start the server in a subprocess
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

        # Navigate to the server's root URL
        driver.get("http://localhost:8000")

        # Find and click the button in the div with id "overview-tab"
        button = driver.find_element(By.CSS_SELECTOR, "#overview-tab button")
        button.click()

        # Wait briefly for modal content to display
        time.sleep(2)

        # Confirm the modal-content div is displayed
        modal_content = driver.find_element(By.CLASS_NAME, "modal-content")
        assert modal_content.is_displayed(), "Modal content is not displayed"

    finally:
        # Stop the server
        process.terminate()
        process.wait()

        # Quit the WebDriver only if initialized
        if 'driver' in locals():
            driver.quit()
