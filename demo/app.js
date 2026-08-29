const els = {
  backendUrl: document.getElementById('backendUrl'),
  childId: document.getElementById('childId'),
  scenario: document.getElementById('scenario'),
  signalType: document.getElementById('signalType'),
  targetLevel: document.getElementById('targetLevel'),
  customControls: document.getElementById('customControls'),
  storyControls: document.getElementById('storyControls'),
  modeRadios: document.querySelectorAll('input[name="demoMode"]'),
  ladderPreview: document.getElementById('ladderPreview'),
  resetSession: document.getElementById('resetSession'),
  stepBtn: document.getElementById('stepBtn'),
  autoplayBtn: document.getElementById('autoplayBtn'),
  restartBtn: document.getElementById('restartBtn'),
  sessionId: document.getElementById('sessionId'),
  chatLog: document.getElementById('chatLog'),
  scoreFill: document.getElementById('scoreFill'),
  scoreVal: document.getElementById('scoreVal'),
  tierBadge: document.getElementById('tierBadge'),
  signalLog: document.getElementById('signalLog'),
  alertCard: document.getElementById('alertCard'),
  nudgeToast: document.getElementById('nudgeToast'),
  nudgeToastText: document.getElementById('nudgeToastText'),
  nudgeToastClose: document.getElementById('nudgeToastClose')
};

function currentMode() {
  return document.querySelector('input[name="demoMode"]:checked')?.value || 'custom';
}

// Same copy as extension/src/background/service-worker.js's
// NUDGE_MESSAGE, so the demo shows exactly what the child would see.
const NUDGE_MESSAGE = 'Heads up — sites like this often ask for personal info. Be careful before sharing anything.';
let nudgeTimer = null;

function showNudgeToast(message) {
  clearTimeout(nudgeTimer);
  els.nudgeToastText.textContent = message;
  els.nudgeToast.classList.remove('hidden');
  nudgeTimer = setTimeout(hideNudgeToast, 10000);
}
function hideNudgeToast() {
  els.nudgeToast.classList.add('hidden');
  clearTimeout(nudgeTimer);
}
els.nudgeToastClose.addEventListener('click', hideNudgeToast);

let state = {
  sessionId: null,
  stepIndex: 0,
  cumulativeScore: 0,
  autoplaying: false
};

function newSessionId() {
  return 'demo_' + Math.random().toString(36).slice(2, 10);
}

function populateScenarios() {
  els.scenario.innerHTML = '';
  for (const [key, scenario] of Object.entries(SCENARIOS)) {
    const opt = document.createElement('option');
    opt.value = key;
    opt.textContent = scenario.label;
    els.scenario.appendChild(opt);
  }
}

function currentScenario() {
  if (currentMode() === 'custom') {
    return buildCustomScenario(els.signalType.value, els.targetLevel.value);
  }
  return SCENARIOS[els.scenario.value];
}

function renderLadderPreview() {
  const scenario = currentScenario();
  els.ladderPreview.classList.remove('hidden');

  let html = `<div class="lp-title">${escapeHtml(scenario.label)} — ${escapeHtml(scenario.description)}</div>`;
  scenario.steps.forEach((step, i) => {
    const weightMatch = findStepWeight(step);
    const weightText = weightMatch === 0 ? '0' : `+${weightMatch}`;
    html += `
      <div class="lp-row pending" data-step="${i}">
        <div class="lp-step-num">${i + 1}</div>
        <div class="lp-content">${escapeHtml(truncate(step.content, 70))}</div>
        <div class="lp-weight ${weightMatch === 0 ? 'zero' : 'positive'}">${weightText}</div>
        <div class="lp-cumulative">score →</div>
      </div>`;
  });
  els.ladderPreview.innerHTML = html;
}

// Looks up a step's declared weight from the ladders/safe-steps tables
// (falls back to 0) purely for the preview display — the ACTUAL score
// always comes back from the real backend response, this is just so
// you can see what to expect before pressing Step.
function findStepWeight(step) {
  const safe = (SAFE_STEPS[step.signalType] || []).find(s => s.content === step.content);
  if (safe) return 0;
  const rung = (ESCALATION_LADDERS[step.signalType] || []).find(s => s.content === step.content);
  if (rung) return rung.weight;
  return 0;
}

function markLadderStepDone(index) {
  const row = els.ladderPreview.querySelector(`.lp-row[data-step="${index}"]`);
  if (row) {
    row.classList.remove('pending');
    row.classList.add('done');
  }
}

function resetSession() {
  state.sessionId = newSessionId();
  els.sessionId.textContent = state.sessionId;
}

function restartScenario() {
  state.stepIndex = 0;
  state.cumulativeScore = 0;
  els.chatLog.innerHTML = '';
  els.signalLog.innerHTML = '';
  els.alertCard.classList.add('hidden');
  els.alertCard.innerHTML = '';
  hideNudgeToast();
  updateScoreUI(0, null);
  resetSession();
  renderLadderPreview();
}

function applyMode() {
  const mode = currentMode();
  els.customControls.classList.toggle('hidden', mode !== 'custom');
  els.storyControls.classList.toggle('hidden', mode !== 'story');
  restartScenario();
}

function updateScoreUI(score, tier) {
  els.scoreVal.textContent = score;
  const pct = Math.min(100, Math.round((score / 8) * 100));
  els.scoreFill.style.width = `${pct}%`;

  els.tierBadge.className = 'tier-badge tier-' + (tier ?? 0);
  const labels = { 0: 'No tier', 1: 'Tier 1 — logged silently', 2: 'Tier 2 — nudge shown to child', 3: 'Tier 3 — parent alerted' };
  els.tierBadge.textContent = labels[tier ?? 0];
}

function renderChatMessage(speaker, text, note) {
  const bubble = document.createElement('div');
  bubble.className = `bubble ${speaker}`;
  bubble.innerHTML = `<div class="who">${speaker === 'stranger' ? 'Unknown contact (fictional)' : speaker === 'child' ? 'Child (this device)' : 'System'}</div><div class="text"></div>${note ? `<div class="note">${escapeHtml(note)}</div>` : ''}`;
  bubble.querySelector('.text').textContent = text;
  els.chatLog.appendChild(bubble);
  els.chatLog.scrollTop = els.chatLog.scrollHeight;
}

function renderSignalLogEntry(step, response) {
  const row = document.createElement('div');
  row.className = 'signal-row';
  const weight = response?.outcome?.score != null ? null : null;
  const status = response?.blocked ? 'BLOCKED' : (response?.status || 'sent');
  row.innerHTML = `
    <div class="signal-type">${step.signalType}</div>
    <div class="signal-content">${escapeHtml(truncate(step.content, 60))}</div>
    <div class="signal-status">${escapeHtml(status)}</div>
  `;
  els.signalLog.appendChild(row);
  els.signalLog.scrollTop = els.signalLog.scrollHeight;
}

function renderAlertCard(outcome) {
  if (!outcome || !outcome.ai_explanation) return;
  const exp = outcome.ai_explanation;
  els.alertCard.classList.remove('hidden');
  els.alertCard.innerHTML = `
    <div class="alert-header">Tier 3 alert — what the parent would see</div>
    <div class="alert-field"><strong>What happened:</strong> ${escapeHtml(exp.what_happened || '')}</div>
    <div class="alert-field"><strong>Why it matters:</strong> ${escapeHtml(exp.why_it_matters || '')}</div>
    <div class="alert-field"><strong>Recommended action:</strong> ${escapeHtml(exp.recommended_action || '')}</div>
    <div class="alert-severity">Severity: ${escapeHtml(exp.severity_label || '')}</div>
  `;
}

function escapeHtml(v) {
  return String(v ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
function truncate(v, n) {
  const s = String(v ?? '');
  return s.length > n ? s.slice(0, n) + '…' : s;
}

async function sendSignal(step) {
  const baseUrl = els.backendUrl.value.replace(/\/$/, '');
  const childId = els.childId.value.trim();
  if (!baseUrl || !childId) {
    alert('Enter a backend URL and Child ID first.');
    return null;
  }

  const body = {
    child_id: childId,
    session_id: state.sessionId,
    signal_type: step.signalType,
    content: step.content,
    url: step.signalType === 'url_visit' ? step.content : null,
    timestamp: new Date().toISOString()
  };

  try {
    const res = await fetch(`${baseUrl}/api/signals`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    return await res.json();
  } catch (e) {
    return { status: 'error', error: e.message };
  }
}

async function runStep() {
  const scenario = currentScenario();
  if (!scenario || state.stepIndex >= scenario.steps.length) return false;

  const step = scenario.steps[state.stepIndex];
  renderChatMessage(step.speaker, step.content, step.note);
  markLadderStepDone(state.stepIndex);

  const response = await sendSignal(step);
  renderSignalLogEntry(step, response || {});

  const outcome = response?.outcome;
  if (outcome && typeof outcome.score === 'number') {
    updateScoreUI(outcome.score, outcome.tier);
    // Tier 2 = in-browser nudge shown to the child (outcome.nudge is
    // true, see core/correlation_engine.py) — this was never rendered
    // here, so tier-2 steps silently did nothing but flip the badge.
    if (outcome.tier === 2 && outcome.nudge) {
      showNudgeToast(NUDGE_MESSAGE);
      renderChatMessage('system', 'Nudge shown to child (not sent to parent)', 'In-browser toast — see bottom-right');
    } else if (outcome.tier === 3) {
      hideNudgeToast();
      renderAlertCard(outcome);
    }
  }

  state.stepIndex++;
  return state.stepIndex < scenario.steps.length;
}

els.stepBtn.addEventListener('click', () => { runStep(); });

els.autoplayBtn.addEventListener('click', async () => {
  if (state.autoplaying) return;
  state.autoplaying = true;
  els.autoplayBtn.textContent = 'Playing…';
  let more = true;
  while (more) {
    more = await runStep();
    await new Promise(r => setTimeout(r, 1400));
  }
  state.autoplaying = false;
  els.autoplayBtn.textContent = 'Auto-play ▶▶';
});

els.resetSession.addEventListener('click', () => {
  resetSession();
  renderChatMessage('system', 'New session started — score resets.', null);
});

els.restartBtn.addEventListener('click', restartScenario);
els.scenario.addEventListener('change', restartScenario);
els.signalType.addEventListener('change', restartScenario);
els.targetLevel.addEventListener('change', restartScenario);
els.modeRadios.forEach(r => r.addEventListener('change', applyMode));

populateScenarios();
applyMode();
