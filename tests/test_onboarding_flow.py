# tests/test_onboarding_flow.py

import subprocess
import time

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def test_onboarding_flow():
    """
    Launches the server, loads the page in Selenium, opens the Onboarding Wizard,
    fills out fields, and submits. Confirms success or that the modal closes.
    """

    process = subprocess.Popen(
        ["python", "my_digital_being/server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Give the server time to start
    time.sleep(5)

    try:
        # 1. Start WebDriver
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=options)

        # 2. Navigate to the server's root URL
        driver.get("http://localhost:8000")

        wait = WebDriverWait(driver, 10)

        # 3. Click the 'overview' tab if needed
        # (In your main.js, the "overview-tab" might be default. If needed, we can do:
        overview_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-tab="overview"]')))
        overview_button.click()

        # 4. Open the onboarding wizard
        # You said the wizard is triggered by a button in the "overview-tab"
        # with text "Open Onboarding Wizard".
        wizard_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[text()="Open Onboarding Wizard"]')))
        wizard_button.click()

        # 5. Fill out the form fields in the modal
        # Example IDs from onboarding.js => #onboardingCharName, #onboardingPrimaryObjective, ...
        char_name_input = wait.until(EC.visibility_of_element_located((By.ID, 'onboardingCharName')))
        char_name_input.clear()
        char_name_input.send_keys("My New Digital Being")

        primary_obj_input = driver.find_element(By.ID, 'onboardingPrimaryObjective')
        primary_obj_input.clear()
        primary_obj_input.send_keys("Test Primary Objective")

        llm_choice = driver.find_element(By.ID, 'onboardingLLMChoice')
        # e.g., pick 'lite_llm' or 'none'
        llm_choice.send_keys("lite_llm")

        time.sleep(1)  # Let the DOM update
        # If "lite_llm", we can fill out #onboardingLiteLLMModelName and #onboardingLiteLLMApiKey
        model_input = driver.find_element(By.ID, 'onboardingLiteLLMModelName')
        model_input.clear()
        model_input.send_keys("openai/gpt-3.5-turbo")

        api_key_input = driver.find_element(By.ID, 'onboardingLiteLLMApiKey')
        api_key_input.clear()
        api_key_input.send_keys("sk-DUMMY-1234")

        # 6. Optionally fill advanced fields
        adv_obj_input = driver.find_element(By.ID, 'onboardingAdvancedObjectives')
        adv_obj_input.send_keys("Extended advanced objectives here...")

        # 7. Possibly scroll, enable/disable some activities checkboxes
        # But let's assume we keep all defaults. If we needed to uncheck:
        #   driver.find_element(By.ID, 'activity_checkbox_activity_draw').click()

        # 8. Click "Save"
        save_button = wait.until(EC.element_to_be_clickable((By.ID, 'onboardingSave')))
        save_button.click()

        # 9. Confirm success message or the modal closes
        # The script sets a success message in #onboardingSuccess, then hides the modal
        success_div = wait.until(EC.visibility_of_element_located((By.ID, 'onboardingSuccess')))
        assert "Onboarding saved successfully" in success_div.text

        # or check that the modal eventually disappears
        time.sleep(2)
        modal_el = driver.find_element(By.CSS_SELECTOR, '.modal')
        assert modal_el.value_of_css_property('display') == 'none' or modal_el.is_displayed() is False, \
            "Expected the onboarding modal to close after success"

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
