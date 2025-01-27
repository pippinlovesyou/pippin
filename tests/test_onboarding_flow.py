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
    fills out the form, and submits. Confirms success or that the modal closes.
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
        # 3. Initialize WebDriver
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=options)

        # 4. Navigate to your server's root
        driver.get("http://localhost:8000")
        wait = WebDriverWait(driver, 10)

        # 5. (Optional) Click the "Overview" tab if needed
        # e.g., if there's a tab with [data-tab="overview"]
        overview_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-tab="overview"]')))
        overview_button.click()

        # 6. Click "Open Onboarding Wizard"
        wizard_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[text()="Open Onboarding Wizard"]')))
        wizard_button.click()

        # 7. Fill out the onboarding modal fields
        # Character Name
        char_name_input = wait.until(EC.visibility_of_element_located((By.ID, 'onboardingCharName')))
        char_name_input.clear()
        char_name_input.send_keys("Test Digital Being")

        # Primary Objective
        primary_obj_input = driver.find_element(By.ID, 'onboardingPrimaryObjective')
        primary_obj_input.clear()
        primary_obj_input.send_keys("Testing Primary Objective")

        # LLM Choice: "lite_llm" or "none"
        llm_choice = driver.find_element(By.ID, 'onboardingLLMChoice')
        llm_choice.send_keys("lite_llm")

        time.sleep(1)  # allow DOM to reveal LiteLLM fields

        # LLM Model & API Key
        model_input = driver.find_element(By.ID, 'onboardingLiteLLMModelName')
        model_input.clear()
        model_input.send_keys("openai/gpt-3.5-turbo")

        api_key_input = driver.find_element(By.ID, 'onboardingLiteLLMApiKey')
        api_key_input.clear()
        api_key_input.send_keys("sk-FAKE-KEY1234")

        # Optionally fill advanced fields
        adv_obj_input = driver.find_element(By.ID, 'onboardingAdvancedObjectives')
        adv_obj_input.send_keys("Some advanced objective text")

        # 8. (Optional) Uncheck or check certain activities if needed:
        # For example, if there's a checkbox #activity_checkbox_activity_nap
        # checkEl = driver.find_element(By.ID, 'activity_checkbox_activity_nap')
        # checkEl.click()

        # 9. Click "Save"
        save_button = wait.until(EC.element_to_be_clickable((By.ID, 'onboardingSave')))
        save_button.click()

        # 10. Check for success message or that the modal closes
        # The code sets success text in #onboardingSuccess, then hides the modal
        success_div = wait.until(EC.visibility_of_element_located((By.ID, 'onboardingSuccess')))
        assert "Onboarding saved successfully" in success_div.text

        time.sleep(1)  # let the modal close

        # Confirm modal has closed (example check)
        modal_el = driver.find_element(By.CSS_SELECTOR, '.modal')
        display_prop = modal_el.value_of_css_property('display')
        assert display_prop == 'none', f"Expected modal display='none', but got '{display_prop}'"

    finally:
        # Terminate the server & print logs
        process.terminate()
        process.wait()
        stdout, stderr = process.communicate()
        print("Server stdout:", stdout.decode())
        print("Server stderr:", stderr.decode())

        if "driver" in locals():
            driver.quit()
