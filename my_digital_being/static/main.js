/**********************************************
 * main.js
 * All the front-end logic except chart helpers
 **********************************************/

let ws = null;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;
const PAGE_SIZE = 50;
let currentOffset = 0;

// Trackers for config editing, chart data, etc.
let currentApiKeySetup = null;
let isEditMode = false;
let currentConfig = {};
// For chart
let activityChart = null;
let activityTypes = new Set();
let activityData = [];
let activityColorMap = new Map();

// Activity editing
let currentEditingActivity = null;
let isRawCodeMode = false;

document.addEventListener('DOMContentLoaded', () => {
  console.log('DOM loaded, connecting WebSocket...');
  connect();

  // Setup tab switching
  document.querySelectorAll('.tab-button').forEach(btn => {
    btn.addEventListener('click', () => {
      const tabName = btn.getAttribute('data-tab');
      showTab(tabName);
    });
  });
});

function showTab(tabName) {
  // Hide all tabs
  document.querySelectorAll('.tab-content').forEach(tab => {
    tab.classList.remove('active');
  });
  // Deactivate all tab buttons
  document.querySelectorAll('.tab-button').forEach(button => {
    button.classList.remove('active');
  });

  // Show the chosen tab
  const selectedTab = document.getElementById(`${tabName}-tab`);
  const selectedButton = document.querySelector(`[data-tab="${tabName}"]`);
  if (selectedTab && selectedButton) {
    selectedTab.classList.add('active');
    selectedButton.classList.add('active');

    // If user clicked 'History' tab, reload the history
    if (tabName === 'history') {
      reloadHistory();
    }
  }
}

function connect() {
  if (ws) {
    ws.close();
  }
  const protocol = (window.location.protocol === 'https:' ? 'wss:' : 'ws:');
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  console.log('Connecting to WebSocket:', wsUrl);
  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log('WebSocket connected');
    document.getElementById('status').textContent = 'Connected';
    document.getElementById('status').classList.add('connected');
    document.getElementById('status').classList.remove('disconnected');
    reconnectAttempts = 0;

    // Request initial data
    requestSystemStatus();
    getActivities();
    getConfig();
    refreshApiKeyStatus();
    refreshComposioStatus();

    // Also fetch the combined skill list
    refreshAllSkills();
  };

  ws.onclose = () => {
    console.log('WebSocket disconnected');
    document.getElementById('status').textContent = 'Disconnected';
    document.getElementById('status').classList.add('disconnected');
    document.getElementById('status').classList.remove('connected');
    ws = null;

    if (reconnectAttempts < maxReconnectAttempts) {
      reconnectAttempts++;
      const timeout = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
      console.log(`Attempting reconnect in ${timeout}ms...`);
      setTimeout(connect, timeout);
    }
  };

  ws.onerror = (error) => {
    console.error('WebSocket Error:', error);
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      console.log('Received message:', data);

      if (data.type === 'command_response') {
        const cmd = data.command;
        switch (cmd) {
          case 'get_system_status':
            displaySystemStatus(data.response);
            break;
          case 'get_activities':
            displayActivityConfigs(data.response);
            break;
          case 'get_config':
            displayConfig(data.response.config);
            break;
          case 'get_activity_history':
            displayActivityHistory(data.response);
            break;
          case 'update_config':
            getConfig();
            break;
          case 'configure_api_key':
            if (data.response.success) {
              refreshApiKeyStatus();
            }
            break;

          case 'get_api_key_status':
          case 'get_composio_integrations':
          case 'initiate_oauth':
          case 'get_composio_app_actions':
            console.log(`Handled command: ${cmd}`);
            break;

          case 'get_all_skills':
            console.log('All known skills =>', data.response.skills);
            displayAllSkills(data.response.skills);
            break;

          default:
            console.warn('Unrecognized command response:', cmd);
        }
      } else if (data.type === 'state_update') {
        console.log('State update:', data.data);
        updateRunningIndicator(data.data);
      }
    } catch (e) {
      console.error('Error processing message:', e);
    }
  };
}

function sendCommand(command, params = {}) {
  return new Promise((resolve, reject) => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      return reject('WebSocket not connected');
    }
    const listener = (evt) => {
      const msg = JSON.parse(evt.data);
      if (msg.type === 'command_response' && msg.command === command) {
        ws.removeEventListener('message', listener);
        resolve(msg.response);
      }
    };
    ws.addEventListener('message', listener);
    ws.send(JSON.stringify({
      type: 'command',
      command,
      params
    }));
  });
}
/*******************************************************
 * [ADDED] Pause/Resume/Stop/Start 
 *******************************************************/
async function pauseBeing() {
  try {
    const resp = await sendCommand('pause');
    if (resp.success) {
      alert(resp.message);
    } else {
      alert(`Failed to pause: ${resp.message}`);
    }
  } catch (e) {
    console.error(e);
    alert(e);
  }
}

async function resumeBeing() {
  try {
    const resp = await sendCommand('resume');
    if (resp.success) {
      alert(resp.message);
    } else {
      alert(`Failed to resume: ${resp.message}`);
    }
  } catch (e) {
    console.error(e);
    alert(e);
  }
}

async function stopLoop() {
  try {
    const resp = await sendCommand('stop_loop');
    if (resp.success) {
      alert(resp.message);
    } else {
      alert(`Failed to stop: ${resp.message}`);
    }
  } catch (e) {
    console.error(e);
    alert(e);
  }
}

async function startLoop() {
  try {
    const resp = await sendCommand('start_loop');
    if (resp.success) {
      alert(resp.message);
    } else {
      alert(`Failed to start: ${resp.message}`);
    }
  } catch (e) {
    console.error(e);
    alert(e);
  }
}

/*******************************************************
 * [ADDED] Update Running Indicator
 *******************************************************/
function updateRunningIndicator(stateData) {
  // we expect { paused: boolean, configured: boolean } etc.
  const runningEl = document.getElementById('runningIndicator');
  if (!runningEl) return;

  let text = 'Stopped';
  let cssClass = 'stopped';

  // If not configured, show that
  if (stateData.configured === false) {
    text = 'Not Configured';
    cssClass = 'not-configured';
  } else {
    // If configured, check paused
    if (stateData.paused) {
      text = 'Paused';
      cssClass = 'paused';
    } else {
      text = 'Running';
      cssClass = 'running';
    }
  }

  // Update text + class
  runningEl.textContent = text;

  // clear existing classes
  runningEl.classList.remove('running', 'paused', 'stopped', 'not-configured');
  runningEl.classList.add(cssClass);
}




/*******************************************************
 *               Basic commands to server
 *******************************************************/
function requestSystemStatus() {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: 'command', command: 'get_system_status' }));
}
function getActivities() {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: 'command', command: 'get_activities' }));
}
function getConfig() {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: 'command', command: 'get_config' }));
}

/*******************************************************
 *               Activity History
 *******************************************************/
function getActivityHistory(offset = 0) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({
    type: 'command',
    command: 'get_activity_history',
    params: { offset, limit: PAGE_SIZE }
  }));
}
function reloadHistory() {
  currentOffset = 0;
  getActivityHistory(0);
}
function loadMoreActivities() {
  currentOffset += PAGE_SIZE;
  getActivityHistory(currentOffset);
}

/*******************************************************
 *               Display: System Status
 *******************************************************/
function displaySystemStatus(data) {
  const systemStatusDiv = document.getElementById('systemStatusContent');
  if (!systemStatusDiv) return;

  const stateObj = data.state || {};
  const memory = data.memory || {};
  const skillsCfg = data.skills_config || {};

  let html = `
    ${renderStatusItem('Memory - Short Term', memory.short_term_count, 'Short-term memory items')}
    ${renderStatusItem('Memory - Long Term', memory.long_term_count, 'Long-term memory items')}
    ${renderStatusItem('Total Activities', memory.total_activities, 'Total # of activities performed')}
    <h4>Current State</h4>
  `;

  Object.entries(stateObj).forEach(([k, v]) => {
    if (k === 'last_activity_timestamp' && v) {
      v = new Date(v).toLocaleString();
    }
    html += renderStatusItem(k, v, `Current value of ${k}`);
  });
  systemStatusDiv.innerHTML = html;

  // Display skills config
  const skillsDiv = document.getElementById('skillsStatusContent');
  skillsDiv.innerHTML = '';
  const skillKeys = Object.keys(skillsCfg);
  if (!skillKeys.length) {
    skillsDiv.innerHTML = '<p>No skills configured</p>';
  } else {
    skillKeys.forEach(skill => {
      const cfg = skillsCfg[skill];
      skillsDiv.innerHTML += `
        <div class="status-item">
          <span class="status-label">${skill}</span>
          <span class="status-value">${cfg.enabled ? 'Enabled' : 'Disabled'}</span>
        </div>
      `;
    });
  }
}

/*******************************************************
 *               Display: Activity Configs
 *******************************************************/
function displayActivityConfigs(data) {
  const container = document.getElementById('activityConfigsContent');
  if (!container) return;
  container.innerHTML = `
    <button class="btn" onclick="openCreateActivityForm()">Create New Activity</button>
    <hr>
  `;

  const acts = data.activities || {};
  const keys = Object.keys(acts);
  if (!keys.length) {
    container.innerHTML += '<p>No activity configs found.</p>';
    return;
  }
  keys.forEach(k => {
    const cfg = acts[k];
    container.innerHTML += `
      <div class="status-item">
        <span class="status-label">${cfg.name}</span>
        <span class="status-value">
          Energy: ${cfg.energy_cost}<br>
          Cooldown: ${cfg.cooldown}s<br>
          Required Skills: ${(cfg.required_skills || []).join(', ')}<br>
          Last Execution: ${cfg.last_execution ? new Date(cfg.last_execution).toLocaleString() : 'Never'}
        </span>
        <button class="btn secondary" onclick="editActivity('${k}')">Edit</button>
      </div>
    `;
  });
}

/*******************************************************
 *    Switch between "nice form" or "raw code" for creation
 *******************************************************/
function openCreateActivityForm() {
  const editorDiv = document.getElementById('activityEditorContent');
  currentEditingActivity = null;
  isRawCodeMode = false;

  editorDiv.innerHTML = `
    <div id="activityFormContainer" style="margin-bottom:20px;">
      <h4 style="margin-top:0;">New Activity (Form Mode)</h4>

      <div class="form-group">
        <label>Activity Name</label>
        <input type="text" id="newActivityName" class="styled-input" placeholder="e.g. Nap" />
      </div>

      <div class="form-group">
        <label>Activity Description (optional)</label>
        <textarea id="newActivityDescription" class="styled-textarea" placeholder="Short docstring or comment..."></textarea>
      </div>

      <div class="form-group">
        <label>Energy Cost</label>
        <input type="number" id="newActivityEnergy" class="styled-input" value="0.2" step="0.1" />
      </div>

      <div class="form-group">
        <label>Cooldown (seconds)</label>
        <input type="number" id="newActivityCooldown" class="styled-input" value="300" />
      </div>

      <div class="form-group">
        <label>Required Skills (comma-separated)</label>
        <input type="text" id="newActivitySkills" class="styled-input" placeholder="skill1, skill2" />
      </div>

      <div style="margin-top:16px;">
        <button class="btn" onclick="submitActivityForm()">Create Activity</button>
        <button class="btn secondary" style="margin-left:10px;" onclick="switchToRawCode()">Or Create Raw Code</button>
      </div>

      <div id="activityFormError" class="error-msg" style="display:none;"></div>
      <div id="activityFormSuccess" class="success-msg" style="display:none;"></div>
    </div>
  `;
}

function switchToRawCode() {
  isRawCodeMode = true;
  const editorDiv = document.getElementById('activityEditorContent');
  editorDiv.innerHTML = `
    <h4 style="margin-top:0;">New Activity (Raw Code Mode)</h4>
    <div class="form-group">
      <label>New Activity Filename (e.g. 'activity_mything.py')</label>
      <input type="text" id="newActivityFilename" class="styled-input" placeholder="activity_something.py" />
    </div>

    <div class="form-group">
      <label>Initial Code:</label>
      <textarea id="newActivityCode" class="styled-textarea" style="height:300px; white-space:pre; font-family:monospace;"></textarea>
    </div>

    <div style="margin-top:16px;">
      <button class="btn" onclick="createNewActivityRaw()">Create</button>
      <button class="btn secondary" style="margin-left:10px;" onclick="openCreateActivityForm()">Back to Form</button>
    </div>
    <div id="rawCreateError" class="error-msg" style="display:none;"></div>
    <div id="rawCreateSuccess" class="success-msg" style="display:none;"></div>
  `;
}

/*******************************************************
 *    Submit from "nice" form
 *******************************************************/
async function submitActivityForm() {
  const nameInput = document.getElementById('newActivityName').value.trim();
  const desc = document.getElementById('newActivityDescription').value.trim();
  const energyVal = parseFloat(document.getElementById('newActivityEnergy').value);
  const cooldownVal = parseInt(document.getElementById('newActivityCooldown').value);
  const rawSkills = document.getElementById('newActivitySkills').value.trim();

  const errorDiv = document.getElementById('activityFormError');
  const successDiv = document.getElementById('activityFormSuccess');

  errorDiv.style.display = 'none';
  successDiv.style.display = 'none';
  errorDiv.innerText = '';
  successDiv.innerText = '';

  if (!nameInput) {
    errorDiv.innerText = "Activity Name is required.";
    errorDiv.style.display = 'block';
    return;
  }

  // Convert name "Nap" => "activity_nap.py" => class "NapActivity"
  const fileName = `activity_${nameInput.toLowerCase()}.py`;
  const className = nameInput.charAt(0).toUpperCase() + nameInput.slice(1) + "Activity";

  // Convert required skills into Python list
  let skillList = [];
  if (rawSkills) {
    skillList = rawSkills.split(',').map(s => s.trim()).filter(s => s);
  }

  // Build code from a template
  const docComment = desc ? `"""${desc}"""\n` : '';
  const codeTemplate = `
${docComment}import logging
from typing import Dict, Any
from framework.activity_decorator import activity, ActivityBase, ActivityResult

logger = logging.getLogger(__name__)

@activity(
name="${nameInput}",
energy_cost=${energyVal},
cooldown=${cooldownVal},
required_skills=${JSON.stringify(skillList)}
)
class ${className}(ActivityBase):
def __init__(self):
    super().__init__()

async def execute(self, shared_data) -> ActivityResult:
    try:
        # Example: This is the main logic for "${nameInput}" activity
        logger.info("Executing ${nameInput} activity")
        # TODO: Actual logic goes here
        return ActivityResult(success=True, data={"message":"${nameInput} done"})
    except Exception as e:
        logger.error(f"Error in ${nameInput} activity: {e}")
        return ActivityResult(success=False, error=str(e))
`.trim();

  try {
    const resp = await sendCommand('save_activity_code', {
      activity_name: fileName,
      new_code: codeTemplate
    });
    if (!resp.success) {
      throw new Error(resp.message || "Unknown error saving code");
    }
    successDiv.innerText = "Activity created successfully!";
    successDiv.style.display = 'block';

    // Hide the form after success
    setTimeout(() => {
      const container = document.getElementById('activityFormContainer');
      if (container) container.style.display = 'none';
      getActivities();
    }, 1500);

  } catch (e) {
    errorDiv.innerText = e.message;
    errorDiv.style.display = 'block';
  }
}


/*******************************************************
 *    Create new activity from raw code
 *******************************************************/
async function createNewActivityRaw() {
  const fileName = document.getElementById('newActivityFilename').value.trim();
  const code = document.getElementById('newActivityCode').value;
  const errorDiv = document.getElementById('rawCreateError');
  const successDiv = document.getElementById('rawCreateSuccess');
  errorDiv.style.display = 'none';
  successDiv.style.display = 'none';
  errorDiv.innerText = '';
  successDiv.innerText = '';

  if (!fileName || !code) {
    errorDiv.innerText = "Filename and code are required.";
    errorDiv.style.display = 'block';
    return;
  }
  try {
    const resp = await sendCommand('save_activity_code', {
      activity_name: fileName,
      new_code: code
    });
    if (!resp.success) {
      throw new Error(resp.message);
    }
    successDiv.innerText = "New activity created!";
    successDiv.style.display = 'block';

    // Hide after success
    setTimeout(() => {
      document.getElementById('activityEditorContent').innerHTML = '';
      getActivities();
    }, 1500);

  } catch (e) {
    errorDiv.innerText = e.message;
    errorDiv.style.display = 'block';
  }
}

/*******************************************************
 *    Editing existing activity (currently raw code only)
 *******************************************************/
async function editActivity(activityKey) {
  currentEditingActivity = activityKey;
  isRawCodeMode = true;
  try {
    const resp = await sendCommand('get_activity_code', { activity_name: activityKey + '.py' });
    if (!resp.success) {
      alert(`Failed to load activity code: ${resp.message}`);
      return;
    }

    const editorDiv = document.getElementById('activityEditorContent');
    editorDiv.innerHTML = `
      <h4 style="margin-top:0;">Editing Activity (Raw Code Mode)</h4>
      <textarea id="activityCodeTextarea" class="styled-textarea" style="height:300px; white-space:pre; font-family:monospace;"></textarea>
      <br>
      <button class="btn" onclick="saveActivityCode()">Save Code</button>
      <button class="btn secondary" style="margin-left:10px;" onclick="trySwitchToFormForExisting()">Switch to Form</button>
      <div id="editRawError" class="error-msg" style="display:none;"></div>
      <div id="editRawSuccess" class="success-msg" style="display:none;"></div>
    `;
    const codeArea = document.getElementById('activityCodeTextarea');
    codeArea.value = resp.code;
  } catch (e) {
    console.error(e);
    alert("Error loading activity code");
  }
}

function trySwitchToFormForExisting() {
  alert("Parsing an existing activity into form fields is not yet implemented. For new activities, use the create form. Otherwise, continue in raw code. Sorry!");
}

async function saveActivityCode() {
  const codeTextarea = document.getElementById('activityCodeTextarea');
  if (!codeTextarea) return;
  const newCode = codeTextarea.value.trim();
  const errorDiv = document.getElementById('editRawError');
  const successDiv = document.getElementById('editRawSuccess');
  errorDiv.style.display = 'none';
  successDiv.style.display = 'none';
  errorDiv.innerText = '';
  successDiv.innerText = '';

  try {
    const resp = await sendCommand('save_activity_code', {
      activity_name: currentEditingActivity + '.py',
      new_code: newCode
    });
    if (!resp.success) {
      throw new Error(resp.message);
    }
    successDiv.innerText = "Activity code updated!";
    successDiv.style.display = 'block';

    setTimeout(() => {
      document.getElementById('activityEditorContent').innerHTML = '';
      getActivities();
    }, 1500);

  } catch (e) {
    errorDiv.innerText = e.message;
    errorDiv.style.display = 'block';
  }
}

/*******************************************************
 *    Config editing
 *******************************************************/
function displayConfig(configObj) {
  currentConfig = configObj || {};
  const container = document.getElementById('configContent');
  if (!container) return;
  if (!Object.keys(currentConfig).length) {
    container.innerHTML = '<p>No config data available.</p>';
    return;
  }

  if (isEditMode) {
    container.innerHTML = Object.entries(currentConfig).map(([section, values]) => `
      <div class="config-section">
        <h4>${section}</h4>
        ${renderEditFields(section, values)}
      </div>
    `).join('');
  } else {
    container.innerHTML = Object.entries(currentConfig).map(([section, values]) => `
      <div class="config-section">
        <h4>${section}</h4>
        ${renderViewFields(section, values)}
      </div>
    `).join('');
  }
}
function toggleEditMode() {
  isEditMode = !isEditMode;
  const btn = document.getElementById('editButton');
  if (btn) btn.textContent = isEditMode ? 'Save' : 'Edit';
  displayConfig(currentConfig);
}
function updateConfigValue(section, key, value) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({
    type: 'command',
    command: 'update_config',
    params: { section, key, value }
  }));
}
function updateArrayItem(section, index, val) {
  if (currentConfig[section] && Array.isArray(currentConfig[section])) {
    currentConfig[section][index] = val;
    updateConfigValue(section, section, currentConfig[section]);
  }
}
function addArrayItem(section) {
  if (currentConfig[section] && Array.isArray(currentConfig[section])) {
    currentConfig[section].push('');
    updateConfigValue(section, section, currentConfig[section]);
  }
}
function removeArrayItem(section, idx) {
  if (currentConfig[section] && Array.isArray(currentConfig[section])) {
    currentConfig[section].splice(idx, 1);
    updateConfigValue(section, section, currentConfig[section]);
  }
}

/*******************************************************
 *    Display: Activity History
 *******************************************************/
function displayActivityHistory(data) {
  const entriesDiv = document.getElementById('activityEntries');
  const loadMoreBtn = document.getElementById('loadMoreButton');
  const checkboxesDiv = document.getElementById('activityCheckboxes');

  if (data.activities && data.activities.length) {
    // Append to existing activityData
    activityData = activityData.concat(data.activities);
    data.activities.forEach(a => activityTypes.add(a.activity_type));

    // Assign colors for each activity type
    Array.from(activityTypes).forEach(t => {
      if (!activityColorMap.has(t)) {
        getActivityColor(t);
      }
    });

    // Generate HTML for new activities
    const newEntriesHTML = data.activities.map(a => {
      const col = getActivityColor(a.activity_type);
      return `
        <div class="activity-entry" style="background:var(--section-bg); padding:10px; margin-bottom:10px; border-radius:8px;">
          <div>
            <span style="color:var(--text-secondary)">${new Date(a.timestamp).toLocaleString()}</span>
            <span style="color:${col}; font-weight:bold;">${a.activity_type}</span>
            ${a.success
          ? `<span style="color: var(--success-color)">✓ Success</span>`
          : `<span style="color: var(--error-color)">✗ Failed - ${a.error || ''}</span>`
        }
          </div>
          ${a.data ? `
            <div style="background:var(--card-bg);padding:8px;margin-top:8px;border-radius:4px;">
              <pre>${JSON.stringify(a.data, null, 2)}</pre>
            </div>
          ` : ''}
          ${a.metadata ? `
            <div style="background:var(--card-bg);padding:8px;margin-top:8px;border-radius:4px;">
              <pre>${JSON.stringify(a.metadata, null, 2)}</pre>
            </div>
          ` : ''}
        </div>
      `;
    }).join('');

    // Append new activities to the existing entries
    entriesDiv.insertAdjacentHTML('beforeend', newEntriesHTML);

    // Update checkboxes (ensure unique and sorted)
    checkboxesDiv.innerHTML = Array.from(activityTypes).sort().map(t => {
      const c = getActivityColor(t);
      return `
        <label style="margin-right:12px;">
          <input type="checkbox" value="${t}" checked onchange="updateActivityChart()">
          <span style="color:${c}">${t}</span>
        </label>
      `;
    }).join('');

    // Update the "Load More" button visibility
    loadMoreBtn.style.display = data.has_more ? 'block' : 'none';

    // Initialize or update chart
    if (activityChart) {
      updateActivityChart();
    } else {
      initializeActivityChart();
    }
  } else {
    if (currentOffset === 0) {
      // If no activities at all
      entriesDiv.innerHTML = '<p>No activities recorded yet.</p>';
    }
    // Hide the "Load More" button if no more activities
    loadMoreBtn.style.display = 'none';
  }
}


/*******************************************************
 *    Chart: initialization + update
 *******************************************************/
function getActivityColor(type) {
  if (activityColorMap.has(type)) {
    return activityColorMap.get(type);
  }
  const colors = [
    'rgb(75, 192, 192)',
    'rgb(255, 99, 132)',
    'rgb(54, 162, 235)',
    'rgb(255, 159, 64)',
    'rgb(153, 102, 255)',
    'rgb(255, 205, 86)',
    'rgb(201, 203, 207)'
  ];
  const nextColor = colors[activityColorMap.size % colors.length];
  activityColorMap.set(type, nextColor);
  return nextColor;
}

function initializeActivityChart() {
  const ctx = document.getElementById('activityChart').getContext('2d');
  activityChart = new Chart(ctx, {
    type: 'line',
    data: { datasets: [] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'nearest', axis: 'x', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: { color: '#fff', usePointStyle: true }
        },
        tooltip: { mode: 'index', intersect: false }
      },
      scales: {
        x: {
          type: 'time',
          time: { unit: 'day' },
          grid: { color: 'rgba(255,255,255,0.1)' },
          ticks: { color: '#fff', maxRotation: 45 }
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(255,255,255,0.1)' },
          ticks: { color: '#fff', stepSize: 1, precision: 0 }
        }
      },
      elements: {
        point: {
          radius: 4,
          hoverRadius: 6,
          borderWidth: 2,
          backgroundColor: 'rgba(255,255,255,0.8)'
        },
        line: {
          tension: 0.3,
          borderWidth: 2,
          fill: true,
          backgroundColor: function (ctx) {
            const chart = ctx.chart;
            const { ctx: chartCtx, chartArea } = chart;
            if (!chartArea) return null;
            const color = ctx.dataset.borderColor;
            const gradient = chartCtx.createLinearGradient(0, chartArea.bottom, 0, chartArea.top);
            gradient.addColorStop(0, 'rgba(0,0,0,0)');
            gradient.addColorStop(1, color.replace('rgb', 'rgba').replace(')', ',0.2)'));
            return gradient;
          }
        }
      }
    }
  });
  updateActivityChart();
}

function updateActivityChart() {
  if (!activityChart || !activityData) return;

  const timeRange = document.getElementById('timeRange').value;
  const selectedActivities = new Set(
    Array.from(document.querySelectorAll('#activityCheckboxes input:checked'))
      .map(c => c.value)
  );

  // We'll bucket the activities by period
  const activities = {};
  const now = new Date();
  let startTime;
  switch (timeRange) {
    case 'hourly':
      startTime = new Date(now.getTime() - 24 * 3600_000);
      break;
    case 'daily':
      startTime = new Date(now.getTime() - 7 * 24 * 3600_000);
      break;
    case 'weekly':
      startTime = new Date(now.getTime() - 4 * 7 * 24 * 3600_000);
      break;
    case 'monthly':
      startTime = new Date(now.getTime() - 12 * 30 * 24 * 3600_000);
      break;
    default:
      startTime = new Date(now.getTime() - 7 * 24 * 3600_000);
  }

  // Count occurrences in each period bucket
  activityData.forEach(act => {
    if (!selectedActivities.has(act.activity_type)) return;
    const ts = new Date(act.timestamp);
    if (ts < startTime) return;
    // Use getPeriodKey from chart-utils
    const periodKey = getPeriodKey(ts, timeRange);
    if (!activities[act.activity_type]) {
      activities[act.activity_type] = {};
    }
    activities[act.activity_type][periodKey] =
      (activities[act.activity_type][periodKey] || 0) + 1;
  });

  // We'll generate a list of all possible period keys
  const allPeriods = getAllPeriods(startTime, now, timeRange);

  // Build the datasets
  const datasets = Object.keys(activities).sort().map(actType => {
    const c = getActivityColor(actType);
    const dataPoints = allPeriods.map(pk => ({
      x: getPeriodDate(pk, timeRange),
      y: activities[actType][pk] || 0
    }));
    return {
      label: actType,
      data: dataPoints,
      borderColor: c,
      backgroundColor: c.replace('rgb', 'rgba').replace(')', ',0.2)'),
      borderWidth: 2,
      tension: 0.3
    };
  });

  activityChart.data.datasets = datasets;
  // Set x-axis time unit
  activityChart.options.scales.x.time.unit = (
    timeRange === 'hourly' ? 'hour' :
      timeRange === 'daily' ? 'day' :
        timeRange === 'weekly' ? 'week' :
          'month'
  );

  activityChart.update();
}

/*******************************************************
 *               Rendering helpers
 *******************************************************/
function renderStatusItem(label, value, tooltip = '') {
  return `
    <div class="status-item">
      <span class="status-label">
        ${label}
        <span class="info-icon">
          <span class="tooltip">${tooltip}</span>
        </span>
      </span>
      <span class="status-value ${typeof value}">${formatValue(value)}</span>
    </div>
  `;
}
function formatValue(val) {
  if (Array.isArray(val)) {
    return val.map(v => `<span class="array-value">${v}</span>`).join('');
  }
  if (typeof val === 'object' && val !== null) {
    return Object.entries(val).map(([k, v]) => `${k}: ${v}`).join('<br>');
  }
  if (typeof val === 'boolean') {
    return val ? '✓ Enabled' : '✗ Disabled';
  }
  return val;
}
function renderViewFields(section, values) {
  if (typeof values !== 'object' || values === null) {
    return renderStatusItem(section, values);
  }
  if (Array.isArray(values)) {
    return `
      <div class="status-item">
        <span class="status-label">
          ${section}
          <span class="info-icon">i
            <span class="tooltip">Value of ${section}</span>
          </span>
        </span>
        <span class="status-value array">
          ${values.map(v => `<span class="array-value">${v}</span>`).join(' ')}
        </span>
      </div>
    `;
  }
  const subFields = Object.entries(values).map(([k, v]) => {
    if (typeof v === 'object' && v !== null) {
      return `
        <div class="nested-section">
          <h5 class="nested-title">${k}</h5>
          ${renderViewFields(k, v)}
        </div>
      `;
    } else {
      return renderStatusItem(k, v);
    }
  }).join('');

  return `
    <div class="status-item" style="flex-direction:column; align-items:flex-start;">
      <span class="param-label" style="margin-bottom:8px;">
        ${section}
        <span class="info-icon">i
          <span class="tooltip">Value of ${section}</span>
        </span>
      </span>
      <div style="width:100%; margin-top:8px;">
        ${subFields}
      </div>
    </div>
  `;
}
function renderEditFields(section, values) {
  if (typeof values !== 'object' || values === null) {
    return `
      <div class="edit-field">
        <label>${section}</label>
        <input type="text" value="${values}" onchange="updateConfigValue('${section}', '${section}', this.value)">
      </div>
    `;
  }
  if (Array.isArray(values)) {
    return `
      <div class="edit-field">
        <label>${section}</label>
        <div>
          ${values.map((val, idx) => `
            <div style="margin-bottom:4px; display:flex; gap:8px; align-items:center;">
              <input type="text" value="${val}" onchange="updateConfigValue('${section}', ${idx}, this.value)">
              <button style="background: var(--error-color); color:#fff;"
                onclick="removeArrayItem('${section}', ${idx})">×</button>
            </div>
          `).join('')}
          <button style="background: var(--success-color); color: var(--background-dark); margin-top:6px;"
            onclick="addArrayItem('${section}')">Add Item</button>
        </div>
      </div>
    `;
  }
  return Object.entries(values).map(([key, val]) => {
    if (typeof val === 'object' && val !== null) {
      return `
        <div class="edit-field">
          <label>${key}</label>
          <div style="margin-left:20px; padding-left:12px; border-left:2px solid var(--primary-color)">
            ${renderEditFields(`${section}.${key}`, val)}
          </div>
        </div>
      `;
    }
    if (typeof val === 'boolean') {
      return `
        <div class="edit-field">
          <label>${key}</label>
          <select onchange="updateConfigValue('${section}', '${key}', (this.value==='true'))">
            <option value="true" ${val ? 'selected' : ''}>Enabled</option>
            <option value="false" ${!val ? 'selected' : ''}>Disabled</option>
          </select>
        </div>
      `;
    }
    if (typeof val === 'number') {
      return `
        <div class="edit-field">
          <label>${key}</label>
          <input type="number" value="${val}" onchange="updateConfigValue('${section}', '${key}', Number(this.value))">
        </div>
      `;
    }
    return `
      <div class="edit-field">
        <label>${key}</label>
        <input type="text" value="${val}" onchange="updateConfigValue('${section}', '${key}', this.value)">
      </div>
    `;
  }).join('');
}


/*******************************************************
 *    API Key Management
 *******************************************************/
async function refreshApiKeyStatus() {
  try {
    const res = await sendCommand('get_api_key_status');
    if (!res.success) throw new Error(res.error || 'Failed to get API key status');
    const container = document.getElementById('apiKeyStatus');
    if (res.skills) {
      container.innerHTML = Object.entries(res.skills).map(([skill, info]) => `
        <div class="dashboard-card">
          <h4>${info.display_name || skill}</h4>
          <div>
            ${Object.entries(info.required_keys || {}).map(([keyName, isConfigured]) => `
              <div class="status-item" style="justify-content:space-between;">
                <span class="status-label">${keyName}</span>
                <span class="status-value ${isConfigured ? 'true' : 'false'}">
                  ${isConfigured ? '✓ Configured' : 'Not Configured'}
                </span>
                ${!isConfigured ? `
                  <button class="configure-key-btn" onclick="handleConfigureKey('${skill}','${keyName}')">Configure</button>
                ` : ''}
              </div>
            `).join('')}
          </div>
        </div>
      `).join('');
    } else {
      container.innerHTML = '<p>No skills found for API key management.</p>';
    }
  } catch (e) {
    console.error('Error refreshing API key status:', e);
  }
}
function handleConfigureKey(skillName, keyName) {
  currentApiKeySetup = { skillName, keyName };
  const modal = document.getElementById('apiKeyModal');
  document.getElementById('apiKeyModalMessage').textContent =
    `Please provide the API key for ${keyName} (${skillName})`;
  document.getElementById('apiKeyInput').value = '';
  modal.style.display = 'block';
}
function closeApiKeyModal() {
  document.getElementById('apiKeyModal').style.display = 'none';
  currentApiKeySetup = null;
}
async function submitApiKey() {
  if (!currentApiKeySetup) return;
  const apiKey = document.getElementById('apiKeyInput').value.trim();
  if (!apiKey) {
    alert('Please provide an API key.');
    return;
  }
  try {
    const res = await sendCommand('configure_api_key', {
      skill_name: currentApiKeySetup.skillName,
      key_name: currentApiKeySetup.keyName,
      api_key: apiKey
    });
    if (!res.success) throw new Error(res.message || 'Failed to configure API key');
    closeApiKeyModal();
    refreshApiKeyStatus();
  } catch (e) {
    console.error('Failed to configure API key:', e);
    alert('Failed: ' + e.message);
  }
}

/*******************************************************
 *  Composio / OAuth (SIMPLE)
 *******************************************************/
async function refreshComposioStatus() {
  try {
    const res = await sendCommand('get_composio_integrations');
    if (!res.success) throw new Error(res.error || 'Failed to get Composio integrations');
    const container = document.getElementById('composioIntegrations');
    if (res.composio_integrations) {
      container.innerHTML = res.composio_integrations.map(integration => `
        <div class="dashboard-card" data-display-name="${integration.display_name || integration.name}">
          <h4>${integration.display_name || integration.name}</h4>
          <div class="status-item" style="justify-content:space-between;">
            <span class="key-name">Connection Status</span>
            <span class="status-value ${integration.connected ? 'true' : 'false'}">
              ${integration.connected ? '✓ Connected' : 'Not Connected'}
            </span>
            ${!integration.connected ? `
              <div class="connect-buttons" data-app="${integration.name}">
                <button class="btn secondary" onclick="checkAuthMethods('${integration.name}')">Connect Account</button>
              </div>
            ` : ''}
          </div>
        </div>
      `).join('');
    } else {
      container.innerHTML = '<p>No composio integrations found</p>';
    }
    filterComposioIntegrations();
  } catch (e) {
    console.error('Error refreshing Composio status:', e);
    alert('Error: ' + e.message);
  }
}
function filterComposioIntegrations() {
  const searchTerm = document.getElementById('composioSearch').value.toLowerCase();
  const items = document.querySelectorAll('#composioIntegrations .dashboard-card');
  items.forEach(item => {
    const name = item.querySelector('h4').textContent.toLowerCase();
    const disp = item.getAttribute('data-display-name')?.toLowerCase() || '';
    if (name.includes(searchTerm) || disp.includes(searchTerm)) {
      item.style.display = '';
    } else {
      item.style.display = 'none';
    }
  });
}

async function checkAuthMethods(appName) {
  try {
    const authRes = await sendCommand('get_auth_schemes', { app_name: appName });
    if (!authRes.success) {
      throw new Error(authRes.error || 'Failed to get auth schemes');
    }

    const authModes = authRes.auth_modes || [];
    const buttonContainer = document.querySelector(`[data-app="${appName}"]`);
    
    if (!buttonContainer) return;

    let buttonsHtml = '<div class="auth-methods">';
    
    if (authModes.includes('OAUTH2') || authModes.includes('OAUTH1')) {
      buttonsHtml += `
        <button class="btn primary" onclick="startOAuthFlow('${appName}')">
          Connect with OAuth
        </button>
      `;
    }
    
    if (authModes.includes('API_KEY')) {
      buttonsHtml += `
        <button class="btn secondary" onclick="startApiKeyFlow('${appName}')">
          Connect with API Key
        </button>
      `;
    }
    
    buttonsHtml += '</div>';
    buttonContainer.innerHTML = buttonsHtml;
  } catch (e) {
    console.error('Failed to get auth methods:', e);
    alert(e.message);
  }
}

async function startOAuthFlow(appName) {
  try {
    const baseUrl = window.location.origin;
    const res = await sendCommand('initiate_oauth', {
      app_name: appName,
      base_url: baseUrl
    });

    if (!res.success) {
      throw new Error(res.error || 'Failed to initiate OAuth');
    }
    if (res.redirect_url) {
      window.location.href = res.redirect_url;
    } else {
      throw new Error('No redirect URL provided');
    }
  } catch (e) {
    console.error('Failed to start OAuth flow:', e);
    alert(e.message);
  }
}

async function startApiKeyFlow(appName) {
  try {
    const authRes = await sendCommand('get_auth_schemes', { app_name: appName });
    if (!authRes.success) {
      throw new Error(authRes.error || 'Failed to get auth schemes');
    }

    showApiKeyForm(appName, authRes.api_key_details);
  } catch (e) {
    console.error('Failed to start API key flow:', e);
    alert(e.message);
  }
}

function showApiKeyForm(appName, keyDetails) {
  const modal = document.getElementById('apiKeyModal');
  const messageEl = document.getElementById('apiKeyModalMessage');

  modal.dataset.appName = appName;

  // Create form with all required fields
  const fields = keyDetails?.fields || [];
  messageEl.innerHTML = `
    <div class="api-key-details">
      <h4>${appName} API Key Setup</h4>
      <div id="apiKeyFields">
        ${fields.map(field => `
          <div class="field-group" style="margin-bottom: 15px;">
            <label for="field_${field.name}">${field.display_name}${field.required ? ' *' : ''}</label>
            <input type="text" 
                   id="field_${field.name}" 
                   class="styled-input" 
                   placeholder="${field.display_name}"
                   data-field-name="${field.name}"
                   data-required="${field.required}">
            <p class="field-description">${field.description || ''}</p>
          </div>
        `).join('')}
      </div>
    </div>
  `;

  const validationDiv = document.createElement('div');
  validationDiv.id = 'apiKeyValidation';
  validationDiv.className = 'validation-message';
  messageEl.appendChild(validationDiv);

  modal.style.display = 'block';

  window.submitApiKey = async function () {
    const validationDiv = document.getElementById('apiKeyValidation');
    const fields = document.querySelectorAll('#apiKeyFields input');
    
    const values = {};
    
    for (const field of fields) {
      const value = field.value.trim();
      const fieldName = field.dataset.fieldName;
      const required = field.dataset.required === 'true';
      
      if (required && !value) {
        validationDiv.textContent = `${field.placeholder} is required`;
        validationDiv.className = 'validation-message error';
        return;
      }
      
      if (value) { 
        values[fieldName] = value;
      }
    }

    try {
      const submitBtn = document.querySelector('#apiKeyModal .primary');
      submitBtn.textContent = 'Connecting...';
      submitBtn.disabled = true;

      console.log('Connecting with API key params:', values);

      const res = await sendCommand('initiate_api_key_connection', {
        app_name: appName,
        connection_params: values
      });

      if (!res.success) {
        throw new Error(res.error || res.message || 'Failed to connect with API key');
      }

      validationDiv.textContent = 'Connection successful!';
      validationDiv.className = 'validation-message success';

      setTimeout(() => {
        closeApiKeyModal();
        refreshComposioStatus();
      }, 1500);

    } catch (e) {
      console.error('Failed to connect with API key:', e);
      validationDiv.textContent = e.message;
      validationDiv.className = 'validation-message error';

      const submitBtn = document.querySelector('#apiKeyModal .primary');
      submitBtn.textContent = 'Try Again';
      submitBtn.disabled = false;
    }
  };
}

const style = document.createElement('style');
style.textContent = `
  .api-key-details {
    margin-bottom: 20px;
  }
  .api-key-details h4 {
    margin: 0 0 10px 0;
    color: var(--primary-color);
  }
  .api-key-details .description {
    margin: 0 0 15px 0;
    color: var(--text-secondary);
  }
  .field-group {
    margin-bottom: 15px;
  }
  .field-group label {
    display: block;
    margin-bottom: 5px;
    color: var(--text-primary);
  }
  .field-group input {
    width: 100%;
    padding: 8px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--input-bg);
    color: var(--text-primary);
  }
  .field-description {
    margin: 5px 0 0 0;
    font-size: 0.9em;
    color: var(--text-secondary);
  }
  .validation-message {
    margin-top: 10px;
    padding: 8px;
    border-radius: 4px;
    font-size: 0.9em;
  }
  .validation-message.error {
    background: var(--error-bg);
    color: var(--error-color);
  }
  .validation-message.warning {
    background: var(--warning-bg);
    color: var(--warning-color);
  }
  .validation-message.success {
    background: var(--success-bg);
    color: var(--success-color);
  }
  .auth-methods {
    display: flex;
    gap: 8px;
  }
  .auth-methods button {
    white-space: nowrap;
  }
`;
document.head.appendChild(style);

async function testGetActionsForTwitter() {
  try {
    const res = await sendCommand('get_composio_app_actions', { app_name: 'TWITTER' });
    console.log("TWITTER actions =>", res);
    alert(JSON.stringify(res, null, 2));
  } catch (e) {
    console.error("Failed to get actions for Twitter", e);
  }
}

window.initiateOAuth = startOAuthFlow;
window.closeApiKeyModal = closeApiKeyModal;
window.submitApiKey = submitApiKey;
window.toggleEditMode = toggleEditMode;

/*******************************************************
 * Combine + Display All Skills
 *******************************************************/
async function refreshAllSkills() {
  try {
    const res = await sendCommand('get_all_skills');
    if (!res.success) {
      console.error('Failed to get all skills:', res.message);
      return;
    }
    displayAllSkills(res.skills || []);
  } catch (e) {
    console.error('Error in refreshAllSkills:', e);
  }
}

function displayAllSkills(skills) {
  const container = document.getElementById('skillsStatusContent');
  if (!container) return;

  if (!skills.length) {
    container.innerHTML = '<p>No known skills found.</p>';
    return;
  }

  let html = '';

  skills.forEach(skill => {
    console.log('[displayAllSkills] skill object =>', skill);

    const skillName = skill.skill_name || '(no skill_name)';
    const enabled = skill.enabled ? '✓' : '✗';
    const metaObj = skill.metadata || {};

    const composioApp = metaObj.composio_app || '(none)';
    const composioAction = metaObj.composio_action || '(none)';

    html += `
      <div class="status-item" style="flex-direction: column; align-items: flex-start;">
        <span style="font-weight: bold; margin-bottom: 4px;">${skillName}</span>
        <div style="margin-left: 8px;">
          <p style="margin:2px 0;">Enabled: ${enabled}</p>
          <p style="margin:2px 0;">(Raw skill object in console)</p>

          <!-- If you want to show some Composio fields explicitly: -->
          <p style="margin:2px 0;"><strong>composio_app:</strong> ${composioApp}</p>
          <p style="margin:2px 0;"><strong>composio_action:</strong> ${composioAction}</p>

          ${
      metaObj
        ? `<pre style="background: var(--card-bg); padding: 4px; border-radius: 4px; margin: 4px 0;">
                   ${JSON.stringify(metaObj, null, 2)}
                 </pre>`
        : ''
      }
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
}

