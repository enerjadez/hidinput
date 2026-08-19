const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const TARGETS = [
  ["none", "— none —"],
  ["a", "A / Cross"],
  ["b", "B / Circle"],
  ["x", "X / Square"],
  ["y", "Y / Triangle"],
  ["lb", "LB"],
  ["rb", "RB"],
  ["lt", "LT"],
  ["rt", "RT"],
  ["ls", "LS"],
  ["rs", "RS"],
  ["back", "Back / Create"],
  ["start", "Start / Options"],
  ["guide", "Guide / PS"],
  ["dup", "D-Up"],
  ["ddown", "D-Down"],
  ["dleft", "D-Left"],
  ["dright", "D-Right"],
  ["space", "Key Space"],
  ["shift", "Key Shift"],
  ["ctrl", "Key Ctrl"],
  ["c", "Key C"],
  ["r", "Key R"],
  ["q", "Key Q"],
  ["e", "Key E"],
  ["f", "Key F"],
  ["v", "Key V"],
  ["mouse_left", "Mouse left"],
  ["mouse_right", "Mouse right"],
];

const SOURCES = [
  ["cross", "Cross"],
  ["circle", "Circle"],
  ["square", "Square"],
  ["triangle", "Triangle"],
  ["l1", "L1"],
  ["r1", "R1"],
  ["l2", "L2"],
  ["r2", "R2"],
  ["l3", "L3"],
  ["r3", "R3"],
  ["create", "Create"],
  ["options", "Options"],
  ["dpad_up", "D-Up"],
  ["dpad_down", "D-Down"],
  ["dpad_left", "D-Left"],
  ["dpad_right", "D-Right"],
  ["ps", "PS"],
  ["touchpad", "Touchpad"],
  ["mute", "Mute"],
  ["fn_l", "Fn L (L4)"],
  ["fn_r", "Fn R (R4)"],
  ["paddle_l", "Paddle L (L5)"],
  ["paddle_r", "Paddle R (R5)"],
];

let state = null;
let presets = [];
let applying = false;

async function api(path, body) {
  const opt = body === undefined
    ? {}
    : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const res = await fetch(path, opt);
  return res.json();
}

function setLit(key, on) {
  $$(`[data-key="${key}"]`).forEach((el) => el.classList.toggle("lit", !!on));
}

function nubs(id, x, y) {
  const nub = $(`#${id} .nub`);
  if (!nub) return;
  const px = ((x - 128) / 128) * 14;
  const py = ((y - 128) / 128) * 14;
  nub.style.transform = `translate(calc(-50% + ${px}px), calc(-50% + ${py}px))`;
}

function renderPlay(s) {
  const inp = s.input || {};
  const b = inp.buttons || {};
  Object.entries(b).forEach(([k, v]) => setLit(k, v));
  nubs("ls", inp.lx ?? 128, inp.ly ?? 128);
  nubs("rs", inp.rx ?? 128, inp.ry ?? 128);
  $("#l2bar").style.width = `${((inp.l2 || 0) / 255) * 100}%`;
  $("#r2bar").style.width = `${((inp.r2 || 0) / 255) * 100}%`;

  const connected = s.connected;
  $("#dot").className = "dot " + (connected ? "on" : "off");
  const link = s.device ? `${s.device.link.toUpperCase()} ${s.device.pid}` : "No controller";
  $("#link").textContent = connected ? link : (s.error || "No DualSense");
  $("#edgePill").style.opacity = s.is_edge ? "1" : "0.35";
  $("#hz").textContent = `${s.poll_hz || 0} Hz`;
  const bat = inp.battery || {};
  $("#batt").textContent = connected
    ? `${bat.pct ?? 0}%${bat.charging ? " ⚡" : ""}`
    : "—";
  $("#err").textContent = s.error || s.emulation_error || "";
  if ($("#emu") && !applying) $("#emu").value = s.emulation || "xbox360";

  const p = s.processed || {};
  $("#stats").innerHTML = `
    <div><span>LS</span><strong>${fmt(p.lx)}  ${fmt(p.ly)}</strong></div>
    <div><span>RS</span><strong>${fmt(p.rx)}  ${fmt(p.ry)}</strong></div>
    <div><span>LT / RT</span><strong>${fmt(p.lt)}  ${fmt(p.rt)}</strong></div>
    <div><span>Held</span><strong>${(p.held || []).join(" ") || "—"}</strong></div>
    <div><span>Profile</span><strong>${s.profile?.name || "—"} · slot ${s.slot}</strong></div>
    <div><span>ViGEm</span><strong>${s.vigem ? "ready" : "missing vgamepad"}</strong></div>
    <div><span>UDP</span><strong>${s.udp?.running ? ":" + s.udp.port + " · " + s.udp.packets : "off"}</strong></div>
    <div><span>Gyro raw</span><strong>${(inp.gyro || []).join("  ")}</strong></div>
  `;
  if ($("#ulog")) {
    $("#ulog").textContent = s.udp?.last || "(no packets yet)";
  }
}

function fmt(n) {
  if (n === undefined || n === null) return "—";
  return Number(n).toFixed(2);
}

function buildRemap(profile) {
  const root = $("#remap");
  if (!root.dataset.ready) {
    root.innerHTML = SOURCES.map(([id, label]) => `
      <div class="remap" data-src="${id}">
        <span>${label}</span>
        <select>${TARGETS.map(([v, t]) => `<option value="${v}">${t}</option>`).join("")}</select>
      </div>`).join("");
    root.dataset.ready = "1";
    root.addEventListener("change", async (ev) => {
      const box = ev.target.closest(".remap");
      if (!box) return;
      await api("/api/remap", { src: box.dataset.src, dst: ev.target.value });
    });
  }
  $$(".remap", root).forEach((box) => {
    const src = box.dataset.src;
    const sel = $("select", box);
    const v = (profile.buttons || {})[src] || "none";
    if (sel && ![...sel.options].some((o) => o.value === v)) {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      sel.appendChild(opt);
    }
    if (sel) sel.value = v;
    box.classList.toggle("hot", !!(state?.input?.buttons || {})[src]);
  });
}

function stickFields(id, side, tune) {
  const el = $(id);
  if (!el.dataset.ready) {
    el.innerHTML = `
      <label class="field">Inner deadzone <input type="range" data-k="deadzone_inner" min="0" max="40" /><span></span></label>
      <label class="field">Outer clamp <input type="range" data-k="deadzone_outer" min="60" max="100" /><span></span></label>
      <label class="field">Anti-deadzone <input type="range" data-k="anti_deadzone" min="0" max="40" /><span></span></label>
      <label class="field">Curve
        <select data-k="curve">
          <option value="linear">Linear</option>
          <option value="smooth">Smooth</option>
          <option value="aggressive">Aggressive</option>
          <option value="heavy">Heavy / late</option>
        </select>
      </label>
    `;
    el.dataset.ready = "1";
    el.addEventListener("input", debounce(async () => {
      const body = {};
      body[side] = readTune(el);
      await api("/api/tune", body);
    }, 80));
  }
  $$("[data-k]", el).forEach((inp) => {
    const k = inp.dataset.k;
    if (k === "curve") inp.value = tune.curve || "linear";
    else if (k === "deadzone_outer") inp.value = Math.round((tune[k] ?? 1) * 100);
    else inp.value = Math.round((tune[k] ?? 0) * 100);
    const span = inp.parentElement.querySelector("span");
    if (span) span.textContent = inp.type === "range" ? (inp.value / 100).toFixed(2) : "";
  });
}

function readTune(el) {
  const o = {};
  $$("[data-k]", el).forEach((inp) => {
    const k = inp.dataset.k;
    o[k] = k === "curve" ? inp.value : Number(inp.value) / 100;
  });
  return o;
}

function fillEffects() {
  const opts = presets.map((p) => `<option value="${p.id}">${p.label}</option>`).join("");
  $("#lEff").innerHTML = opts;
  $("#rEff").innerHTML = opts;
  $("#effGrid").innerHTML = presets.map((p) =>
    `<div class="preset" data-id="${p.id}"><b>${p.label}</b><span>${p.desc}</span></div>`
  ).join("");
}

function bindUi() {
  $$("#nav button").forEach((b) => {
    b.onclick = () => {
      $$("#nav button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      $$(".view").forEach((v) => v.classList.remove("active"));
      $(`#view-${b.dataset.view}`).classList.add("active");
    };
  });
  $("#reconnect").onclick = () => api("/api/connect", {});
  $("#emu").onchange = () => api("/api/emulation", { kind: $("#emu").value });
  $("#saveP").onclick = async () => {
    const name = $("#pname").value.trim() || state?.profile?.name || "Custom";
    const profile = { ...(state?.profile || {}), name };
    await api("/api/profile/save", { profile });
  };
  $("#uon").onclick = () => api("/api/udp", { port: Number($("#uport").value), enabled: true });
  $("#color").oninput = () => {
    const hex = $("#color").value;
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    api("/api/lightbar", { r, g, b });
  };
  $$("[data-rgb]").forEach((b) => {
    b.onclick = () => {
      const [r, g, bl] = b.dataset.rgb.split(",").map(Number);
      api("/api/lightbar", { r, g, b: bl });
    };
  });
  const rumble = debounce(() => api("/api/rumble", { left: Number($("#rumL").value), right: Number($("#rumR").value) }), 40);
  $("#rumL").oninput = rumble;
  $("#rumR").oninput = rumble;
  $("#pled").onchange = () => api("/api/tune", { player_led: Number($("#pled").value) });
  const trig = debounce(async () => {
    await api("/api/tune", {
      left_trigger: { hair: Number($("#lHair").value) / 100, deadzone: Number($("#lDz").value) / 100, effect: $("#lEff").value },
      right_trigger: { hair: Number($("#rHair").value) / 100, deadzone: Number($("#rDz").value) / 100, effect: $("#rEff").value },
    });
    await api("/api/triggers", { left: $("#lEff").value, right: $("#rEff").value });
  }, 80);
  ["lHair", "rHair", "lDz", "rDz", "lEff", "rEff"].forEach((id) => $(`#${id}`).addEventListener("input", trig));
  $("#effGrid").addEventListener("click", async (ev) => {
    const p = ev.target.closest(".preset");
    if (!p) return;
    $("#rEff").value = p.dataset.id;
    await api("/api/triggers", { left: $("#lEff").value, right: p.dataset.id });
  });
  const gyro = debounce(() => api("/api/tune", {
    gyro: { mode: $("#gMode").value, activation: $("#gAct").value, sensitivity: Number($("#gSens").value) / 10 },
  }), 80);
  $("#gMode").onchange = gyro;
  $("#gAct").onchange = gyro;
  $("#gSens").oninput = () => { $("#gSensV").textContent = (Number($("#gSens").value) / 10).toFixed(1); gyro(); };
}

function renderProfiles(s) {
  const list = $("#plist");
  list.innerHTML = (s.profiles || []).map((n) =>
    `<div class="preset" data-name="${n}"><b>${n}</b><span>click to load</span></div>`
  ).join("") || "<span class='warnbox'>No saved profiles yet</span>";
  list.onclick = (ev) => {
    const p = ev.target.closest(".preset");
    if (p) api("/api/profile/select", { name: p.dataset.name });
  };
  const slots = $("#slots");
  const names = s.profiles || [];
  const labels = { 1: "Fn + △", 2: "Fn + ○", 3: "Fn + ✕", 4: "Fn + □" };
  slots.innerHTML = [1, 2, 3, 4].map((i) => `
    <div class="remap ${s.slot === i ? "hot" : ""}">
      <span>${labels[i]} · slot ${i}</span>
      <select data-slot="${i}">
        ${names.map((n) => `<option value="${n}" ${s.slots[i] === n ? "selected" : ""}>${n}</option>`).join("")}
      </select>
    </div>`).join("");
  slots.onchange = (ev) => {
    const sel = ev.target;
    if (sel.dataset.slot) api("/api/slot", { slot: Number(sel.dataset.slot), name: sel.value });
  };
}

function syncTuneWidgets(s) {
  if (applying || !s.profile) return;
  applying = true;
  const p = s.profile;
  stickFields("#lsTune", "left_stick", p.left_stick || {});
  stickFields("#rsTune", "right_stick", p.right_stick || {});
  $("#lHair").value = Math.round((p.left_trigger?.hair || 0) * 100);
  $("#rHair").value = Math.round((p.right_trigger?.hair || 0) * 100);
  $("#lDz").value = Math.round((p.left_trigger?.deadzone || 0) * 100);
  $("#rDz").value = Math.round((p.right_trigger?.deadzone || 0) * 100);
  $("#lHairV").textContent = (Number($("#lHair").value) / 100).toFixed(2);
  $("#rHairV").textContent = (Number($("#rHair").value) / 100).toFixed(2);
  $("#lDzV").textContent = (Number($("#lDz").value) / 100).toFixed(2);
  $("#rDzV").textContent = (Number($("#rDz").value) / 100).toFixed(2);
  if (p.left_trigger?.effect) $("#lEff").value = p.left_trigger.effect;
  if (p.right_trigger?.effect) $("#rEff").value = p.right_trigger.effect;
  $("#gMode").value = p.gyro?.mode || "off";
  $("#gAct").value = p.gyro?.activation || "always";
  $("#gSens").value = Math.round((p.gyro?.sensitivity || 1.4) * 10);
  $("#gSensV").textContent = (Number($("#gSens").value) / 10).toFixed(1);
  $("#pname").placeholder = p.name || "Profile name";
  const lb = p.lightbar || [0, 90, 255];
  $("#color").value = "#" + lb.map((x) => Number(x).toString(16).padStart(2, "0")).join("");
  $("#pled").value = String(p.player_led ?? 1);
  $("#uport").value = s.udp?.port || 6969;
  applying = false;
}

function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

let tuneSynced = false;
async function tick() {
  try {
    state = await api("/api/state");
    renderPlay(state);
    if (state.profile) buildRemap(state.profile);
    if (!tuneSynced && state.profile) {
      syncTuneWidgets(state);
      renderProfiles(state);
      tuneSynced = true;
    }
    if (state.profile && $("#view-profiles").classList.contains("active")) renderProfiles(state);
  } catch (err) {
    $("#link").textContent = "API offline";
    $("#dot").className = "dot off";
  }
}

async function boot() {
  bindUi();
  try {
    const p = await api("/api/presets");
    presets = p.triggers || [];
    fillEffects();
  } catch { /* first paint still works */ }
  setInterval(tick, 40);
  tick();
}

boot();
