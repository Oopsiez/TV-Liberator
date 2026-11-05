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
    el.innerHTML = tvs.map((t, i) => `
      <div class="tv pick" data-i="${i}" title="Click to select">
        <div class="name">${t.name || t.host}
          <span class="tag ${t.vendor}">${t.vendor}</span></div>
        <div class="muted">${t.host}${t.model ? " · " + t.model : ""}${
          t.firmware ? " · fw " + t.firmware : ""}</div>
        <div class="muted">${t.capability ? t.capability.note : ""}</div>
        <button class="selBtn">Select this TV</button>
      </div>`).join("");
    el.querySelectorAll(".tv.pick").forEach((d) => {
      d.onclick = () => selectTv(tvs[+d.dataset.i], d);
    });
    if (tvs.length === 1) selectTv(tvs[0], el.querySelector(".tv.pick"));
  } catch (e) { el.innerHTML = `<p class="muted">${e.message}</p>`; }
};

let selected = null;
async function selectTv(tv, node) {
  selected = tv;
  document.querySelectorAll(".tv.pick").forEach((d) => {
    d.classList.toggle("selected", d === node);
    d.querySelector(".selBtn").textContent =
      d === node ? "Selected \u2713" : "Select this TV";
  });
  $("#selTv").textContent =
    `Selected: ${tv.name || tv.host} (${tv.vendor}, ${tv.host})`;
  $("#lgPass").hidden = tv.vendor !== "lg";
  const pick = $("#appPick");
  try {
    const { apps } = await api(`/api/apps/catalog/${tv.vendor}`);
    pick.innerHTML = apps.map((a) =>
      `<option value="${a.id}">${a.name}</option>`).join("");
    pick.disabled = !apps.length;
    $("#install").disabled = !apps.length;
  } catch (e) { $("#installOut").textContent = "Error: " + e.message; }
}

$("#install").onclick = async () => {
  if (!selected) return;
  const out = $("#installOut");
  const btn = $("#install");
  btn.disabled = true;
  out.textContent = `Installing ${$("#appPick").selectedOptions[0].text} on ` +
    `${selected.host}… this can take a minute.`;
  try {
    const r = await post("/api/apps/install", {
      host: selected.host, vendor: selected.vendor,
      app_id: $("#appPick").value, passphrase: $("#lgPass").value.trim(),
    });
    out.textContent = `Installed ${r.package}.\n\n${r.output}`;
  } catch (e) { out.textContent = "Error: " + e.message; }
  finally { btn.disabled = false; }
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
