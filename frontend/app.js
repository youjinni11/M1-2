/* 환율 AI 비서 — 바닐라 JS 프론트엔드 (프레임워크 없음) */
const API = ((window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "http://127.0.0.1:8000").replace(/\/$/, "");

const $ = (id) => document.getElementById(id);
const state = {
  conversationId: null, // 현재 이어서 대화 중인 ID (null이면 새 대화)
  data: [],
  stats: null,
};

/* ---------------- 공통 fetch ---------------- */
async function api(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (res.status === 204) return null;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    let detail = body.detail;
    if (Array.isArray(detail)) detail = detail.map((d) => d.msg).join(", "); // Pydantic 검증 에러
    throw new Error(detail || `요청 실패 (${res.status})`);
  }
  return body;
}

const fmt = (n) => Number(n).toLocaleString("ko-KR", { maximumFractionDigits: 2 });

/* ---------------- 서버 깨우기 (Render 콜드스타트 대응) ---------------- */
async function wakeServer() {
  const status = $("serverStatus");
  const banner = $("coldStartBanner");
  const slowTimer = setTimeout(() => banner.classList.remove("hidden"), 2500);
  for (let attempt = 0; attempt < 6; attempt++) {
    try {
      await api("/");
      clearTimeout(slowTimer);
      banner.classList.add("hidden");
      status.textContent = "● 서버 연결됨";
      status.className = "pill ok";
      return true;
    } catch (e) {
      status.textContent = `서버 깨우는 중… (${attempt + 1})`;
      await new Promise((r) => setTimeout(r, 5000));
    }
  }
  clearTimeout(slowTimer);
  status.textContent = "● 서버 연결 실패";
  status.className = "pill err";
  banner.textContent = "백엔드 서버에 연결하지 못했어요. 잠시 후 새로고침해 주세요.";
  return false;
}

/* ---------------- 요약 ---------------- */
function renderSummary(s) {
  const unit = s.unit || "";
  $("sPeriod").textContent = s.period;
  $("sCount").textContent = `${fmt(s.count)}개`;
  $("sAvg").textContent = `${fmt(s.metrics.average)}${unit}`;
  $("sMax").textContent = `${fmt(s.metrics.max)}${unit} (${s.metrics.max_date})`;
  $("sMin").textContent = `${fmt(s.metrics.min)}${unit} (${s.metrics.min_date})`;
  $("sLatest").textContent = `${fmt(s.metrics.latest)}${unit} (${s.metrics.latest_date})`;
  $("sTrend").textContent = s.trend;
}

async function loadSummary() {
  try {
    renderSummary(await api("/api/data/summary"));
  } catch (e) {
    $("sTrend").textContent = "요약을 불러오지 못했어요: " + e.message;
  }
}

async function loadStatistics() {
  try {
    state.stats = await api("/api/data/statistics");
    $("sStd").textContent = `${fmt(state.stats.std_dev)}원`;
    $("sVol").textContent = `${state.stats.volatility_pct}%`;
    drawChart();
  } catch (e) {
    console.warn("통계 조회 실패", e);
  }
}

/* ---------------- 그래프 (Canvas 직접 그리기) ---------------- */
function drawChart() {
  const canvas = $("chart");
  const series = state.stats ? state.stats.series : [];
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth;
  const h = 180;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);
  const css = getComputedStyle(document.documentElement);
  const muted = css.getPropertyValue("--muted").trim();
  if (series.length < 2) {
    ctx.fillStyle = muted;
    ctx.fillText("그래프를 그릴 데이터가 부족합니다", 12, 24);
    return;
  }
  const pad = { l: 46, r: 10, t: 12, b: 22 };
  const vals = series.map((p) => p.value);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const x = (i) => pad.l + (i / (series.length - 1)) * (w - pad.l - pad.r);
  const y = (v) => pad.t + (1 - (v - min) / (max - min || 1)) * (h - pad.t - pad.b);

  // 축 눈금
  ctx.font = "10px sans-serif";
  ctx.fillStyle = muted;
  ctx.strokeStyle = css.getPropertyValue("--border").trim();
  for (let k = 0; k <= 3; k++) {
    const v = min + ((max - min) * k) / 3;
    ctx.beginPath();
    ctx.moveTo(pad.l, y(v));
    ctx.lineTo(w - pad.r, y(v));
    ctx.stroke();
    ctx.fillText(Math.round(v).toLocaleString(), 4, y(v) + 3);
  }
  ctx.fillText(series[0].date, pad.l, h - 6);
  const last = series[series.length - 1].date;
  ctx.fillText(last, w - pad.r - ctx.measureText(last).width, h - 6);

  const line = (key, color, width) => {
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    let started = false;
    series.forEach((p, i) => {
      if (p[key] == null) return;
      started ? ctx.lineTo(x(i), y(p[key])) : ctx.moveTo(x(i), y(p[key]));
      started = true;
    });
    ctx.stroke();
  };
  line("value", css.getPropertyValue("--primary").trim(), 1.4);
  line("ma", css.getPropertyValue("--ma").trim(), 2);
}

/* ---------------- 데이터 CRUD ---------------- */
async function loadData(highlightId) {
  try {
    const res = await api("/api/data");
    state.data = res.items;
    renderTable(highlightId);
  } catch (e) {
    $("dataBody").innerHTML = "";
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 4;
    td.className = "muted";
    td.textContent = "데이터를 불러오지 못했어요: " + e.message;
    tr.appendChild(td);
    $("dataBody").appendChild(tr);
  }
}

function renderTable(highlightId) {
  const body = $("dataBody");
  body.innerHTML = "";
  const rows = [...state.data].reverse(); // 최신 날짜가 위로
  rows.forEach((item) => {
    const tr = document.createElement("tr");
    if (item.id === highlightId) tr.className = "highlight";
    const cells = [item.date, fmt(item.value), item.memo || ""];
    cells.forEach((text, i) => {
      const td = document.createElement("td");
      td.textContent = text;
      if (i === 1) td.className = "num";
      tr.appendChild(td);
    });
    const act = document.createElement("td");
    act.className = "actions";
    const edit = document.createElement("button");
    edit.className = "btn ghost small";
    edit.textContent = "수정";
    edit.onclick = () => startEdit(item);
    const del = document.createElement("button");
    del.className = "btn danger small";
    del.textContent = "삭제";
    del.onclick = () => removeData(item);
    act.append(edit, del);
    tr.appendChild(act);
    body.appendChild(tr);
  });
  $("dataCount").textContent = `총 ${state.data.length}개 (최신순)`;
  if (highlightId) {
    const el = body.querySelector("tr.highlight");
    if (el) el.scrollIntoView({ block: "center" });
  }
}

function setDataMsg(text, ok = true) {
  const el = $("dataMsg");
  el.textContent = text;
  el.className = "form-msg " + (ok ? "ok" : "err");
}

function startEdit(item) {
  $("editId").value = item.id;
  $("fDate").value = item.date;
  $("fValue").value = item.value;
  $("fMemo").value = item.memo || "";
  $("saveBtn").textContent = "수정 저장";
  $("cancelEdit").classList.remove("hidden");
  setDataMsg(`${item.date} 데이터를 수정하는 중이에요.`);
  $("fValue").focus();
}

function resetForm() {
  $("dataForm").reset();
  $("editId").value = "";
  $("saveBtn").textContent = "추가";
  $("cancelEdit").classList.add("hidden");
}

async function submitData(ev) {
  ev.preventDefault();
  const id = $("editId").value;
  const payload = { date: $("fDate").value, value: Number($("fValue").value), memo: $("fMemo").value };
  $("saveBtn").disabled = true;
  try {
    const saved = id
      ? await api(`/api/data/${id}`, { method: "PUT", body: JSON.stringify(payload) })
      : await api("/api/data", { method: "POST", body: JSON.stringify(payload) });
    setDataMsg(`✅ ${id ? "수정" : "추가"} 완료: ${saved.date} · ${fmt(saved.value)}원 (id: ${saved.id})`);
    resetForm();
    await refreshAll(saved.id);
  } catch (e) {
    setDataMsg("❌ 저장 실패: " + e.message, false);
  } finally {
    $("saveBtn").disabled = false;
  }
}

async function removeData(item) {
  if (!confirm(`${item.date} (${fmt(item.value)}원) 데이터를 삭제할까요?`)) return;
  try {
    await api(`/api/data/${item.id}`, { method: "DELETE" });
    setDataMsg(`🗑️ 삭제 완료: ${item.date}`);
    await refreshAll();
  } catch (e) {
    setDataMsg("❌ 삭제 실패: " + e.message, false);
  }
}

async function refreshAll(highlightId) {
  await Promise.all([loadData(highlightId), loadSummary(), loadStatistics()]);
}

/* ---------------- 내보내기 ---------------- */
function download(format) {
  // 백엔드 /api/data/export 가 파일을 만들어 내려준다.
  window.location.href = `${API}/api/data/export?format=${format}`;
}

/* ---------------- 대화 기록 ---------------- */
async function loadConversations() {
  const list = $("conversationList");
  try {
    const items = await api("/api/conversations");
    list.innerHTML = "";
    if (!items.length) {
      list.innerHTML = '<li class="muted small">아직 저장된 대화가 없어요.</li>';
      return;
    }
    items.forEach((c) => {
      const li = document.createElement("li");
      li.className = "conv-item" + (c.id === state.conversationId ? " active" : "");
      const info = document.createElement("div");
      info.style.minWidth = "0";
      const title = document.createElement("div");
      title.className = "conv-title";
      title.textContent = c.title || "(제목 없음)";
      const meta = document.createElement("div");
      meta.className = "conv-meta";
      meta.textContent = `${c.message_count}개 메시지 · ${(c.updated_at || "").slice(0, 16).replace("T", " ")}`;
      info.append(title, meta);
      const del = document.createElement("button");
      del.className = "conv-del";
      del.title = "대화 삭제";
      del.textContent = "✕";
      del.onclick = (e) => {
        e.stopPropagation();
        deleteConversation(c);
      };
      li.append(info, del);
      li.onclick = () => openConversation(c.id);
      list.appendChild(li);
    });
  } catch (e) {
    list.innerHTML = "";
    const li = document.createElement("li");
    li.className = "muted small";
    li.textContent = "대화 목록을 불러오지 못했어요: " + e.message;
    list.appendChild(li);
  }
}

async function openConversation(id) {
  try {
    const conv = await api(`/api/conversations/${id}`);
    state.conversationId = conv.id;
    $("messages").innerHTML = "";
    conv.messages.forEach((m) => addMessage(m.role, m.content));
    $("chatMode").textContent = `불러온 대화: ${conv.title}`;
    loadConversations();
  } catch (e) {
    addMessage("error", "대화를 불러오지 못했어요: " + e.message);
  }
}

async function deleteConversation(c) {
  if (!confirm(`"${c.title}" 대화를 삭제할까요?`)) return;
  try {
    await api(`/api/conversations/${c.id}`, { method: "DELETE" });
    if (state.conversationId === c.id) newChat();
    loadConversations();
  } catch (e) {
    alert("삭제 실패: " + e.message);
  }
}

function newChat() {
  state.conversationId = null;
  $("messages").innerHTML = "";
  addMessage("assistant", "새 대화를 시작해요. 저장된 환율 데이터에 대해 무엇이든 물어보세요.");
  $("chatMode").textContent = "새 대화";
  loadConversations();
}

/* ---------------- 채팅 ---------------- */
function addMessage(role, text, tools) {
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.textContent = text;
  if (tools && tools.length) {
    const t = document.createElement("span");
    t.className = "tools";
    t.textContent = "🔧 사용한 도구: " + tools.join(", ");
    div.appendChild(t);
  }
  $("messages").appendChild(div);
  $("messages").scrollTop = $("messages").scrollHeight;
  return div;
}

function showTyping() {
  const div = document.createElement("div");
  div.className = "msg assistant";
  div.innerHTML = '<span class="typing"><span></span><span></span><span></span></span> 데이터를 확인하며 답변을 만드는 중…';
  $("messages").appendChild(div);
  $("messages").scrollTop = $("messages").scrollHeight;
  return div;
}

async function sendMessage(text) {
  const input = $("chatInput");
  const btn = $("sendBtn");
  addMessage("user", text);
  input.value = "";
  input.disabled = btn.disabled = true;
  const loading = showTyping();
  try {
    const res = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message: text, conversation_id: state.conversationId }),
    });
    loading.remove();
    addMessage("assistant", res.reply, res.tools_used);
    state.conversationId = res.conversation_id;
    $("chatMode").textContent = "대화 자동 저장됨";
    renderSummary(res.summary);
    loadConversations();
  } catch (e) {
    loading.remove();
    addMessage("error", "⚠️ 답변 실패: " + e.message);
  } finally {
    input.disabled = btn.disabled = false;
    input.focus();
  }
}

/* ---------------- 다크 모드 ---------------- */
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  $("themeToggle").textContent = theme === "dark" ? "☀️ 라이트 모드" : "🌙 다크 모드";
  try { localStorage.setItem("theme", theme); } catch (e) { /* 저장 불가 환경 무시 */ }
  drawChart();
}

/* ---------------- 시작 ---------------- */
document.addEventListener("DOMContentLoaded", async () => {
  let saved = "light";
  try { saved = localStorage.getItem("theme") || "light"; } catch (e) { /* 무시 */ }
  applyTheme(saved);

  $("themeToggle").onclick = () =>
    applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark");
  $("chatForm").onsubmit = (e) => {
    e.preventDefault();
    const text = $("chatInput").value.trim();
    if (text) sendMessage(text);
  };
  document.querySelectorAll(".chip").forEach((c) => (c.onclick = () => sendMessage(c.dataset.q)));
  $("newChat").onclick = newChat;
  $("dataForm").onsubmit = submitData;
  $("cancelEdit").onclick = () => { resetForm(); setDataMsg(""); };
  $("refreshSummary").onclick = () => refreshAll();
  $("exportCsv").onclick = () => download("csv");
  $("exportJson").onclick = () => download("json");
  window.addEventListener("resize", drawChart);

  if (await wakeServer()) {
    await Promise.all([refreshAll(), loadConversations()]);
  }
});
