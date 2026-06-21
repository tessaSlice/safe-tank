// ── Demo data ─────────────────────────────────────────────────────────────────
const DEMO_FRAMES = [
  { vibration: false, humidity: 55.2, temperature: 23.1, gas: 180 },
  { vibration: false, humidity: 56.8, temperature: 23.4, gas: 210 },
  { vibration: true,  humidity: 57.1, temperature: 23.6, gas: 290 },
  { vibration: false, humidity: 58.3, temperature: 24.0, gas: 320 },
  { vibration: false, humidity: 60.0, temperature: 24.5, gas: 400 },
  { vibration: false, humidity: 61.4, temperature: 25.1, gas: 530 },
  { vibration: true,  humidity: 63.9, temperature: 26.0, gas: 620 },
];
let demoIndex = 0;

// ── State ─────────────────────────────────────────────────────────────────────
let currentData = {};
let waitingForResponse = false;
let chatHasContent = false;

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("query-input").addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      sendQuery();
    }
  });

  if (CONFIG.liveMode) {
    setBadge("connecting");
    startPolling();
  } else {
    setBadge("demo");
    runDemo();
  }
});

// ── Demo mode ─────────────────────────────────────────────────────────────────
function runDemo() {
  function tick() {
    const data = DEMO_FRAMES[demoIndex % DEMO_FRAMES.length];
    currentData = data;
    updateSensors(data);
    updateTimestamp();
    demoIndex++;
    setTimeout(tick, 1800);
  }
  tick();
}

// ── Live mode: poll GET /sensors ──────────────────────────────────────────────
async function startPolling() {
  async function poll() {
    try {
      const res = await fetch(`${CONFIG.serverUrl}/sensors`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      currentData = data;
      updateSensors(data);
      updateTimestamp();
      setBadge("connected");
    } catch (e) {
      setBadge("disconnected");
      console.warn("Sensor poll failed:", e.message);
    }
  }

  await poll();
  setInterval(poll, CONFIG.pollIntervalMs);
}

// ── Sensor rendering ──────────────────────────────────────────────────────────
function updateSensors(data) {
  let alertCount = 0;

  if ("vibration" in data) {
    const active = Boolean(data.vibration);
    const card = document.getElementById("card-vibration");
    document.getElementById("val-vibration").textContent = active ? "YES" : "NO";
    card.classList.toggle("vibrating", active);
    setStatus(card, document.getElementById("dot-vibration"), active ? "danger" : "ok");
    if (active) alertCount++;
  }

  if ("humidity" in data) {
    const v = parseFloat(data.humidity);
    document.getElementById("val-humidity").textContent = v.toFixed(1);
    const level = getLevel("humidity", v);
    setStatus(document.getElementById("card-humidity"), document.getElementById("dot-humidity"), level);
    setGauge("gauge-humidity", v, 0, 100);
    if (level !== "ok") alertCount++;
  }

  if ("temperature" in data) {
    const v = parseFloat(data.temperature);
    document.getElementById("val-temperature").textContent = v.toFixed(1);
    const level = getLevel("temperature", v);
    setStatus(document.getElementById("card-temperature"), document.getElementById("dot-temperature"), level);
    setGauge("gauge-temperature", v, -10, 60);
    if (level !== "ok") alertCount++;
  }

  if ("gas" in data) {
    const v = parseFloat(data.gas);
    document.getElementById("val-gas").textContent = v.toFixed(0);
    const level = getLevel("gas", v);
    setStatus(document.getElementById("card-gas"), document.getElementById("dot-gas"), level);
    setGauge("gauge-gas", v, 0, 1000);
    if (level !== "ok") alertCount++;
  }

  updateOverallStatus(alertCount);
}

function getLevel(key, value) {
  const t = CONFIG.thresholds[key];
  if (!t) return "ok";
  if (value >= t.danger) return "danger";
  if (value >= t.warn)   return "warn";
  return "ok";
}

function setStatus(card, dot, level) {
  card.classList.remove("ok", "warn", "danger");
  dot.classList.remove("ok", "warn", "danger");
  card.classList.add(level);
  dot.classList.add(level);
}

function setGauge(id, value, min, max) {
  const pct = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));
  document.getElementById(id).style.width = pct + "%";
}

function updateOverallStatus(alertCount) {
  const el = document.getElementById("overall-status");
  document.getElementById("alert-count").textContent = alertCount;
  if (alertCount === 0) {
    el.textContent = "Nominal"; el.className = "overall-badge nominal";
  } else if (alertCount === 1) {
    el.textContent = "Warning"; el.className = "overall-badge warning";
  } else {
    el.textContent = "Alert";   el.className = "overall-badge alert";
  }
}

// ── LLM query ─────────────────────────────────────────────────────────────────
async function sendQuery() {
  const input = document.getElementById("query-input");
  const query = input.value.trim();
  if (!query || waitingForResponse) return;

  if (!chatHasContent) {
    document.getElementById("chat-window").innerHTML = "";
    chatHasContent = true;
  }

  appendMsg("user", query);
  input.value = "";
  const typingEl = appendTyping();
  setQueryBusy(true);

  if (!CONFIG.liveMode) {
    await new Promise(r => setTimeout(r, 1200));
    typingEl.remove();
    appendMsg("ai", "[Demo mode] Connect your Pi and set liveMode: true in config.js to get real answers.");
    setQueryBusy(false);
    return;
  }

  try {
    const res = await fetch(`${CONFIG.serverUrl}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    typingEl.remove();
    appendMsg("ai", json.response ?? json.error ?? "(no response)");
  } catch (err) {
    typingEl.remove();
    appendMsg("ai", `Could not reach the server: ${err.message}`);
  } finally {
    setQueryBusy(false);
  }
}

// ── UI helpers ────────────────────────────────────────────────────────────────
function appendMsg(role, text) {
  const win = document.getElementById("chat-window");
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.innerHTML = `
    <div class="msg-label">${role === "user" ? "You" : "AI"}</div>
    <div class="msg-bubble">${escapeHtml(text)}</div>
  `;
  win.appendChild(div);
  win.scrollTop = win.scrollHeight;
}

function appendTyping() {
  const win = document.getElementById("chat-window");
  const div = document.createElement("div");
  div.className = "msg ai";
  div.innerHTML = `
    <div class="msg-label">AI</div>
    <div class="msg-bubble typing-dots"><span></span><span></span><span></span></div>
  `;
  win.appendChild(div);
  win.scrollTop = win.scrollHeight;
  return div;
}

function setQueryBusy(busy) {
  waitingForResponse = busy;
  document.getElementById("send-btn").disabled = busy;
}

function setBadge(state) {
  const b = document.getElementById("connection-badge");
  const labels = { connected: "Live", disconnected: "Disconnected", connecting: "Connecting", demo: "Demo" };
  b.className = "badge " + state;
  b.textContent = labels[state] ?? state;
}

function updateTimestamp() {
  document.getElementById("last-update").textContent = new Date().toLocaleTimeString();
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
