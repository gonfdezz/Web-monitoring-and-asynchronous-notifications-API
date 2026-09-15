"use strict";

const REFRESH_MS = 10000;

const state = {
  sites: [],
  expandedId: null,
  loading: false,
};

const $ = (id) => document.getElementById(id);

// ---------- Capa de acceso a la API ----------

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    let detail = `Error ${response.status}`;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : detail;
    } catch (_) {
      // la respuesta no traía JSON; nos quedamos con el código
    }
    throw new Error(detail);
  }

  return response.status === 204 ? null : response.json();
}

// ---------- Pintado ----------

function showError(message) {
  const box = $("error");
  box.textContent = message;
  box.hidden = !message;
}

function formatLatency(ms) {
  if (ms === null || ms === undefined) return "—";
  return `${Math.round(ms)} ms`;
}

function formatTime(iso) {
  if (!iso) return "sin comprobar";
  return new Date(iso).toLocaleTimeString("es-ES");
}

function renderSummary() {
  const total = state.sites.length;
  const up = state.sites.filter((s) => s.status === "up").length;
  const down = state.sites.filter((s) => s.status === "down").length;

  $("summary").textContent = total === 0
    ? "Sin sitios vigilados"
    : `${up} de ${total} responden` + (down ? ` · ${down} sin respuesta` : "");
}

function buildRow(site) {
  const li = document.createElement("li");
  li.className = "site";

  const row = document.createElement("button");
  row.className = "site__row";
  row.type = "button";
  row.setAttribute("aria-expanded", String(state.expandedId === site.id));

  const light = document.createElement("span");
  light.className = `light light--${site.status}`;

  const info = document.createElement("span");
  const name = document.createElement("span");
  name.className = "site__name";
  name.textContent = site.name;
  const url = document.createElement("span");
  url.className = "site__url";
  url.textContent = site.url;
  info.append(name, url);

  const latency = document.createElement("span");
  latency.className = "site__latency";
  latency.textContent = formatTime(site.last_checked_at);

  const chevron = document.createElement("span");
  chevron.className = "site__latency";
  chevron.textContent = state.expandedId === site.id ? "−" : "+";

  row.append(light, info, latency, chevron);
  row.addEventListener("click", () => toggle(site.id));
  li.append(row);

  if (state.expandedId === site.id) {
    const detail = document.createElement("div");
    detail.className = "detail";
    detail.textContent = "Cargando histórico…";
    li.append(detail);
    loadDetail(site, detail);
  }

  return li;
}

function render() {
  const list = $("sites");
  list.replaceChildren(...state.sites.map(buildRow));
  $("empty").hidden = state.sites.length > 0;
  renderSummary();
}

// ---------- Detalle de un sitio ----------

async function loadDetail(site, container) {
  try {
    const [metrics, logs] = await Promise.all([
      api(`/sites/${site.id}/metrics?hours=24`).catch(() => null),
      api(`/sites/${site.id}/logs?hours=24&limit=60`),
    ]);

    container.replaceChildren();

    if (metrics) {
      const stats = document.createElement("div");
      stats.className = "detail__stats";
      stats.append(
        stat("Disponibilidad 24 h", `${metrics.uptime_percent} %`),
        stat("Latencia media", formatLatency(metrics.avg_response_time_ms)),
        stat("Percentil 95", formatLatency(metrics.p95_response_time_ms)),
        stat("Comprobaciones", String(metrics.total_checks)),
      );
      container.append(stats);
    }

    container.append(buildStrip(logs));

    const remove = document.createElement("button");
    remove.className = "remove";
    remove.type = "button";
    remove.textContent = "Dejar de vigilar";
    remove.addEventListener("click", () => removeSite(site));
    container.append(remove);
  } catch (error) {
    container.textContent = `No se pudo cargar el histórico: ${error.message}`;
  }
}

function stat(label, value) {
  const div = document.createElement("div");
  div.textContent = value;
  const small = document.createElement("span");
  small.textContent = label;
  div.append(small);
  return div;
}

function buildStrip(logs) {
  const strip = document.createElement("div");
  strip.className = "strip";

  if (logs.length === 0) {
    strip.textContent = "Todavía no hay comprobaciones.";
    return strip;
  }

  const ordered = [...logs].reverse();          // el más antiguo a la izquierda
  const max = Math.max(...ordered.map((l) => l.response_time_ms || 0), 1);

  for (const log of ordered) {
    const bar = document.createElement("div");
    bar.className = log.is_up ? "strip__bar" : "strip__bar strip__bar--down";
    bar.style.height = `${Math.max(((log.response_time_ms || 0) / max) * 100, 6)}%`;
    bar.title = log.is_up
      ? `${formatTime(log.checked_at)} · ${formatLatency(log.response_time_ms)}`
      : `${formatTime(log.checked_at)} · ${log.error || "sin respuesta"}`;
    strip.append(bar);
  }

  return strip;
}

// ---------- Acciones ----------

function toggle(id) {
  state.expandedId = state.expandedId === id ? null : id;
  render();
}

async function refresh() {
  if (state.loading) return;          // no solapar peticiones
  state.loading = true;
  try {
    state.sites = await api("/sites?limit=200");
    showError("");
    render();
  } catch (error) {
    showError(`No se pudo contactar con la API: ${error.message}`);
  } finally {
    state.loading = false;
  }
}

async function addSite() {
  const name = $("name").value.trim();
  const url = $("url").value.trim();
  const interval = Number($("interval").value);

  if (!name || !url) {
    showError("Hacen falta un nombre y una dirección.");
    return;
  }

  const button = $("add-btn");
  button.disabled = true;
  try {
    await api("/sites", {
      method: "POST",
      body: JSON.stringify({ name, url, check_interval: interval }),
    });
    $("name").value = "";
    $("url").value = "";
    showError("");
    await refresh();
  } catch (error) {
    showError(error.message);
  } finally {
    button.disabled = false;
  }
}

async function removeSite(site) {
  if (!confirm(`¿Dejar de vigilar ${site.name}? Se borrará su histórico.`)) return;
  try {
    await api(`/sites/${site.id}`, { method: "DELETE" });
    state.expandedId = null;
    await refresh();
  } catch (error) {
    showError(error.message);
  }
}

// ---------- Arranque ----------

$("add-btn").addEventListener("click", addSite);
$("url").addEventListener("keydown", (e) => { if (e.key === "Enter") addSite(); });

refresh();
setInterval(refresh, REFRESH_MS);