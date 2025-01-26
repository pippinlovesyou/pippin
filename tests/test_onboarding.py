from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

        # Wait for the button to be clickable and click it
        wait = WebDriverWait(driver, 10)  # Wait up to 10 seconds
        button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#overview-tab button")))
        button.click()

        # Wait for the modal-content to become visible
        modal_content = wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "modal-content")))
        assert modal_content.is_displayed(), "Modal content is not displayed"

    finally:
        # Stop the server
        process.terminate()
        process.wait()

        # Quit the WebDriver
        if "driver" in locals():
            driver.quit()
