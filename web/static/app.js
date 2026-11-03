const $ = (id) => document.getElementById(id);
let status = {};
let currentJob = null;
let musicId = null, logoId = null;

// ---------- Tabs ----------
document.querySelectorAll(".tab").forEach(t => t.onclick = () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
    t.classList.add("active");
    const tab = t.dataset.tab;
    $("tab-crear").classList.toggle("hidden", tab !== "crear");
    $("tab-biblioteca").classList.toggle("hidden", tab !== "biblioteca");
    $("tab-automatizar").classList.toggle("hidden", tab !== "automatizar");
    if (tab === "biblioteca") loadLibrary();
    if (tab === "automatizar") { loadTopics(); loadScheduler(); }
});

// ---------- Estado ----------
async function loadStatus() {
    status = await (await fetch("/api/status")).json();
    const mk = (ok, l) => `<span class="chip ${ok ? "ok" : "off"}">${ok ? "●" : "○"} ${l}</span>`;
    $("status-chips").innerHTML =
        mk(status.ffmpeg_ready, "FFmpeg") + mk(status.providers.opencode, "OpenCode") +
        mk(status.youtube.connected, "YouTube") + mk(status.tiktok.connected, "TikTok");
    if (status.provider) $("provider").value = status.provider;
    $("theme").innerHTML = (status.themes || ["verde"]).map(t => `<option value="${t}">${t}</option>`).join("");
}

// ---------- Voces ----------
async function loadVoices() {
    const lang = $("lang").value;
    const r = await (await fetch(`/api/voices?lang=${lang}`)).json();
    const def = status.default_voice || "";
    $("voice").innerHTML = (r.voices || []).map(v =>
        `<option value="${v.name}" ${v.name === def ? "selected" : ""}>${v.name} · ${v.gender}</option>`).join("");
}

function rateStr() { const v = +$("rate").value; return (v >= 0 ? "+" : "") + v + "%"; }
function pitchStr() { const v = +$("pitch").value; return (v >= 0 ? "+" : "") + v + "Hz"; }
$("rate").oninput = () => $("rate-val").textContent = rateStr();
$("pitch").oninput = () => $("pitch-val").textContent = pitchStr();

$("btn-voice-play").onclick = async (e) => {
    e.preventDefault();
    const btn = $("btn-voice-play"); btn.textContent = "⏳...";
    try {
        const r = await fetch("/api/voice/preview", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ voice: $("voice").value, rate: rateStr(), pitch: pitchStr() }),
        });
        if (!r.ok) throw new Error((await r.json()).error || "error");
        const blob = await r.blob();
        const a = $("voice-audio"); a.src = URL.createObjectURL(blob); a.play();
    } catch (err) { alert("No se pudo generar la muestra: " + err.message); }
    btn.textContent = "▶ Escuchar";
};

// ---------- Modelos ----------
async function loadModels() {
    if ($("provider").value !== "opencode") { $("model").innerHTML = '<option value="">(por defecto)</option>'; return; }
    const r = await (await fetch("/api/opencode/models")).json();
    if (r.error) { $("model").innerHTML = '<option value="">(error: pon tu API key)</option>'; return; }
    $("model").innerHTML = '<option value="">(por defecto)</option>' +
        r.models.map(m => `<option value="${m.id}">${m.id}</option>`).join("");
}
$("btn-models").onclick = (e) => { e.preventDefault(); loadModels(); };
$("provider").onchange = loadModels;
$("lang").onchange = loadVoices;

// ---------- Uploads música/logo ----------
$("music").onchange = async () => {
    const f = $("music").files[0]; if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    const r = await (await fetch("/api/upload/music", { method: "POST", body: fd })).json();
    musicId = r.id; $("music-name").textContent = "✔ " + r.name;
};
$("logo").onchange = async () => {
    const f = $("logo").files[0]; if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    const r = await (await fetch("/api/upload/logo", { method: "POST", body: fd })).json();
    logoId = r.id; $("logo-name").textContent = "✔ " + r.name;
};

// ---------- Generar guion ----------
async function genScript() {
    $("btn-script").disabled = true; $("btn-regen") && ($("btn-regen").disabled = true);
    $("script-title").textContent = "generando...";
    const body = {
        topic: $("topic").value.trim() || null,
        lang: $("lang").value,
        provider: $("provider").value,
        model: $("model").value || null,
        num_scenes: +$("num_scenes").value || null,
        target_seconds: +$("target_seconds").value || null,
        previous_project: $("previous_project").value || null,
        part: +$("part").value || 2,
        style: $("style").value,
    };
    try {
        const r = await (await fetch("/api/script/generate", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
        })).json();
        if (r.error) throw new Error(r.error);
        $("plan-json").value = JSON.stringify(r.plan, null, 2);
        // Aplicar el tema y mood del estilo elegido (el usuario puede cambiarlos)
        if (r.plan._theme) $("theme").value = r.plan._theme;
        if (r.plan._mood) $("music_mood").value = r.plan._mood;
        const est = r.plan._style ? ` · estilo: ${r.plan._style}` : "";
        $("script-title").textContent = "— " + (r.plan.title || "") + est;
        $("script-empty").classList.add("hidden");
        $("script-box").classList.remove("hidden");
    } catch (err) {
        $("script-title").textContent = "";
        alert("Error al generar guion: " + err.message);
    }
    $("btn-script").disabled = false; $("btn-regen") && ($("btn-regen").disabled = false);
}
$("btn-script").onclick = genScript;
$("btn-regen").onclick = genScript;

// ---------- Renderizar ----------
$("btn-render").onclick = async () => {
    let plan;
    try { plan = JSON.parse($("plan-json").value); }
    catch (e) { alert("El guion no es JSON válido: " + e.message); return; }
    $("btn-render").disabled = true;
    $("log").textContent = ""; $("bar-fill").style.width = "0%"; $("pct").textContent = "0%";
    $("result").classList.add("hidden");

    const body = {
        plan, lang: $("lang").value, voice: $("voice").value,
        rate: rateStr(), pitch: pitchStr(), theme: $("theme").value,
        music_id: musicId, logo_id: logoId, music_mood: $("music_mood").value,
        branding: $("branding").checked, part: +$("part").value || null,
    };
    const r = await (await fetch("/api/render", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    })).json();
    currentJob = r.job_id;
    openSocket(r.job_id);
};

function openSocket(jobId) {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/${jobId}`);
    ws.onmessage = (ev) => {
        const d = JSON.parse(ev.data);
        if (d.pct != null) { $("bar-fill").style.width = d.pct + "%"; $("pct").textContent = d.pct + "%"; }
        if (d.message && d.message !== "FIN") appendLog(`[${d.pct}%] ${d.message}`);
        if (d.error) { appendLog("⚠ ERROR: " + d.message); $("btn-render").disabled = false; }
        if (d.stage === "done" && d.result) showResult(d.result);
    };
    ws.onclose = () => { $("btn-render").disabled = false; };
}
function appendLog(l) { const e = $("log"); e.textContent += l + "\n"; e.scrollTop = e.scrollHeight; }

// ---------- Previsualizar una escena ----------
$("btn-preview-scene").onclick = async () => {
    let plan;
    try { plan = JSON.parse($("plan-json").value); } catch (e) { alert("Guion no válido: " + e.message); return; }
    const scene = (plan.scenes || [])[0];
    if (!scene) { alert("El guion no tiene escenas."); return; }
    const btn = $("btn-preview-scene"); btn.textContent = "⏳ Renderizando...";
    try {
        const r = await fetch("/api/scene/preview", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ scene, theme: $("theme").value }),
        });
        if (!r.ok) throw new Error((await r.json()).error || "error");
        const blob = await r.blob();
        const v = $("scene-preview"); v.src = URL.createObjectURL(blob); v.classList.remove("hidden"); v.play();
    } catch (err) { alert("No se pudo previsualizar: " + err.message); }
    btn.textContent = "👁 Previsualizar escena 1";
};

function showResult(res) {
    $("result").classList.remove("hidden");
    $("preview").src = `/video/${currentJob}?t=${Date.now()}`;
    $("r-download").href = `/download/${currentJob}`;
    if (res.project) $("r-thumb-yt").href = `/thumb_yt/${res.project}`;
    $("btn-yt-upload").disabled = !status.youtube.connected;
    $("btn-tt-upload").disabled = !status.tiktok.connected;
}

// ---------- Subidas ----------
$("btn-yt-upload").onclick = async () => {
    $("upload-msg").textContent = "Subiendo a YouTube...";
    const r = await (await fetch("/api/upload/youtube", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ job_id: currentJob }),
    })).json();
    $("upload-msg").textContent = r.error ? "⚠ " + r.error : "✔ Subido: " + r.url;
};
$("btn-tt-upload").onclick = async () => {
    $("upload-msg").textContent = "Subiendo a TikTok...";
    const r = await (await fetch("/api/upload/tiktok", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ job_id: currentJob }),
    })).json();
    $("upload-msg").textContent = r.error ? "⚠ " + r.error : "✔ " + (r.note || "Subido a TikTok");
};
$("btn-yt-connect").onclick = async () => {
    alert("Se abrirá Google para autorizar (revisa tu navegador).");
    const r = await (await fetch("/auth/youtube/connect", { method: "POST" })).json();
    alert(r.error ? "⚠ " + r.error : "✔ YouTube conectado."); loadStatus();
};
$("btn-tt-connect").onclick = () => { location.href = "/auth/tiktok/connect"; };

// ---------- Biblioteca ----------
function cardHtml(i, isSeries) {
    const partBadge = isSeries ? `<div class="part-badge">PARTE ${i.part}</div>` : "";
    const img = i.has_thumb ? `<img src="${i.thumb_url}" loading="lazy">`
        : (i.has_thumb_yt ? `<img src="${i.thumb_yt_url}" loading="lazy">` : '<div class="noimg">▶</div>');
    return `<div class="lib-card">
        ${partBadge}
        <div class="thumb" onclick="document.getElementById('v_${i.project}').play()">${img}</div>
        <video id="v_${i.project}" src="${i.video_url}" preload="none" controls playsinline class="lib-video"></video>
        <div class="lib-title">${i.title}</div>
        <div class="lib-date">${i.date}</div>
        <div class="row">
            <a class="ghost mini" href="${i.video_url}" download>⬇</a>
            <button class="ghost mini" onclick="makePart2('${i.project}')">+ Parte</button>
            <button class="ghost mini" onclick="libUpload('youtube','${i.project}')">▶ YT</button>
            <button class="ghost mini" onclick="libUpload('tiktok','${i.project}')">♪ TT</button>
            <button class="ghost mini" onclick="delVideo('${i.project}')" title="Borrar">🗑</button>
        </div>
    </div>`;
}

async function loadLibrary() {
    const r = await (await fetch("/api/library")).json();
    const series = r.series || [];
    const items = r.items || [];
    $("lib-empty").classList.toggle("hidden", items.length > 0);
    // Selector de "Parte 2" (lista plana de todos los videos)
    $("previous_project").innerHTML = '<option value="">(ninguno — video nuevo)</option>' +
        items.map(i => `<option value="${i.project}">${i.title}</option>`).join("");
    // Biblioteca agrupada por series
    $("lib-grid").innerHTML = series.map(s => {
        const isSeries = s.count > 1;
        const cards = s.parts.map(i => cardHtml(i, isSeries)).join("");
        const head = isSeries
            ? `<div class="series-head">📁 ${s.title} <span class="series-count">${s.count} partes</span></div>`
            : "";
        return `<div class="series ${isSeries ? "is-series" : ""}">${head}<div class="series-cards">${cards}</div></div>`;
    }).join("");
}
window.makePart2 = (project) => {
    document.querySelector('.tab[data-tab="crear"]').click();
    loadLibrary().then(() => { $("previous_project").value = project; });
    $("part").value = 2;
    alert("Listo: se continuará la serie desde ese video. Pulsa 'Generar guion'.");
};
window.delVideo = async (project) => {
    if (!confirm("¿Borrar este video de la biblioteca? No se puede deshacer.")) return;
    const r = await (await fetch(`/api/library/${project}`, { method: "DELETE" })).json();
    if (r.error) alert("⚠ " + r.error); else loadLibrary();
};
window.libUpload = async (platform, project) => {
    if (!status[platform].connected) { alert("Conecta " + platform + " primero (abajo en Biblioteca)."); return; }
    const r = await (await fetch(`/api/upload/${platform}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project }),
    })).json();
    alert(r.error ? "⚠ " + r.error : "✔ " + (r.url || r.note || "Subido"));
};

// ---------- Automatización ----------
$("btn-batch").onclick = async () => {
    $("btn-batch").disabled = true;
    $("batch-log").textContent = ""; $("batch-fill").style.width = "0%"; $("batch-pct").textContent = "0%";
    const body = {
        count: +$("batch_count").value || 3, source: $("batch_source").value,
        lang: $("lang").value, provider: $("provider").value, model: $("model").value || null,
        theme: $("theme").value, voice: $("voice").value, rate: rateStr(), pitch: pitchStr(),
        music_mood: $("music_mood").value, branding: $("branding").checked, style: $("style").value,
    };
    const r = await (await fetch("/api/batch", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    })).json();
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/${r.job_id}`);
    ws.onmessage = (ev) => {
        const d = JSON.parse(ev.data);
        if (d.pct != null) { $("batch-fill").style.width = d.pct + "%"; $("batch-pct").textContent = d.pct + "%"; }
        if (d.message && d.message !== "FIN") { const e = $("batch-log"); e.textContent += `[${d.pct}%] ${d.message}\n`; e.scrollTop = e.scrollHeight; }
        if (d.error) { $("batch-log").textContent += "⚠ " + d.message + "\n"; }
    };
    ws.onclose = () => { $("btn-batch").disabled = false; };
};

async function loadTopics() {
    const r = await (await fetch("/api/topics")).json();
    const list = r.topics || [];
    $("topic-list").innerHTML = list.length
        ? list.map(t => `<li><span>${t}</span><button class="mini" onclick="delTopic(${JSON.stringify(t).replace(/"/g, "&quot;")})">✕</button></li>`).join("")
        : '<li class="hint">Vacío. Añade temas para generarlos en lote.</li>';
}
$("btn-topic-add").onclick = async () => {
    const v = $("topic-new").value.trim(); if (!v) return;
    await fetch("/api/topics", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ topic: v }) });
    $("topic-new").value = ""; loadTopics();
};
window.delTopic = async (t) => {
    await fetch("/api/topics", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ topic: t }) });
    loadTopics();
};

async function loadScheduler() {
    const c = await (await fetch("/api/scheduler")).json();
    $("sch_enabled").checked = !!c.enabled; $("sch_hour").value = c.hour; $("sch_minute").value = c.minute;
    $("sch_count").value = c.count; $("sch_source").value = c.source;
}
$("btn-sch-save").onclick = async () => {
    const cfg = {
        enabled: $("sch_enabled").checked, hour: +$("sch_hour").value, minute: +$("sch_minute").value,
        count: +$("sch_count").value, source: $("sch_source").value,
        lang: $("lang").value, provider: $("provider").value, model: $("model").value, theme: $("theme").value,
        voice: $("voice").value, music_mood: $("music_mood").value, branding: $("branding").checked,
    };
    await fetch("/api/scheduler", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cfg) });
    alert("✔ Programación guardada. Funcionará mientras el panel esté abierto.");
};

// ---------- Presets (recordar última config) ----------
const CFG_FIELDS = ["provider", "model", "lang", "theme", "voice", "rate", "pitch", "num_scenes", "target_seconds", "music_mood", "style"];
function saveCfg() {
    try {
        const cfg = {}; CFG_FIELDS.forEach(f => cfg[f] = $(f).value);
        cfg.branding = $("branding").checked;
        localStorage.setItem("cs_cfg", JSON.stringify(cfg));
    } catch (e) { /* storage no disponible */ }
}
function loadCfg() {
    try {
        const cfg = JSON.parse(localStorage.getItem("cs_cfg") || "{}");
        CFG_FIELDS.forEach(f => { if (cfg[f] != null && $(f)) $(f).value = cfg[f]; });
        if (cfg.branding != null) $("branding").checked = cfg.branding;
        $("rate-val").textContent = rateStr(); $("pitch-val").textContent = pitchStr();
    } catch (e) { /* ignore */ }
}
["provider", "model", "lang", "theme", "voice", "rate", "pitch", "num_scenes", "target_seconds", "branding", "music_mood", "style"]
    .forEach(id => { const el = $(id); if (el) el.addEventListener("change", saveCfg); });

// ---------- Init ----------
(async () => {
    await loadStatus();
    await loadVoices();
    await loadModels();
    loadCfg();            // restaurar última configuración tras poblar los menús
    loadLibrary();
    if (new URLSearchParams(location.search).get("tiktok") === "connected") loadStatus();
})();
