const $ = (s) => document.querySelector(s);
const api = async (url, opts) => {
  const r = await fetch(url, opts);
  const t = await r.text();
  let j; try { j = JSON.parse(t); } catch { j = { detail: t }; }
  if (!r.ok) throw new Error(j.detail || r.statusText);
  return j;
};
const post = (url, body) => api(url, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body || {}),
});

api("/api/version").then((v) => ($("#version").textContent = v.version));

$("#scan").onclick = async () => {
  const el = $("#tvs");
  el.innerHTML = '<p class="muted">Scanning…</p>';
  try {
    const { tvs } = await post("/api/discover");
    if (!tvs.length) {
      el.innerHTML = '<p class="muted">No TVs found. Make sure they are on ' +
        'and on this network.</p>';
      return;
    }
    el.innerHTML = tvs.map((t) => `
      <div class="tv">
        <div class="name">${t.name || t.host}
          <span class="tag ${t.vendor}">${t.vendor}</span></div>
        <div class="muted">${t.host}${t.model ? " · " + t.model : ""}${
          t.firmware ? " · fw " + t.firmware : ""}</div>
        <div class="muted">${t.capability ? t.capability.note : ""}</div>
      </div>`).join("");
  } catch (e) { el.innerHTML = `<p class="muted">${e.message}</p>`; }
};

$("#install").onclick = async () => {
  const out = $("#installOut");
  out.textContent = "Installing…";
  try {
    const r = await post("/api/samsung/install", {
      host: $("#pkgHost").value.trim(),
      package_path: $("#pkgPath").value.trim(),
    });
    out.textContent = r.output;
  } catch (e) { out.textContent = "Error: " + e.message; }
};

document.querySelectorAll(".planBtn").forEach((b) => {
  b.onclick = async () => {
    const r = await api(`/api/privacy/plan/${b.dataset.vendor}`);
    $("#planOut").textContent = JSON.stringify(r.plan, null, 2);
  };
});

document.querySelectorAll(".updBtn").forEach((b) => {
  b.onclick = async () => {
    const r = await api(`/api/updates/plan/${b.dataset.vendor}`);
    $("#updOut").textContent = JSON.stringify(r, null, 2);
  };
});

const renderGuard = (s) => {
  $("#guardStatus").innerHTML = s.running
    ? `<b>Running</b> · allowed ${s.allowed} · blocked ${s.blocked} ·
       ${s.allowed_domains.length} domains allowed`
    : "Stopped.";
};

$("#guardStart").onclick = async () => {
  const profiles = [...document.querySelectorAll(".prof:checked")]
    .map((c) => c.value);
  const extra = $("#extraAllow").value.split(",")
    .map((s) => s.trim()).filter(Boolean);
  try {
    renderGuard(await post("/api/guard/start",
      { profiles, extra_allow: extra }));
  } catch (e) { $("#guardStatus").textContent = "Error: " + e.message; }
};
$("#guardStop").onclick = async () =>
  renderGuard(await post("/api/guard/stop"));
api("/api/guard/status").then(renderGuard);
