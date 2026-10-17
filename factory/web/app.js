const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const STATUS = { queued: "Đang chờ", running: "Đang render", done: "Xong", failed: "Lỗi" };

let engines = [], spec = null, specPath = null, currentJob = null, pollTimer = null;
let podcastInfo = { configured: false, voices: [], default: "mai" };
const sleep = (ms) => new Promise((ok) => setTimeout(ok, ms));

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
  return body;
}

function msg(text, kind = "") { const m = $("formMsg"); m.textContent = text; m.className = "msg " + kind; }

// ---------- giọng đọc video ----------
async function loadTTSVoices() {
  $("ttsNote").textContent = "Đang kết nối server VieNeu…";
  try {
    const info = await api("/api/tts/vieneu/voices");
    $("vieneuVoices").innerHTML = info.voices.map((v) => `<option value="${esc(v.key)}">${esc(v.label)}</option>`).join("");
    $("vieneuVoice").placeholder = info.default;
    if ($("ttsProvider").value === "vieneu") $("ttsNote").textContent = info.ready
      ? `VieNeu sẵn sàng. Để trống để dùng ${info.default}. Phụ đề căn bằng Whisper; file podcast tải lên được ưu tiên.`
      : info.reason;
  } catch (e) {
    if ($("ttsProvider").value === "vieneu") $("ttsNote").textContent = e.message;
  }
}

function renderTTS(s) {
  $("ttsProvider").value = s.tts_provider || "edge";
  $("vieneuVoice").value = s.vieneu_voice || "";
  const vieneu = $("ttsProvider").value === "vieneu";
  $("vieneuBox").classList.toggle("hidden", !vieneu);
  if (vieneu) return loadTTSVoices();
  else $("ttsNote").textContent = "Giọng Edge theo kịch bản. Bản podcast ưu tiên file tải lên hoặc ElevenLabs nếu đã cấu hình.";
}

$("ttsProvider").onchange = async () => {
  try {
    const s = JSON.parse($("specJson").value);
    s.tts_provider = $("ttsProvider").value;
    $("specJson").value = JSON.stringify(s, null, 2);
    spec = s;
    await renderTTS(s);
  } catch (e) { msg("JSON sai cú pháp: " + e.message, "err"); }
};

$("vieneuVoice").oninput = () => {
  try {
    const s = JSON.parse($("specJson").value);
    const voice = $("vieneuVoice").value.trim();
    if (voice) s.vieneu_voice = voice; else delete s.vieneu_voice;
    $("specJson").value = JSON.stringify(s, null, 2);
    spec = s;
  } catch (e) { msg("JSON sai cú pháp: " + e.message, "err"); }
};
$("btnTTSVoices").onclick = loadTTSVoices;

// ---------- engine ----------
async function loadEngines() {
  engines = await api("/api/engines");
  $("engineChips").innerHTML = engines.map((e) => `<span class="chip ${e.ready ? "ok" : "no"}" title="${esc(e.reason)}">${esc(e.label)}</span>`).join("");
  $("engineChecks").innerHTML = engines.map((e) => `
    <label><input type="checkbox" value="${e.key}" ${e.ready ? "checked" : "disabled"}>
      ${esc(e.label)} ${e.ready ? "" : `<span class="why">(${esc(e.reason)})</span>`}</label>`).join("");
}

// ---------- bản podcast (chỉ MoneyPrinterTurbo) ----------
async function loadPodcastVoices() {
  podcastInfo = await api("/api/podcast/voices").catch(() => podcastInfo);
  $("podcastVoice").innerHTML = podcastInfo.voices.map((v) => `<option value="${esc(v.key)}">${esc(v.label)}</option>`).join("");
  $("podcastNote").textContent = podcastInfo.configured
    ? "Khi chọn Edge: dùng ElevenLabs nếu có key, hoặc file tải lên. Khi chọn VieNeu: dùng giọng VieNeu, trừ khi đã tải file giọng lên."
    : "Chưa có ELEVENLABS_API_KEY: dùng giọng đọc video đã chọn hoặc file tải lên.";
}

function renderPodcast(s) {
  const p = s && s.podcast;
  $("podcastText").innerHTML = p ? `<b>${esc(p.title || "")}</b><br>${esc(p.say.slice(0, 180))}${p.say.length > 180 ? "…" : ""}`
    : "Chưa có. Bản MoneyPrinterTurbo sẽ đọc kịch bản thường.";
  $("btnPodcast").textContent = p ? "Viết lại" : "Viết bản podcast";
  $("podcastVoice").value = (p && p.voice) || podcastInfo.default;
  $("btnElevenWeb").disabled = !p;
  $("podcastAudio").innerHTML = p && p.audio
    ? `✓ Dùng file giọng <b>${esc(p.audio)}</b> (Whisper căn phụ đề)<button class="btn ghost small" id="btnDropAudio">Bỏ file</button>` : "";
  if (p && p.audio) $("btnDropAudio").onclick = () => setPodcastAudio(null);
}

async function setPodcastAudio(path) {
  const s = JSON.parse($("specJson").value);
  if (!s.podcast) throw new Error("Chưa có bản podcast.");
  if (path) s.podcast.audio = path; else delete s.podcast.audio;
  if (specPath) await api(`/api/content/${specPath}`, { method: "PUT", body: JSON.stringify(s) });
  showSpec(s, specPath);
}

// Bán tự động: web ElevenLabs do bạn tự bấm (gói Free được dùng giọng thư viện trên web, không qua API);
// hệ thống chép sẵn lời thoại, mở trang, rồi tự nhận file mp3 mới trong thư mục Downloads.
$("btnElevenWeb").onclick = async () => {
  let s;
  try { s = JSON.parse($("specJson").value); } catch (e) { return msg("JSON sai cú pháp: " + e.message, "err"); }
  if (!s.podcast) return msg("Chưa có bản podcast — bấm Viết bản podcast trước.", "err");
  try { await navigator.clipboard.writeText(s.podcast.say); } catch (e) { /* trình duyệt chặn clipboard: tự chép từ JSON */ }
  window.open("https://elevenlabs.io/app/speech-synthesis/text-to-speech", "_blank");
  const btn = $("btnElevenWeb");
  btn.disabled = true;
  msg("Đã chép lời podcast. Trên ElevenLabs: chọn giọng (vd. Nhật Phong) → Ctrl+V → Generate → Download. Đang chờ file trong Downloads…");
  try {
    const { id } = await api("/api/podcast/watch", { method: "POST", body: JSON.stringify({ name: s.id }) });
    let job;
    for (;;) {
      await sleep(2000);
      job = await api(`/api/draft/${id}`);
      if (job.status !== "running") break;
    }
    if (job.status === "failed") throw new Error(job.error);
    await setPodcastAudio(job.result.audio);
    msg(`Đã nhận ${job.result.source}. Bấm Tạo video (chỉ cần tick MoneyPrinterTurbo).`, "ok");
  } catch (e) { msg(e.message, "err"); }
  btn.disabled = false;
};

$("audioFile").onchange = async (ev) => {
  const f = ev.target.files[0];
  ev.target.value = "";
  if (!f) return;
  msg(`Đang tải lên ${f.name}…`);
  try {
    const res = await fetch(`/api/podcast/audio?name=${encodeURIComponent(f.name)}`, { method: "POST", body: f });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
    await setPodcastAudio(body.audio);
    msg(`Đã gắn file giọng ${f.name}.`, "ok");
  } catch (e) { msg(e.message, "err"); }
};

$("btnPodcast").onclick = async () => {
  let s;
  try { s = JSON.parse($("specJson").value); } catch (e) { return msg("JSON sai cú pháp: " + e.message, "err"); }
  const btn = $("btnPodcast");
  btn.disabled = true; btn.textContent = "Gemini đang viết…"; msg("Gemini viết lời thoại kiểu podcast tâm sự…");
  try {
    const { id } = await api("/api/podcast", { method: "POST", body: JSON.stringify({ spec: s }) });
    let job;
    for (;;) {
      await sleep(2000);
      job = await api(`/api/draft/${id}`);
      if (job.log.length) msg(job.log[job.log.length - 1]);
      if (job.status !== "running") break;
    }
    if (job.status === "failed") throw new Error(job.error);
    s.podcast = { ...job.result.podcast, voice: $("podcastVoice").value };
    if (specPath) await api(`/api/content/${specPath}`, { method: "PUT", body: JSON.stringify(s) });
    showSpec(s, specPath);
    msg(`Đã có bản podcast${specPath ? " (đã lưu vào kịch bản)" : ""}.`, "ok");
  } catch (e) { msg(e.message, "err"); }
  btn.disabled = false; renderPodcast(spec);
};

$("podcastVoice").onchange = () => {
  try {
    const s = JSON.parse($("specJson").value);
    if (s.podcast) { s.podcast.voice = $("podcastVoice").value; $("specJson").value = JSON.stringify(s, null, 2); spec = s; }
  } catch (e) { /* JSON đang sửa dở: giọng sẽ được gắn lúc bấm Tạo video */ }
};

// ---------- kịch bản ----------
async function loadContent() {
  const items = await api("/api/content");
  $("contentSelect").innerHTML = items.map((c) =>
    `<option value="${esc(c.path)}">${esc(c.series ? `${c.series} · Tập ${c.ep}: ` : "")}${esc(c.title)} (${c.scenes} cảnh)</option>`).join("");
}

function showSpec(s, path) {
  spec = s; specPath = path;
  $("specBox").classList.remove("hidden");
  $("specPath").textContent = path || "";
  $("specTitle").textContent = s.title;
  $("sceneList").innerHTML = s.scenes.map((sc) => `<li><span class="type">${esc(sc.type)}</span>${esc(sc.say.slice(0, 90))}${sc.say.length > 90 ? "…" : ""}</li>`).join("");
  $("issues").classList.add("hidden");
  $("specJson").value = JSON.stringify(s, null, 2);
  renderTTS(s);
  renderPodcast(s);
}

document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === t));
  $("pane-topic").classList.toggle("hidden", t.dataset.tab !== "topic");
  $("pane-content").classList.toggle("hidden", t.dataset.tab !== "content");
}));

$("btnDraft").onclick = async () => {
  const btn = $("btnDraft");
  btn.disabled = true; btn.textContent = "Gemini đang viết…"; msg("Bắt đầu: lập dàn ý → viết kịch bản → rà soát. Gói miễn phí có thể phải chờ.");
  try {
    const { id } = await api("/api/draft", { method: "POST", body: JSON.stringify({
      topic: $("topic").value, level: $("level").value, hook: $("hook").value, notes: $("notes").value, check: $("check").checked,
      podcast: $("podcastDraft").checked, tournament: $("tournament").checked }) });
    let job;
    for (;;) {
      await new Promise((ok) => setTimeout(ok, 2000));
      job = await api(`/api/draft/${id}`);
      if (job.log.length) msg(job.log[job.log.length - 1]);
      if (job.status !== "running") break;
    }
    if (job.status === "failed") throw new Error(job.error);
    const r = job.result;
    showSpec(r.spec, r.path); await loadContent();
    const box = $("issues");
    box.innerHTML = (r.issues || []).map((i) => `<li>${esc(i)}</li>`).join("");
    box.classList.toggle("hidden", !(r.issues || []).length);
    msg("Đã có nháp. Đọc lại, sửa JSON nếu cần, rồi bấm Tạo video.", "ok");
  } catch (e) { msg(e.message, "err"); }
  btn.disabled = false; btn.textContent = "Nhờ Gemini viết nháp";
};

$("btnOpen").onclick = async () => {
  const path = $("contentSelect").value;
  if (!path) return;
  try { showSpec(await api(`/api/content/${path}`), path); msg(""); } catch (e) { msg(e.message, "err"); }
};

$("btnToggleJson").onclick = () => $("jsonBox").classList.toggle("hidden");

$("btnSaveSpec").onclick = async () => {
  let s;
  try { s = JSON.parse($("specJson").value); } catch (e) { return msg("JSON sai cú pháp: " + e.message, "err"); }
  const path = specPath || `drafts/${(s.id || "video").replace(/[^\w-]/g, "")}.json`;
  try { await api(`/api/content/${path}`, { method: "PUT", body: JSON.stringify(s) }); showSpec(s, path); msg("Đã lưu.", "ok"); await loadContent(); }
  catch (e) { msg(e.message, "err"); }
};

$("btnCreate").onclick = async () => {
  let s;
  try { s = JSON.parse($("specJson").value); } catch (e) { return msg("JSON sai cú pháp: " + e.message, "err"); }
  if (s.podcast) s.podcast.voice = $("podcastVoice").value;
  const picked = [...document.querySelectorAll("#engineChecks input:checked")].map((i) => i.value);
  if (!picked.length) return msg("Chọn ít nhất một engine.", "err");
  $("btnCreate").disabled = true;
  try {
    const job = await api("/api/jobs", { method: "POST", body: JSON.stringify({ spec: s, engines: picked }) });
    msg(`Đã tạo job với ${picked.length} engine.`, "ok");
    await loadJobs(); openJob(job.id);
  } catch (e) { msg(e.message, "err"); }
  $("btnCreate").disabled = false;
};

// ---------- job ----------
function dots(job) {
  return `<span class="dots">${Object.values(job.engines).map((e) => `<span class="dot ${e.status}"></span>`).join("")}</span>`;
}

async function loadJobs() {
  const jobs = await api("/api/jobs");
  $("jobList").innerHTML = jobs.length ? jobs.map((j) => `
    <li data-id="${esc(j.id)}" class="${currentJob === j.id ? "active" : ""}">
      <div class="jt">${esc(j.title)}</div>
      <div class="jm">${dots(j)} ${esc(j.created.replace("T", " ").slice(0, 16))} ${j.selected ? "· đã chọn" : ""}</div>
    </li>`).join("") : `<li class="muted">Chưa có lần tạo nào.</li>`;
  $("jobList").querySelectorAll("li[data-id]").forEach((li) => li.onclick = () => openJob(li.dataset.id));
}

function openJob(id) { currentJob = id; loadJobs(); renderJob(); }

async function renderJob() {
  clearTimeout(pollTimer);
  if (!currentJob) return;
  let job;
  try { job = await api(`/api/jobs/${currentJob}`); } catch (e) { $("detail").innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }
  const byKey = Object.fromEntries(engines.map((e) => [e.key, e]));
  const cards = Object.entries(job.engines).map(([key, info]) => card(job, key, info, byKey[key] || { label: key, style: "" })).join("");
  const pub = job.published ? `
    <div class="publish">
      <b>Đã chọn: ${esc((byKey[job.selected] || {}).label || job.selected)}</b>
      <div class="small">File để đăng: ${esc(job.published.video)}</div>
      <textarea id="captionBox" rows="5">${esc(job.published.caption)}</textarea>
      <div class="row"><button class="btn small" id="btnCopy">Chép caption</button>
      <a class="btn small" href="${esc(publishUrl(job))}" download>Tải video</a></div>
    </div>` : "";
  // giữ nguyên thẻ video đang phát để khỏi bị giật khi cập nhật trạng thái
  const playing = [...document.querySelectorAll(".frame video")].some((v) => !v.paused);
  if (!playing || $("detail").dataset.job !== job.id) {
    $("detail").dataset.job = job.id;
    $("detail").innerHTML = `
      <div class="jobhead"><div><div class="muted small">${esc(job.created.replace("T", " "))}</div><h1>${esc(job.title)}</h1></div></div>
      ${pub}<div class="grid">${cards}</div>`;
    bindCard(job);
  }
  if (Object.values(job.engines).some((e) => e.status === "queued" || e.status === "running")) {
    pollTimer = setTimeout(() => { renderJob(); loadJobs(); }, 2500);
  }
}

function publishUrl(job) {
  const file = job.published.video.split(/[\\/]/).pop();
  return `/publish/${encodeURIComponent(job.id)}/${encodeURIComponent(file)}`;
}

function card(job, key, info, eng) {
  const base = `/runs/${encodeURIComponent(job.id)}/${key}`;
  let frame;
  if (info.status === "done") {
    frame = `<video src="${base}/video.mp4?v=${info.seconds}" poster="${base}/thumb.jpg?v=${info.seconds}" controls playsinline preload="none"></video>`;
  } else if (info.status === "failed") {
    frame = `<div class="state failed"><div class="big">Lỗi</div><div>${esc((info.message || "").slice(-240))}</div></div>`;
  } else {
    const since = info.started ? Math.round((Date.now() - new Date(info.started)) / 1000) : 0;
    frame = `<div class="state">${info.status === "running" ? `<div class="spinner"></div><div class="big">Đang render · ${since}s</div>` : `<div class="big">Đang chờ lượt</div>`}
      <div>${esc(info.message || "")}</div></div>`;
  }
  const selected = job.selected === key;
  return `<div class="vcard ${selected ? "selected" : ""}">
    <div class="vhead"><b>${esc(eng.label)}</b><span>${esc(eng.style)}</span></div>
    <div class="frame">${frame}</div>
    <div class="vfoot">
      <div class="vmeta"><span class="badge ${info.status}">${STATUS[info.status] || info.status}</span>
        <span>${info.duration ? `${info.duration}s video` : ""}${info.seconds ? ` · render ${info.seconds}s` : ""}</span></div>
      <div class="vbtns">
        <button class="btn ${selected ? "" : "primary"}" data-act="select" data-key="${key}" ${info.status !== "done" ? "disabled" : ""}>${selected ? "Đã chọn" : "Chọn để đăng"}</button>
        <button class="btn" data-act="rerun" data-key="${key}" ${info.status === "running" || info.status === "queued" ? "disabled" : ""}>Chạy lại</button>
        ${key === "remotion" && info.status === "done" ? '<button class="btn" data-act="edit" data-key="remotion">Chỉnh sửa</button>' : ''}
        <button class="btn" data-act="log" data-key="${key}">Log</button>
      </div>
    </div></div>`;
}

function bindCard(job) {
  document.querySelectorAll(".vbtns button").forEach((b) => b.onclick = async () => {
    const key = b.dataset.key;
    try {
      if (b.dataset.act === "select") { await api(`/api/jobs/${job.id}/select/${key}`, { method: "POST" }); await loadJobs(); $("detail").dataset.job = ""; renderJob(); }
      if (b.dataset.act === "rerun") { await api(`/api/jobs/${job.id}/rerun/${key}`, { method: "POST" }); $("detail").dataset.job = ""; renderJob(); }
      if (b.dataset.act === "edit") { await window.openRemotionEditor(job.id); }
      if (b.dataset.act === "log") {
        const r = await api(`/api/jobs/${job.id}/log/${key}`).catch(() => ({ log: "Chưa có log." }));
        $("logTitle").textContent = `Log · ${key}`; $("logText").textContent = r.log; $("logDialog").showModal();
      }
    } catch (e) { alert(e.message); }
  });
  const copy = $("btnCopy");
  if (copy) copy.onclick = () => { navigator.clipboard.writeText($("captionBox").value); copy.textContent = "Đã chép"; };
}

(async function init() {
  await loadEngines(); await loadPodcastVoices(); await loadContent(); await loadJobs();
  setInterval(loadJobs, 8000);
})();

if (typeof window !== "undefined") window.addEventListener("editorPublished", async () => {
  $("detail").dataset.job = "";
  await loadJobs(); await renderJob();
});
