const $ = (id) => document.getElementById(id);
const escHtml = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const SCENE_TYPES = ["terminal", "diagram", "evidence", "map", "stat", "timeline", "brand"];

let status = {};
let currentJob = null;
let currentPlan = null;
let editorMode = "visual";
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
    $("theme").innerHTML = (status.themes || ["verde"]).map(t => `<option value="${escHtml(t)}">${escHtml(t)}</option>`).join("");
}

// ---------- Recursos persistentes (música / logos) ----------
async function loadAssets() {
    try {
        const r = await (await fetch("/api/assets")).json();
        const prevMusic = $("music-saved").value || musicId || "";
        const prevLogo = $("logo-saved").value || logoId || "";
        $("music-saved").innerHTML = '<option value="">(ninguna — usar mood procedural)</option>' +
            (r.music || []).map(a => `<option value="${escHtml(a.id)}">${escHtml(a.name)}</option>`).join("");
        $("logo-saved").innerHTML = '<option value="">(ninguno)</option>' +
            (r.logos || []).map(a => `<option value="${escHtml(a.id)}">${escHtml(a.name)}</option>`).join("");
        if (prevMusic) $("music-saved").value = prevMusic;
        if (prevLogo) $("logo-saved").value = prevLogo;
        musicId = $("music-saved").value || null;
        logoId = $("logo-saved").value || null;
    } catch (e) { /* ignore */ }
}
$("music-saved").onchange = () => { musicId = $("music-saved").value || null; saveCfg(); };
$("logo-saved").onchange = () => { logoId = $("logo-saved").value || null; saveCfg(); };

// ---------- Voces ----------
async function loadVoices() {
    const lang = $("lang").value;
    const r = await (await fetch(`/api/voices?lang=${lang}`)).json();
    const def = status.default_voice || "";
    $("voice").innerHTML = (r.voices || []).map(v =>
        `<option value="${escHtml(v.name)}" ${v.name === def ? "selected" : ""}>${escHtml(v.name)} · ${escHtml(v.gender)}</option>`).join("");
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
        r.models.map(m => `<option value="${escHtml(m.id)}">${escHtml(m.id)}</option>`).join("");
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
    await loadAssets();
    $("music-saved").value = r.id;
};
$("logo").onchange = async () => {
    const f = $("logo").files[0]; if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    const r = await (await fetch("/api/upload/logo", { method: "POST", body: fd })).json();
    logoId = r.id; $("logo-name").textContent = "✔ " + r.name;
    await loadAssets();
    $("logo-saved").value = r.id;
};

// ---------- Editor visual de escenas <-> JSON ----------
function syncPlanToJson() {
    if (!currentPlan) return;
    $("plan-json").value = JSON.stringify(currentPlan, null, 2);
}

function getActivePlan() {
    if (editorMode === "json") {
        currentPlan = JSON.parse($("plan-json").value);
        return currentPlan;
    }
    syncPlanToJson();
    return currentPlan;
}

function updateStats() {
    if (!currentPlan) return;
    const scenes = currentPlan.scenes || [];
    const words = scenes.reduce((acc, s) => acc + String(s.narration || "").trim().split(/\s+/).filter(Boolean).length, 0);
    const estSec = Math.round(words / 2.6);
    $("ed-stats").textContent = `${scenes.length} escenas · ~${words} palabras (~${estSec}s)`;
}

function sceneExtraField(sc, idx) {
    const t = sc.scene_type || "evidence";
    if (t === "terminal") {
        const val = (sc.terminal_lines || []).join("\n");
        return `<label>Líneas de terminal (una por línea)</label>
            <textarea rows="3" class="mono" onchange="edSceneLines(${idx}, this.value)">${escHtml(val)}</textarea>`;
    }
    if (t === "diagram" || t === "map" || t === "timeline") {
        const val = (sc.diagram_nodes || []).join("\n");
        return `<label>Nodos / pasos (uno por línea)</label>
            <textarea rows="3" onchange="edSceneNodes(${idx}, this.value)">${escHtml(val)}</textarea>`;
    }
    if (t === "stat") {
        return `<div class="two">
            <div><label>Cifra gigante</label><input type="text" value="${escHtml(sc.stat_value || "")}" onchange="edSceneField(${idx},'stat_value',this.value)"></div>
            <div><label>Etiqueta</label><input type="text" value="${escHtml(sc.stat_label || "")}" onchange="edSceneField(${idx},'stat_label',this.value)"></div>
        </div>`;
    }
    if (t === "brand") {
        return `<label>Subtítulo</label><input type="text" value="${escHtml(sc.subtitle || "")}" onchange="edSceneField(${idx},'subtitle',this.value)">`;
    }
    return `<label>Código / evidencia</label>
        <textarea rows="3" class="mono" onchange="edSceneField(${idx},'code_snippet',this.value)">${escHtml(sc.code_snippet || "")}</textarea>`;
}

function renderVisualEditor() {
    if (!currentPlan) return;
    $("ed-title").value = currentPlan.title || "";
    $("ed-desc").value = currentPlan.description || "";
    const scenes = currentPlan.scenes || [];
    $("ed-scenes").innerHTML = scenes.map((sc, idx) => {
        const typeOpts = SCENE_TYPES.map(t => `<option value="${t}" ${sc.scene_type === t ? "selected" : ""}>${t}</option>`).join("");
        return `<div class="scene-card">
            <div class="scene-card-head">
                <strong>ESCENA ${idx + 1}</strong>
                <div class="scene-actions">
                    <button type="button" class="mini" onclick="previewSceneIdx(${idx})" title="Previsualizar esta escena">👁</button>
                    <button type="button" class="mini" onclick="moveScene(${idx},-1)" ${idx === 0 ? "disabled" : ""} title="Subir">↑</button>
                    <button type="button" class="mini" onclick="moveScene(${idx},1)" ${idx === scenes.length - 1 ? "disabled" : ""} title="Bajar">↓</button>
                    <button type="button" class="mini" onclick="delScene(${idx})" title="Eliminar">✕</button>
                </div>
            </div>
            <div class="two">
                <div><label>Tipo</label><select onchange="edSceneType(${idx},this.value)">${typeOpts}</select></div>
                <div><label>Badge</label><input type="text" value="${escHtml(sc.badge || "")}" onchange="edSceneField(${idx},'badge',this.value)"></div>
            </div>
            <label>Titular en pantalla</label>
            <input type="text" value="${escHtml(sc.headline || "")}" onchange="edSceneField(${idx},'headline',this.value)">
            <label>Narración (voz)</label>
            <textarea rows="2" onchange="edSceneField(${idx},'narration',this.value)">${escHtml(sc.narration || "")}</textarea>
            ${sceneExtraField(sc, idx)}
        </div>`;
    }).join("");
    updateStats();
    syncPlanToJson();
}

$("ed-title").oninput = () => { if (currentPlan) { currentPlan.title = $("ed-title").value; syncPlanToJson(); } };
$("ed-desc").oninput = () => { if (currentPlan) { currentPlan.description = $("ed-desc").value; syncPlanToJson(); } };

window.edSceneField = (idx, key, val) => {
    currentPlan.scenes[idx][key] = val;
    if (key === "narration") updateStats();
    syncPlanToJson();
};
window.edSceneType = (idx, val) => {
    currentPlan.scenes[idx].scene_type = val;
    renderVisualEditor();
};
window.edSceneLines = (idx, val) => {
    currentPlan.scenes[idx].terminal_lines = val.split("\n").map(x => x.trim()).filter(Boolean);
    syncPlanToJson();
};
window.edSceneNodes = (idx, val) => {
    currentPlan.scenes[idx].diagram_nodes = val.split("\n").map(x => x.trim()).filter(Boolean);
    syncPlanToJson();
};
window.moveScene = (idx, dir) => {
    const arr = currentPlan.scenes;
    const j = idx + dir;
    if (j < 0 || j >= arr.length) return;
    [arr[idx], arr[j]] = [arr[j], arr[idx]];
    renderVisualEditor();
};
window.delScene = (idx) => {
    if ((currentPlan.scenes || []).length <= 1) { alert("El guion necesita al menos 1 escena."); return; }
    currentPlan.scenes.splice(idx, 1);
    renderVisualEditor();
};
$("btn-add-scene").onclick = () => {
    if (!currentPlan) return;
    currentPlan.scenes.push({
        id: currentPlan.scenes.length + 1,
        scene_type: "evidence",
        headline: "NUEVA ESCENA",
        badge: "ANÁLISIS",
        narration: "Escribe aquí lo que narrará la voz en esta escena.",
        terminal_lines: [],
        diagram_nodes: [],
        code_snippet: "// Detalle técnico",
    });
    renderVisualEditor();
};

function setEditorMode(mode) {
    if (mode === "visual" && editorMode === "json") {
        try { currentPlan = JSON.parse($("plan-json").value); }
        catch (e) { alert("Corrige el JSON antes de volver al editor visual: " + e.message); return; }
        renderVisualEditor();
    } else if (mode === "json") {
        syncPlanToJson();
    }
    editorMode = mode;
    $("visual-editor").classList.toggle("hidden", mode !== "visual");
    $("plan-json").classList.toggle("hidden", mode !== "json");
    $("mode-visual").classList.toggle("active", mode === "visual");
    $("mode-json").classList.toggle("active", mode === "json");
}
$("mode-visual").onclick = () => setEditorMode("visual");
$("mode-json").onclick = () => setEditorMode("json");

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
        currentPlan = r.plan;
        if (r.plan._theme) $("theme").value = r.plan._theme;
        if (r.plan._mood) $("music_mood").value = r.plan._mood;
        const est = r.plan._style ? ` · estilo: ${r.plan._style}` : "";
        $("script-title").textContent = "— " + (r.plan.title || "") + est;
        $("script-empty").classList.add("hidden");
        $("script-box").classList.remove("hidden");
        $("editor-switch").classList.remove("hidden");
        renderVisualEditor();
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
    try { plan = getActivePlan(); }
    catch (e) { alert("El guion no es JSON válido: " + e.message); return; }
    if (!plan) { alert("Genera un guion primero."); return; }
    $("btn-render").disabled = true;
    $("log").textContent = ""; $("bar-fill").style.width = "0%"; $("pct").textContent = "0%";
    $("result").classList.add("hidden");

    const body = {
        plan, lang: $("lang").value, voice: $("voice").value,
        rate: rateStr(), pitch: pitchStr(), theme: $("theme").value,
        music_id: $("music-saved").value || musicId,
        logo_id: $("logo-saved").value || logoId,
        music_mood: $("music_mood").value,
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

// ---------- Previsualizar cualquier escena ----------
window.previewSceneIdx = async (idx) => {
    let plan;
    try { plan = getActivePlan(); } catch (e) { alert("Guion no válido: " + e.message); return; }
    const scene = (plan.scenes || [])[idx];
    if (!scene) { alert("La escena no existe."); return; }
    const btn = $("btn-preview-scene");
    btn.textContent = `⏳ Renderizando escena ${idx + 1}...`;
    btn.disabled = true;
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
    btn.disabled = false;
};
$("btn-preview-scene").onclick = () => window.previewSceneIdx(0);

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
    const img = i.has_thumb ? `<img src="${escHtml(i.thumb_url)}" loading="lazy">`
        : (i.has_thumb_yt ? `<img src="${escHtml(i.thumb_yt_url)}" loading="lazy">` : '<div class="noimg">▶</div>');
    const proj = escHtml(i.project);
    return `<div class="lib-card">
        ${partBadge}
        <div class="thumb" onclick="document.getElementById('v_${proj}').play()">${img}</div>
        <video id="v_${proj}" src="${escHtml(i.video_url)}" preload="none" controls playsinline class="lib-video"></video>
        <div class="lib-title">${escHtml(i.title)}</div>
        <div class="lib-date">${escHtml(i.date)}</div>
        <div class="row">
            <a class="ghost mini" href="${escHtml(i.video_url)}" download>⬇</a>
            <button class="ghost mini" onclick="makePart2('${proj}')">+ Parte</button>
            <button class="ghost mini" onclick="libUpload('youtube','${proj}')">▶ YT</button>
            <button class="ghost mini" onclick="libUpload('tiktok','${proj}')">♪ TT</button>
            <button class="ghost mini" onclick="delVideo('${proj}')" title="Borrar">🗑</button>
        </div>
    </div>`;
}

async function loadLibrary() {
    const r = await (await fetch("/api/library")).json();
    const series = r.series || [];
    const items = r.items || [];
    $("lib-empty").classList.toggle("hidden", items.length > 0);
    $("previous_project").innerHTML = '<option value="">(ninguno — video nuevo)</option>' +
        items.map(i => `<option value="${escHtml(i.project)}">${escHtml(i.title)}</option>`).join("");
    $("lib-grid").innerHTML = series.map(s => {
        const isSeries = s.count > 1;
        const cards = s.parts.map(i => cardHtml(i, isSeries)).join("");
        const head = isSeries
            ? `<div class="series-head">📁 ${escHtml(s.title)} <span class="series-count">${s.count} partes</span></div>`
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
        auto_upload_youtube: $("batch_auto_yt").checked,
        auto_upload_tiktok: $("batch_auto_tt").checked,
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
    ws.onclose = () => { $("btn-batch").disabled = false; loadTopics(); };
};

async function loadTopics() {
    const r = await (await fetch("/api/topics")).json();
    const list = r.topics || [];
    $("history-badge").textContent = r.history_count ? `· ${r.history_count} producidos` : "";
    $("topic-list").innerHTML = list.length
        ? list.map(t => `<li><span>${escHtml(t)}</span><button class="mini" onclick="delTopic(${JSON.stringify(t).replace(/"/g, "&quot;")})">✕</button></li>`).join("")
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
    $("sch_auto_yt").checked = !!c.auto_upload_youtube;
    $("sch_auto_tt").checked = !!c.auto_upload_tiktok;
}
$("btn-sch-save").onclick = async () => {
    const cfg = {
        enabled: $("sch_enabled").checked, hour: +$("sch_hour").value, minute: +$("sch_minute").value,
        count: +$("sch_count").value, source: $("sch_source").value,
        lang: $("lang").value, provider: $("provider").value, model: $("model").value, theme: $("theme").value,
        voice: $("voice").value, music_mood: $("music_mood").value, branding: $("branding").checked,
        auto_upload_youtube: $("sch_auto_yt").checked, auto_upload_tiktok: $("sch_auto_tt").checked,
    };
    await fetch("/api/scheduler", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cfg) });
    alert("✔ Programación guardada. Funcionará mientras el panel esté abierto.");
};

// ---------- Presets (recordar última config) ----------
const CFG_FIELDS = ["provider", "model", "lang", "theme", "voice", "rate", "pitch", "num_scenes", "target_seconds", "music_mood", "style", "music-saved", "logo-saved"];
function saveCfg() {
    try {
        const cfg = {}; CFG_FIELDS.forEach(f => { if ($(f)) cfg[f] = $(f).value; });
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
        musicId = $("music-saved").value || null;
        logoId = $("logo-saved").value || null;
    } catch (e) { /* ignore */ }
}
[...CFG_FIELDS, "branding"]
    .forEach(id => { const el = $(id); if (el) el.addEventListener("change", saveCfg); });

// ---------- Init ----------
(async () => {
    await loadStatus();
    await loadVoices();
    await loadModels();
    await loadAssets();
    loadCfg();
    loadLibrary();
    if (new URLSearchParams(location.search).get("tiktok") === "connected") loadStatus();
})();
