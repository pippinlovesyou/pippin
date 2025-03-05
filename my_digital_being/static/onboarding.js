/**********************************************
 * onboarding.js
 * Enhanced web UI wizard for "Onboarding"
 * LLM selection: "LiteLLM" or "None"
 **********************************************/

(function() {
  let onboardingModal = null;
  let onboardingOverlay = null;

  // We'll store the loaded activity list globally so we can build checkboxes.
  let discoveredActivities = {};
  let loadedConfigs;

  document.addEventListener('DOMContentLoaded', () => {
    // Insert a button in the overview tab for the wizard
    const overviewTab = document.getElementById('overview-tab');
    if (overviewTab) {
      const wizardButton = document.createElement('button');
      wizardButton.className = 'btn';
      wizardButton.textContent = 'Open Onboarding Wizard';
      wizardButton.style.marginBottom = '10px';
      wizardButton.onclick = openOnboardingModal;
      overviewTab.insertBefore(wizardButton, overviewTab.firstChild);
    }

    createOnboardingModal();
  });

  function createOnboardingModal() {
    onboardingOverlay = document.createElement('div');
    onboardingOverlay.className = 'modal';
    onboardingOverlay.style.zIndex = '99999';
    onboardingOverlay.innerHTML = `
      <div class="modal-content">
        <div class="modal-header">
          <h3>Onboarding Wizard</h3>
          <button class="close-modal">&times;</button>
        </div>
        <div class="modal-body" style="max-height: 70vh; overflow-y: auto;">

          <h4>1) Character Setup</h4>
          <div class="form-group">
            <label>Character Name</label>
            <input type="text" id="onboardingCharName" class="styled-input" value="Digital Being" />
          </div>
          <div class="form-group">
            <label>Primary Objective</label>
            <input type="text" id="onboardingPrimaryObjective" class="styled-input" value="Assist users" />
          </div>

          <hr/>
          <h4>2) LLM Setup</h4>
          <p style="font-size:0.9em; color:var(--text-secondary);">
            If you pick "LiteLLM," you can specify a model (like "anthropic/claude-2" or "openrouter/openai/gpt-4") 
            and optionally provide a single API key. 
            That key might be from OpenAI, an OpenRouter token, or other.
          </p>
          <div class="form-group">
            <label>LLM Choice</label>
            <select id="onboardingLLMChoice" class="styled-input">
              <option value="lite_llm">LiteLLM</option>
              <option value="none">None (Skip LLM)</option>
            </select>
          </div>

          <!-- LiteLLM fields -->
          <div id="liteLLMSetup" style="display:none;">
            <div class="form-group">
              <label>Model Name (e.g. "anthropic/claude-2" or "openrouter/openai/gpt-4")</label>
              <input type="text" id="onboardingLiteLLMModelName" class="styled-input" value="openai/gpt-4" />
            </div>
            <div class="form-group">
              <label>API Key (optional)</label>
              <input type="text" id="onboardingLiteLLMApiKey" class="styled-input" placeholder="Your LLM provider key" />
            </div>
          </div>

          <hr/>
          <h4>3) Advanced Setup</h4>
          <p style="font-size:0.9em; color:var(--text-secondary);">
            Provide additional multi-line text for advanced objectives, example activities, and general constraints.
            (Optional, leave blank if you prefer.)
          </p>
          <div class="form-group">
            <label>Advanced Objectives (multi-line)</label>
            <textarea id="onboardingAdvancedObjectives" class="styled-textarea" placeholder="Extended or advanced objectives..."></textarea>
          </div>
          <div class="form-group">
            <label>Example Activities (multi-line)</label>
            <textarea id="onboardingExampleActivities" class="styled-textarea" placeholder="Suggested tasks or domain-specific actions..."></textarea>
          </div>
          <div class="form-group">
            <label>General Constraints (multi-line)</label>
            <textarea id="onboardingGeneralConstraints" class="styled-textarea" placeholder="Any rules or boundaries to keep in mind..."></textarea>
          </div>

          <hr/>
          <h4>4) Enable/Disable Activities</h4>
          <div id="activityEnableSection">
            <p style="font-style: italic; color: var(--text-secondary);">Loading activity list...</p>
          </div>

          <div class="error-msg" id="onboardingError" style="display:none; margin-top:12px;"></div>
          <div class="success-msg" id="onboardingSuccess" style="display:none; margin-top:12px;"></div>
        </div>
        <div class="modal-footer">
          <button class="btn secondary" id="onboardingCancel">Cancel</button>
          <button class="btn primary" id="onboardingSave">Save</button>
        </div>
      </div>
    `;

    document.body.appendChild(onboardingOverlay);

    onboardingModal = onboardingOverlay.querySelector('.modal-content');

    // Close handlers
    onboardingOverlay.querySelector('.close-modal').onclick = closeOnboardingModal;
    onboardingOverlay.querySelector('#onboardingCancel').onclick = closeOnboardingModal;

    // Save handler
    onboardingOverlay.querySelector('#onboardingSave').onclick = saveOnboardingData;

    // Watch for LLM choice changes
    const llmChoiceSelect = onboardingOverlay.querySelector('#onboardingLLMChoice');
    llmChoiceSelect.addEventListener('change', handleLLMChoiceChange);

    // Default "lite_llm" or "none"
    handleLLMChoiceChange();
  }

  async function loadOnboardingData() {
    try {
      // 1) get_config
      const response = await sendCommand('get_config');
      if (!response.success) {
        console.warn("Failed to load config for onboarding:", response.message);
        return;
      }
      const cfg = response.config || {};
      const charCfg = cfg.character_config || {};
      const skillCfg = cfg.skills_config || {};
      const constraintsCfg = cfg.activity_constraints || {};
      loadedConfigs = cfg

      // Fill in the fields
      populateCharacterFields(charCfg);
      populateAdvancedFields(constraintsCfg, charCfg, skillCfg);

      // 2) get_activities
      const actsResp = await sendCommand('get_activities');
      if (actsResp.success) {
        discoveredActivities = actsResp.activities;  // e.g. { "activity_draw": {...}, ... }
        displayActivityEnables();
      } else {
        console.warn("Failed to fetch activities:", actsResp.message);
      }

    } catch (err) {
      console.error("Error loading onboarding data:", err);
    }
  }

  function populateCharacterFields(charCfg) {
    const cName = charCfg.name || "Digital Being";
    document.getElementById('onboardingCharName').value = cName;

    const primaryObj = (charCfg.objectives && charCfg.objectives.primary) || "Assist users";
    document.getElementById('onboardingPrimaryObjective').value = primaryObj;
  }

  function populateAdvancedFields(constraintsCfg, charCfg, skillCfg) {
    const advObj = (charCfg.objectives && charCfg.objectives.advanced) || "";
    document.getElementById('onboardingAdvancedObjectives').value = advObj;

    const exampleActs = charCfg.example_activities || "";
    document.getElementById('onboardingExampleActivities').value = exampleActs;

    const globalCons = constraintsCfg.global_constraints || "";
    document.getElementById('onboardingGeneralConstraints').value = globalCons;

    // LLM choice
    const defaultSkill = skillCfg.default_llm_skill || null;
    let choice = "none";
    if (defaultSkill === "lite_llm") {
      choice = "lite_llm";
      const liteCfg = skillCfg.lite_llm || {};
      const modelName = liteCfg.model_name || "openai/gpt-4";
      document.getElementById('onboardingLiteLLMModelName').value = modelName;
    }
    document.getElementById('onboardingLLMChoice').value = choice;
    handleLLMChoiceChange();
  }

  function displayActivityEnables() {
    const container = document.getElementById('activityEnableSection');
    if (!container) return;
    if (!discoveredActivities || !Object.keys(discoveredActivities).length) {
      container.innerHTML = '<p>No activities discovered.</p>';
      return;
    }

    let html = '';
    Object.entries(discoveredActivities).forEach(([moduleName, info]) => {
      const className = info.name;
      const isEnabled = info.enabled !== false;  // default true
      const checkboxId = `activity_checkbox_${moduleName}`;

      html += `
      <div style="margin-bottom:8px;">
        <label style="display:flex; align-items:center; gap:8px;">
          <input type="checkbox" id="${checkboxId}" ${isEnabled ? 'checked' : ''}/>
          <strong>${className}</strong> <em>(${moduleName})</em>
          <span style="font-size:0.9em; color:var(--text-secondary);">
            cooldown=${info.cooldown}, energy=${info.energy_cost}
          </span>
        </label>
      </div>
      `;
    });
    container.innerHTML = html;
  }

  function openOnboardingModal() {
    if (onboardingOverlay) {
      loadOnboardingData().then(() => {
        onboardingOverlay.style.display = 'flex';
        onboardingOverlay.style.alignItems = 'center';
        onboardingOverlay.style.justifyContent = 'center';
      });
    }
  }

  function closeOnboardingModal() {
    if (onboardingOverlay) {
      onboardingOverlay.style.display = 'none';
    }
  }

  function handleLLMChoiceChange() {
    const choice = document.getElementById('onboardingLLMChoice').value;
    const liteLLMSetup = document.getElementById('liteLLMSetup');

    if (choice === 'lite_llm') {
      liteLLMSetup.style.display = 'block';
    } else {
      liteLLMSetup.style.display = 'none';
    }
  }

  async function saveOnboardingData() {
    const errorDiv = document.getElementById('onboardingError');
    const successDiv = document.getElementById('onboardingSuccess');
    errorDiv.style.display = 'none';
    successDiv.style.display = 'none';
    errorDiv.innerText = '';
    successDiv.innerText = '';

    // 1) Basic character fields
    const charName = document.getElementById('onboardingCharName').value.trim() || "Digital Being";
    const primaryObjective = document.getElementById('onboardingPrimaryObjective').value.trim() || "Assist users";

    // 2) LLM choice
    let skills = {};
    const llmChoice = document.getElementById('onboardingLLMChoice').value;
    if (llmChoice === 'lite_llm') {
      const modelName = document.getElementById('onboardingLiteLLMModelName').value.trim() || "openai/gpt-4";
      const liteKey = document.getElementById('onboardingLiteLLMApiKey').value.trim();
      skills["lite_llm"] = {
        "enabled": true,
        "model_name": modelName,
        "required_api_keys": ["LITELLM"],
        "api_key_mapping": {
          "LITELLM": "LITELLM_API_KEY"
        }
      };
      if (liteKey) {
        skills["lite_llm"]["provided_api_key"] = liteKey;
      }
      skills["default_llm_skill"] = "lite_llm";
    } else {
      // none
      skills["default_llm_skill"] = null;
    }

    // 3) Advanced text
    const advObjectives = document.getElementById('onboardingAdvancedObjectives').value;
    const exampleActs = document.getElementById('onboardingExampleActivities').value;
    const generalConstraints = document.getElementById('onboardingGeneralConstraints').value;

    const character = {
      name: charName,
      objectives: {
        primary: primaryObjective
      }
    };
    if (advObjectives && advObjectives.trim()) {
      character.objectives["advanced"] = advObjectives.trim();
    }
    if (exampleActs && exampleActs.trim()) {
      character["example_activities"] = exampleActs.trim();
    }

    // 4) Build an activities_config object from the checkboxes
    const activities_config = {};
    if (discoveredActivities && Object.keys(discoveredActivities).length) {
      Object.entries(discoveredActivities).forEach(([moduleName, info]) => {
        const className = info.name;
        const checkboxId = `activity_checkbox_${moduleName}`;
        const boxEl = document.getElementById(checkboxId);
        const isChecked = boxEl ? boxEl.checked : true;
        activities_config[className] = loadedConfigs.activity_constraints.activities_config[className]
        activities_config[className].enabled = isChecked
      });
    }

    const constraints = {};
    if (generalConstraints && generalConstraints.trim()) {
      constraints["global_constraints"] = generalConstraints.trim();
    }
    constraints["activities_config"] = activities_config;

    // Prepare final data to send
    const params = {
      character: character,
      skills: skills,
      constraints: constraints
    };

    try {
      const result = await sendCommand('save_onboarding_data', params);
      if (!result.success) {
        throw new Error(result.message || "Failed to save onboarding data");
      }

      successDiv.innerText = "Onboarding saved successfully!";
      successDiv.style.display = 'block';

      setTimeout(() => {
        closeOnboardingModal();
      }, 1500);

    } catch (e) {
      errorDiv.innerText = e.message;
      errorDiv.style.display = 'block';
    }
  }
})();
