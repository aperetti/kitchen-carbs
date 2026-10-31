/* Kitchen Carbs tablet app. Concepts: okf/features/*.md. The only dose is the meal summary's, worked out on the server (okf/rules/no-dosing.md). */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const whole = x => Math.floor(x + 0.5);                       // okf/rules/whole-gram-rounding.md
const exact = (grams, cp100, qty = 1) => grams * cp100 / 100 * qty;
const fmtQty = q => "×" + (q % 1 ? q.toFixed(1) : q);
const itemG = i => Math.round(i.grams * (i.qty ?? 1) * 10) / 10;   // the food's weight: logged meals may still carry a quantity
const fmtG = g => `${+(+g).toFixed(1)} g`;
const EATEN = ["all", "most", "half", "little", "none"];
const CONTAINERS = { auto: "Auto", plate: "Plate", bowl: "Bowl", dressing: "Dressing container", counter: "On the counter (no dish)", package: "In its own package" };
const SOURCE = { fatsecret: "FatSecret", usda: "USDA FoodData Central", label: "Package label", "care-team": "Care team", openfoodfacts: "Open Food Facts" };
const pad2 = n => String(n).padStart(2, "0");
const localDay = (d = new Date()) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
const hhmm = (d = new Date()) => `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
const dayLabel = iso => new Date(iso + "T12:00").toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
const shiftDay = (iso, n) => { const d = new Date(iso + "T12:00"); d.setDate(d.getDate() + n); return localDay(d); };
const photoUrl = p => p ? "/photos/" + p : "";
// High-DPI photos (okf/design/components/plate-photo.md): the server makes 320–2400 px copies; the browser picks one.
const IMG_W = [320, 800, 1600, 2400];
const sized = (p, sizes) => p ? `src="/img/800/${p}" srcset="${IMG_W.map(w => `/img/${w}/${p} ${w}w`).join(", ")}" sizes="${sizes}"` : "";
const uid = () => (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2));

/* ---------- storage (per-tablet conveniences and the offline queue) ---------- */
const store = {
  get(k, d) { try { const v = localStorage.getItem("kc." + k); return v ? JSON.parse(v) : d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem("kc." + k, JSON.stringify(v)); } catch { /* storage full or blocked */ } },
};
const pinStore = {
  get() { try { return sessionStorage.getItem("kc.pin") || ""; } catch { return ""; } },
  set(v) { try { v ? sessionStorage.setItem("kc.pin", v) : sessionStorage.removeItem("kc.pin"); } catch { } },
};

const S = {
  session: null, foods: store.get("foods", []), offline: false,
  tags: store.get("tags", []), favs: store.get("favs", []), sizeRefs: [],
  confirm: store.get("confirm", { enabled: false, foods: [] }),   // this account's checked foods (okf/features/confirm-food.md)
  q: "", filter: store.get("filter", "all"), favSel: null, openCard: null,
  plate: store.get("plate", []).map(x => x.qty === 1 && x.base ? x   // older plates kept a ×quantity: fold it into the grams
    : { ...x, grams: Math.round(x.grams * (x.qty ?? 1) * 10) / 10, base: x.base ?? x.grams, qty: 1 }), queue: store.get("queue", []), plateTime: null,
  log: { day: localDay(), data: null, sel: null, selEntry: null, adding: false, period: "day", stats: null, glucose: {} },
  m: { tab: "foods", food: null, addTab: "lookup", busy: {}, err: "", scan: null, look: { q: "", res: null, busy: false } },
};

/* ---------- api ---------- */
class ApiError extends Error { constructor(status, msg, signin = false) { super(msg); this.status = status; this.signin = signin; } }
async function api(path, { method = "GET", body, form, parent = false } = {}) {
  const headers = {};
  if (body) headers["Content-Type"] = "application/json";
  if (parent) headers["X-Parent-Pin"] = pinStore.get();
  const mine = store.get("push", "");   // this device's own saves don't notify it (okf/features/notify-family.md)
  if (mine) headers["X-KC-Push"] = mine;
  let r;
  try { r = await fetch(path, { method, headers, body: form || (body && JSON.stringify(body)) }); }
  catch { setOffline(true); throw new ApiError(0, "Can't reach the kitchen server."); }
  setOffline(false);
  const data = r.headers.get("content-type")?.includes("json") ? await r.json() : await r.text();
  if (!r.ok) {
    let msg = data?.detail;
    if (Array.isArray(msg)) msg = msg.map(d => d.msg.replace(/^Value error, /, "")).join(" ");
    if (r.status === 401 && data?.signin) showSignIn();   // this device's sign-in ended (okf/features/sign-in.md)
    throw new ApiError(r.status, msg || `Request failed (${r.status}).`, !!data?.signin);
  }
  return data;
}

let toastTimer;
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => (t.hidden = true), 3200);
}
function setOffline(v) { if (S.offline !== v) { S.offline = v; renderStatus(); } }
function renderStatus() {
  const parts = [];
  const env = S.session?.env;
  if (env === "qa") parts.push("QA: a copy of the kitchen's data for trying new versions. Nothing here reaches the real log.");
  else if (env === "dev") parts.push("Development: sample data.");
  if (S.offline) parts.push("Can't reach the kitchen server. Showing the foods saved on this tablet.");
  const q = S.queue.length;
  if (q) parts.push(`${q} log item${q > 1 ? "s" : ""} waiting to sync.`);
  const bad = S.queue.find(m => m.error);
  if (bad) parts.push(`Not saved: ${bad.error}`);
  $("#status").hidden = !parts.length;
  $("#status").textContent = parts.join(" ");
}

/* ---------- routing ---------- */
const VIEWS = ["foods", "plate", "log", "manage"];
function route() {
  if (S.signedOut) return showSignIn();
  let h = location.hash.slice(1).split("/")[0];
  if (h === "plate" && splitMode()) { history.replaceState(history.state, "", "#foods"); h = "foods"; }   // the plate is beside the foods
  const v = VIEWS.includes(h) ? h : "foods";
  placePlate();
  if (v !== "manage") { stopScanner(); S.rawStop?.(); S.rawStop = null; S.m.look.scanning = false; }
  else if (!mBooted && history.state?.m) mApply(history.state.m);   // a reload keeps the entry: pick up where it was
  else if (!history.state?.m) {   // arrived from a link: read the place from the address, then record it
    mFromHash();
    history.replaceState({ m: { ...mSnap(), depth: 0 } }, "", mHash(mSnap()));
  }
  if (v === "manage") mBooted = true;
  VIEWS.forEach(x => ($("#v-" + x).hidden = x !== v));
  document.querySelectorAll("#tabs a").forEach(a => a.dataset.v === v ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
  ({ foods: () => { renderFoods(); if (splitMode()) renderPlate(); }, plate: renderPlate, log: () => loadLog(S.log.day), manage: renderManage })[v]();
  renderPlatebar(v);
}
addEventListener("hashchange", route);

/* ---------- foods ---------- */
async function loadFoods() {
  try {
    [S.foods, S.tags, S.favs, S.sizeRefs, S.confirm] = await Promise.all([api("/api/foods"), api("/api/tags"), api("/api/favorites"), api("/api/size-refs"), api("/api/confirmations")]);
    store.set("foods", S.foods); store.set("tags", S.tags); store.set("favs", S.favs); store.set("confirm", S.confirm);
  } catch { /* keep the cached lists */ }
}
/* When the app opens, show the meal for the time of day if there is a tag for it (okf/features/browse-foods.md) */
function pickMealFilter() {
  const name = suggestName().toLowerCase(), tag = S.tags.find(t => t.name.trim().toLowerCase() === name);
  if (tag) { S.filter = tag.id; store.set("filter", S.filter); }
}
async function loadFavs() { try { S.favs = await api("/api/favorites"); store.set("favs", S.favs); } catch { } }
const suggestName = (t = hhmm()) => t < "10:30" ? "Breakfast" : t < "15:00" ? "Lunch" : "Dinner";
const foodById = id => S.foods.find(f => f.id === id);
const shownPhoto = p => p.photo.styled || p.photo.original;

/* Foods: a grid of cards; each portion button adds to the plate (okf/features/browse-foods.md, okf/features/view-food.md) */
const carbRange = f => f.range ? (f.range[0] === f.range[1] ? `${f.range[0]} g carbs` : `${f.range[0]}–${f.range[1]} g carbs`) : "No portions yet";
function renderFoods() {
  if (!["all", "fav"].includes(S.filter) && !S.tags.some(t => t.id === S.filter)) S.filter = "all";
  const filters = [["fav", "Favorites"], ["all", "All"], ...S.tags.map(t => [t.id, t.name])];
  $("#cats").innerHTML = filters.map(([k, l]) => `<button data-filter="${k}" class="${k === S.filter ? "on" : ""}">${esc(l)}</button>`).join("");
  if (S.filter === "fav") return renderFavorites();
  const q = S.q.trim().toLowerCase();
  const list = S.foods.filter(f => (S.filter === "all" || f.tags.includes(S.filter)) && (!q || f.name.toLowerCase().includes(q)));
  const more = otherMatches(list);
  $("#foodList").innerHTML = list.length ? list.map(foodCard).join("") + more
    : more ? `<div class="empty"><p>Nothing in ${esc(filterName())} matches.</p></div>${more}`
    : `<div class="empty">${!S.foods.length ? "No foods yet. A parent can add them in Manage."
        : `<p>No foods match.</p>${S.q.trim().length >= 2 && S.session ? `<p><button class="btn" data-act="add-search">Look up “${esc(S.q.trim())}” and add it</button></p>
           <p class="meta">A parent checks the numbers first.</p>` : ""}`}</div>`;
}
/* A search inside a tag or Favorites also finds foods outside it, listed after (okf/features/browse-foods.md) */
const filterName = () => S.filter === "fav" ? "Favorites" : S.tags.find(t => t.id === S.filter)?.name || "this category";
function otherMatches(shown) {
  const q = S.q.trim().toLowerCase();
  if (!q || S.filter === "all") return "";
  const ids = new Set(shown.map(f => f.id));
  const rest = S.foods.filter(f => !ids.has(f.id) && f.name.toLowerCase().includes(q));
  return rest.length ? `<h3 class="morehead">In other categories</h3>${rest.map(foodCard).join("")}` : "";
}
/* Fiber, for reference only: never taken off the carbs (okf/domain/food.md) */
const fiberIn = (f, g) => Math.round(g * f.fiber_per_100g / 10) / 10;
const fiberText = (f, g) => f.fiber_per_100g == null ? "" : ` (including ${fiberIn(f, g)} g fiber)`;
function foodCard(f) {
  const p0 = f.portions[0], img = p0 && shownPhoto(p0), open = S.openCard === f.id;
  const verified = f.trust === "parent-verified" ? `verified ${dayLabel(f.verified_at)}` : `<span class="warn">not verified</span>`;
  const tags = [f.trust !== "parent-verified" && "Not verified"].filter(Boolean);
  const onPlate = S.plate.filter(x => x.food_id === f.id).reduce((g, x) => g + itemG(x), 0);   // shows it was added (okf/features/view-food.md)
  const estimated = f.portions.filter(p => p.photo.estimated && !p.photo.original).map(p => esc(p.label));
  const serving = f.portions[0];
  return `<article class="card ${open ? "open" : ""} ${serving ? "addable" : ""}" ${serving ? `data-addcard="${esc(f.id)}" tabindex="0" role="button" aria-pressed="${onPlate > 0}" aria-label="${esc(f.name)}, ${esc(serving.label)}, ${serving.carbs} grams of carbs. Tap to ${onPlate ? "take off" : "add to"} the plate"` : ""}>
    <div class="cimg">${img ? `<img ${sized(img, "(min-width: 1100px) 300px, (min-width: 681px) 33vw, 50vw")} alt="" loading="lazy">` : `<span class="noimg">No photo yet</span>`}
      ${tags.length ? `<div class="ctags">${tags.map(t => `<span>${t}</span>`).join("")}</div>` : ""}
      ${onPlate ? `<span class="onplate" title="On the plate · ${fmtG(onPlate)}" aria-label="On the plate, ${fmtG(onPlate)}">✓</span>` : ""}
      <b class="cname" title="${esc(f.name)}"><span>${esc(f.name)}</span></b>
      <button class="info" data-info="${esc(f.id)}" aria-expanded="${open}" aria-label="Details for ${esc(f.name)}">${open ? "×" : "i"}</button>
      ${open ? `<div class="cinfo" data-stay><b>${esc(f.name)}</b>
        <a href="#manage/foods/${encodeURIComponent(f.id)}" class="cedit">Edit in Manage</a>
        <span>${f.portions.map(p => `${esc(p.label)} = ${p.grams} g, ${p.carbs} g carbs${fiberText(f, p.grams)}`).join(" · ") || "No portions yet. A parent can add one in Manage."}</span>
        <span>${f.carbs_per_100g} g carbs per 100 g${f.basis && f.basis !== "as-sold" ? ` ${STATE[f.basis]}` : ""}${f.cook_ratio ? ` · cooked ×${+f.cook_ratio.toFixed(2)}, weighed ${dayLabel(f.cook_measured_at)}` : ""}</span>
        ${estimated.length ? `<span class="warn">Estimated photo: ${estimated.join(", ")}. Gemini drew ${estimated.length > 1 ? "them" : "it"}; the amount may not match.</span>` : ""}
        <span>${esc(SOURCE[f.source_kind] || f.source_kind)} · ${esc(f.source_ref)} · ${verified}${f.barcode && !f.source_ref.includes(f.barcode) ? ` · barcode ${esc(f.barcode)}` : ""}</span>
        ${f.notes ? `<span>${esc(f.notes)}</span>` : ""}
        ${f.label_photo ? `<a href="${photoUrl(f.label_photo)}" target="_blank" rel="noopener">View the nutrition label</a>` : ""}</div>` : ""}</div>
  </article>`;
}

/* ---------- favorite plates (okf/features/favorite-plates.md) ---------- */
const favSummary = f => f.items.map(i => `${i.food_name} ${i.grams ? fmtG(itemG(i)) : fmtQty(i.qty)}`).join(" · ");
const orphaned = f => f.items.every(i => i.missing);   // no foods left (okf/domain/favorite-plate.md)
let confirmOrphans = 0, confirmDrop = 0;
function renderFavorites() {
  const q = S.q.trim().toLowerCase();
  const list = S.favs.filter(f => !q || f.name.toLowerCase().includes(q) || favSummary(f).toLowerCase().includes(q));
  const n = S.favs.filter(orphaned).length;
  $("#foodList").innerHTML = (n ? `<p class="orphanbar">${n} favorite${n > 1 ? "s have" : " has"} no foods left.
      <button class="linkbtn" data-act="fav-orphans">${Date.now() - confirmOrphans < 4000 ? `Tap again to remove ${n > 1 ? "them" : "it"}` : `Remove ${n > 1 ? "them" : "it"}`}</button></p>` : "")
    + (list.length ? list.map(f => {
    const img = f.photo || f.items.find(i => i.photo)?.photo, open = S.favSel === f.id;
    const usable = !f.items.every(i => i.missing);
    return `<article class="card ${open ? "open" : ""} ${usable ? "addable" : ""}" ${usable ? `data-favuse="${f.id}" tabindex="0" role="button" aria-label="Put ${esc(f.name)}, ${f.total} grams of carbs, on the plate"` : ""}>
      <div class="cimg">${img ? `<img ${sized(img, "(min-width: 1100px) 300px, 50vw")} alt="" loading="lazy">` : `<span class="noimg"></span>`}
        ${f.missing ? `<div class="ctags"><span>${orphaned(f) ? "No foods left" : `${f.missing} item${f.missing > 1 ? "s" : ""} missing`}</span></div>` : ""}
        <b class="cname" title="${esc(f.name)}"><span>${esc(f.name)}</span></b>
        <button class="info" data-favinfo="${f.id}" aria-expanded="${open}" aria-label="More for ${esc(f.name)}">${open ? "×" : "i"}</button>
        ${open ? `<div class="cinfo" data-stay><b>${esc(f.name)}</b><span>${esc(favSummary(f))} · ${f.total} g carbs</span>
          <span>Carbs use today's food values; tune each item's grams on the plate.</span>
          ${f.photo ? `<span class="warn">Plate photo combined by Gemini from the food photos; the amounts may not match.</span>` : ""}
          ${usable ? `<button type="button" class="linkbtn" data-act="fav-photo">${f.photo_candidate ? "Check the new plate photo" : f.photo ? "New plate photo" : "Make a plate photo"}</button>` : ""}
          <form class="cmtform" id="favRename"><input id="favName" maxlength="60" value="${esc(f.name)}" aria-label="Favorite name"><button class="btn small">Rename</button></form>
          ${f.missing && !orphaned(f) ? `<span class="warn">Gone from the food list: ${esc(f.items.filter(i => i.missing).map(i => i.food_name).join(", "))}</span>
            <button type="button" class="linkbtn" data-act="fav-drop">${Date.now() - confirmDrop < 4000 ? "Tap again to remove them" : `Remove the missing item${f.missing > 1 ? "s" : ""}`}</button>` : ""}
          <button type="button" class="linkbtn" data-act="fav-unpin">${confirmUnpin && Date.now() - confirmUnpin < 4000 ? "Tap again to unpin" : "Unpin this favorite"}</button></div>` : ""}</div>
    </article>`;
  }).join("") : `<div class="empty">${S.favs.length ? "No favorites match." : "No favorite plates yet. Build a plate, then tap Pin as favorite. You can also pin a meal from the log."}</div>`)
    + otherMatches([]);
}
let confirmUnpin = 0;
function useFavorite(f) {
  const ok = f.items.filter(i => !i.missing);
  for (const i of ok) {
    const same = S.plate.find(x => x.portion_id === i.portion_id);
    if (same) same.grams = Math.min(2000, r1(same.grams + itemG(i) * stateFactor(same)));   // favorites keep the food's own state's grams
    else S.plate.push({ key: uid(), food_id: i.food_id, food_name: i.food_name, portion_id: i.portion_id, portion_label: i.portion_label,
                        grams: itemG(i), base: i.grams, carbs_per_100g: i.carbs_per_100g, qty: 1, photo: i.photo });
  }
  savePlate();
  const missing = f.items.filter(i => i.missing).map(i => i.food_name);
  toast(missing.length ? `Added ${f.name}. Left out: ${missing.join(", ")} (no longer in the food list).` : `Added ${f.name} to the plate`);
}
/* A favorite's plate photo, combined by Gemini from its foods' photos and checked before use (okf/features/favorite-plates.md) */
const favDlg = $("#favPhotoDialog");
function openFavPhoto(id) { S.fp = { id, busy: false, started: 0, err: null, pinErr: null }; favDlg.showModal(); drawFavPhoto(); }
function drawFavPhoto() {
  const s = S.fp, f = s && S.favs.find(x => x.id === s.id);
  if (!f) { if (favDlg.open) favDlg.close(); return; }
  const ok = f.items.filter(i => !i.missing), cand = f.photo_candidate, big = "(min-width: 760px) 720px, 100vw";
  const inputs = `<div class="fpin">${ok.map(i => `<figure>${i.photo ? `<img ${sized(i.photo, "160px")} alt="">` : `<span class="noimg">No photo</span>`}
      <figcaption>${esc(i.food_name)}<small>${fmtG(itemG(i))}${i.photo ? "" : " · described by name"}</small></figcaption></figure>`).join("")}</div>`;
  let body;
  if (!pinStore.get()) body = `<form class="cmtform" id="fpPin"><input id="fpPinIn" type="password" inputmode="numeric" autocomplete="current-password" placeholder="Parent PIN" aria-label="Parent PIN"><button class="btn small">Unlock</button></form>
      ${s.pinErr ? `<p class="err">${esc(s.pinErr)}</p>` : `<p class="meta">Making a photo needs the parent PIN.</p>`}`;
  else if (s.busy) body = `<div class="fpbusy"><div class="jobbar" role="progressbar" aria-label="Making the photo"><i></i></div>
      <span class="meta">Gemini is combining the photos · <span data-fpsince>0 s</span></span></div>`;
  else if (cand) body = `<figure class="fpres"><img ${sized(cand, big)} alt="New plate photo"></figure>
      <p class="meta">Check that every food is there, in its own dish, and that the amounts look right. It will be labelled as combined by Gemini; carbs never come from the photo.</p>
      ${s.err ? `<p class="err">${esc(s.err)}</p>` : ""}
      <div class="actions"><button class="btn primary" data-fp="accept">Use this photo</button><button class="btn" data-fp="make">Try again</button><button class="btn quiet" data-fp="discard">Discard</button></div>`;
  else body = `${f.photo ? `<figure class="fpres"><img ${sized(f.photo, big)} alt="Current plate photo"><figcaption>Current plate photo</figcaption></figure>` : ""}
      ${s.err ? `<p class="err">${esc(s.err)}</p>` : ""}
      <div class="actions"><button class="btn primary" data-fp="make">${f.photo ? "Make a new one" : "Make the photo"}</button>${f.photo ? `<button class="btn quiet" data-fp="remove">Remove plate photo</button>` : ""}</div>`;
  favDlg.innerHTML = `<div class="dlghead"><b>Plate photo · ${esc(f.name)}</b><button class="rm" data-fp="close" aria-label="Close">×</button></div>
    <div class="dlgbody"><p class="meta">Gemini puts ${ok.length > 1 ? `these ${ok.length} foods` : "this food"} together in one photo, each in its own dish, with the amounts in this favorite.</p>${inputs}${body}</div>`;
}
favDlg.addEventListener("click", async e => {
  if (e.target === favDlg) return favDlg.close();   // a tap on the backdrop
  const t = e.target.closest("[data-fp]"), s = S.fp; if (!t || !s || s.busy) return;
  const act = t.dataset.fp;
  if (act === "close") return favDlg.close();
  s.err = null;
  if (act === "make") {
    s.busy = true; s.started = Date.now(); drawFavPhoto();
    const tick = setInterval(() => { const el = favDlg.querySelector("[data-fpsince]"); if (el) el.textContent = `${Math.round((Date.now() - s.started) / 1000)} s`; }, 1000);
    try { await api(`/api/favorites/${s.id}/photo`, { method: "POST", parent: true }); }
    catch (err) { if (err.status === 401) pinStore.set(""); s.err = err.message; }
    clearInterval(tick); s.busy = false;
  } else {
    try { await api(`/api/favorites/${s.id}/photo/review`, { method: "POST", parent: true, body: { action: act } }); }
    catch (err) { if (err.status === 401) pinStore.set(""); s.err = err.message; }
  }
  await loadFavs(); renderFoods();
  if (S.fp !== s) return;   // closed while Gemini worked: the new photo waits in the favorite's details
  if (act === "accept" && !s.err) { favDlg.close(); toast("Plate photo saved"); } else drawFavPhoto();
});
favDlg.addEventListener("submit", async e => {
  if (e.target.id !== "fpPin") return; e.preventDefault();
  pinStore.set($("#fpPinIn").value);
  try { await api("/api/pin/check", { method: "POST", parent: true }); S.fp.pinErr = null; }
  catch (err) { pinStore.set(""); S.fp.pinErr = err.message; }
  drawFavPhoto();
});
favDlg.addEventListener("close", () => { S.fp = null; favDlg.innerHTML = ""; });
async function pinFavorite(path, body) {
  try { const f = await api(path, { method: "POST", body }); await loadFavs(); toast(`Pinned "${f.name}" to Favorites`); return true; }
  catch (err) { toast(err.message); return false; }
}

document.addEventListener("input", e => { if (e.target.id === "q") { S.q = e.target.value; renderFoods(); } });
// Scan barcodes from the foods page: Scan several, and Complete comes back here (okf/features/food-lookup.md)
$("#bulkScan").addEventListener("click", () => { S.batchFromFoods = true; if (S.m.batch) S.m.batch.focus = null; });
$("#v-foods").addEventListener("click", async e => {
  if (e.target.closest("[data-stay]") && !e.target.closest("[data-act]")) return;   // reading or renaming in the details
  const t = e.target.closest("[data-filter],[data-info],[data-favinfo],[data-act],[data-addcard],[data-favuse]"); if (!t) return;
  if (t.dataset.act === "add-search") { openAddDialog(S.q.trim()); return; }
  if (t.dataset.filter) { const k = t.dataset.filter; S.filter = ["fav", "all"].includes(k) ? k : +k; store.set("filter", S.filter); renderFoods(); }
  else if (t.dataset.addcard) {
    const f = foodById(t.dataset.addcard);
    if (S.plate.some(x => x.food_id === f.id)) {   // a second tap takes it off the plate again
      S.plate = S.plate.filter(x => x.food_id !== f.id); savePlate(); flash(t); toast(`Removed ${f.name}`);
    } else if (f.portions.length > 1) openPortionPick(f, t);   // pick the starting amount (okf/features/browse-foods.md)
    else addFromCard(t, f, f.portions[0].id);
  }
  else if (t.dataset.info) { S.openCard = S.openCard === t.dataset.info ? null : t.dataset.info; renderFoods(); }
  else if (t.dataset.favuse) { useFavorite(S.favs.find(x => x.id === +t.dataset.favuse)); flash(t); }
  else if (t.dataset.favinfo) { S.favSel = S.favSel === +t.dataset.favinfo ? null : +t.dataset.favinfo; confirmUnpin = 0; renderFavorites(); }
  else if (t.dataset.act === "fav-orphans") {   // a second tap within 4 s confirms
    if (Date.now() - confirmOrphans > 4000) { confirmOrphans = Date.now(); renderFoods(); return; }
    confirmOrphans = 0;
    try { const r = await api("/api/favorites/remove-orphans", { method: "POST" }); await loadFavs(); renderFoods(); toast(`Removed ${r.removed} favorite${r.removed === 1 ? "" : "s"} with no foods left`); }
    catch (err) { toast(err.message); }
  }
  else if (t.dataset.act === "fav-drop") {
    if (Date.now() - confirmDrop > 4000) { confirmDrop = Date.now(); renderFoods(); return; }
    confirmDrop = 0;
    try { const r = await api(`/api/favorites/${S.favSel}/drop-missing`, { method: "POST" }); await loadFavs(); renderFoods();
          toast(`Removed ${r.removed_items} missing item${r.removed_items === 1 ? "" : "s"}`); }
    catch (err) { toast(err.message); }
  }
  else if (t.dataset.act === "fav-photo") openFavPhoto(S.favSel);
  else if (t.dataset.act === "fav-unpin") {
    if (Date.now() - confirmUnpin > 4000) { confirmUnpin = Date.now(); t.textContent = "Tap again to unpin"; return; }
    try { await api(`/api/favorites/${S.favSel}`, { method: "DELETE" }); await loadFavs(); S.favSel = null; renderFoods(); toast("Unpinned"); } catch (err) { toast(err.message); }
  }
  else if (t.dataset.act === "side-remove") { S.plate = S.plate.filter(x => x.key !== t.closest("[data-key]").dataset.key); savePlate(); }
  else if (t.dataset.act === "side-clear") { S.plate = []; S.plateTime = null; savePlate(); }
});
function addFromCard(card, f, portionId) {
  const from = (card.querySelector(".cimg img") || card.querySelector(".cimg") || card).getBoundingClientRect(), src = card.querySelector(".cimg img")?.currentSrc;
  addToPlate(f.id, portionId);
  if (S.q) {   // searching for several foods in a row: clear it and keep typing (okf/features/browse-foods.md)
    S.q = ""; $("#q").value = ""; renderFoods(); $("#q").focus();
  } else {   // only the tapped card animates
    const c = card.isConnected ? card : $(`[data-addcard="${CSS.escape(f.id)}"]`);
    if (c) { flash(c); flash(c.querySelector(".onplate"), "fresh"); }
  }
  showJustAdded(); flyToPlate(from, src);
}
/* A food with several portions: choose the starting amount; the plate slider still sets any weight (okf/design/components/portion-tabs.md) */
const pickDlg = $("#portionDialog");
let pickFor = null;
function openPortionPick(f, card) {
  pickFor = { f, card };
  pickDlg.innerHTML = `<div class="dlghead"><b>${esc(f.name)}</b><button class="rm" data-pick="close" aria-label="Close">×</button></div>
    <div class="dlgbody"><p class="meta">Pick a portion. You can change the weight on the plate.</p>
      <ul class="pickrows">${f.portions.map(p => { const img = shownPhoto(p); return `<li><button data-pick="${p.id}">
        ${img ? `<img ${sized(img, "96px")} alt="">` : `<span class="noimg"></span>`}
        <span class="t">${esc(p.label)}<small>${fmtG(p.grams)}</small></span><span class="c">${p.carbs} g carbs</span></button></li>`; }).join("")}</ul></div>`;
  pickDlg.showModal();
}
pickDlg.addEventListener("click", e => {
  if (e.target === pickDlg) return pickDlg.close();   // a tap on the backdrop
  const t = e.target.closest("[data-pick]"); if (!t || !pickFor) return;
  const { f, card } = pickFor; pickDlg.close();
  if (t.dataset.pick !== "close") addFromCard(card, f, +t.dataset.pick);
});
pickDlg.addEventListener("close", () => { pickFor = null; pickDlg.innerHTML = ""; });
function showJustAdded() {   // the plate pane lights up the row that changed and brings it into view
  const row = splitMode() && S.justAdded && $(`#platePane [data-key="${S.justAdded}"]`);
  if (row) row.scrollIntoView({ block: "nearest", behavior: "smooth" });
  setTimeout(() => { S.justAdded = null; }, 50);
}
/* The tapped food's photo flies to the plate count, which bumps (okf/features/browse-foods.md) */
const plateTarget = () => splitMode() ? $("#platePane .total .n") || $("#platePane")
  : $("#plateCount")?.offsetParent ? $("#plateCount").closest("a") : $("#pbTotal");
function flyToPlate(a, src) {
  const target = plateTarget(); if (!target) return;
  const bump = () => flash(plateTarget(), "bump");
  if (matchMedia("(prefers-reduced-motion: reduce)").matches || !a.width) return bump();
  const b = target.getBoundingClientRect(), size = Math.min(a.width, a.height, 160);
  const g = document.createElement(src ? "img" : "span"); if (src) g.src = src;
  g.className = "flyer"; g.setAttribute("aria-hidden", "true");
  Object.assign(g.style, { left: `${a.left + a.width / 2 - size / 2}px`, top: `${a.top + a.height / 2 - size / 2}px`, width: `${size}px`, height: `${size}px` });
  document.body.append(g);
  const dx = b.left + b.width / 2 - (a.left + a.width / 2), dy = b.top + b.height / 2 - (a.top + a.height / 2), end = 24 / size;
  const fly = g.animate([
    { transform: "translate(0, 0) scale(1)", opacity: 1 },
    { transform: `translate(${dx * 0.45}px, ${dy * 0.45 - 40}px) scale(${(1 + end) / 2})`, opacity: 0.95, offset: 0.5 },
    { transform: `translate(${dx}px, ${dy}px) scale(${end})`, opacity: 0.4 }], { duration: 550, easing: "cubic-bezier(.45, 0, .55, 1)" });
  fly.onfinish = fly.oncancel = () => { g.remove(); bump(); };
}
const flash = (el, cls = "added") => { if (!el) return; el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); };   // replay a short animation
$("#v-foods").addEventListener("keydown", e => {   // cards are buttons for the keyboard too
  if ((e.key === "Enter" || e.key === " ") && e.target.matches("[data-addcard],[data-favuse]")) { e.preventDefault(); e.target.click(); }
});
$("#v-foods").addEventListener("submit", async e => {
  if (e.target.id !== "favRename") return; e.preventDefault();
  const name = $("#favName").value.trim(); if (!name) return;
  try { await api(`/api/favorites/${S.favSel}`, { method: "PUT", body: { name } }); await loadFavs(); renderFoods(); } catch (err) { toast(err.message); }
});

/* ---------- plate (okf/features/build-plate.md) ---------- */
function savePlate() {
  store.set("plate", S.plate); renderPlatebar();
  if (splitMode() && $("#platePane").contains($("#plateView"))) renderPlate();
  refreshBadges();   // the 'On plate' badges follow the plate, quietly
}
/* Update the 'On plate' badges in place: redrawing the grid would replay every badge's entrance. */
function refreshBadges() {
  document.querySelectorAll("#foodList [data-addcard]").forEach(card => {
    const g = S.plate.filter(x => x.food_id === card.dataset.addcard).reduce((a, x) => a + itemG(x), 0);
    let b = card.querySelector(".onplate");
    card.setAttribute("aria-pressed", g > 0);
    if (!g) { b?.remove(); return; }
    if (!b) { b = document.createElement("span"); b.className = "onplate"; card.querySelector(".cimg").insertBefore(b, card.querySelector(".cname")); }
    b.textContent = "✓"; b.title = `On the plate · ${fmtG(g)}`; b.setAttribute("aria-label", `On the plate, ${fmtG(g)}`);
  });
}

/* Tablets and computers: Foods and the plate side by side, with a draggable divider (okf/design/components/plate-bar.md) */
const SPLIT_MQ = matchMedia("(min-width: 900px)");
const splitMode = () => SPLIT_MQ.matches;
function placePlate() {   // one plate element: in the Foods screen's right pane when split, on its own screen otherwise
  const pv = $("#plateView"), home = splitMode() ? $("#platePane") : $("#v-plate");
  if (pv.parentElement !== home) home.appendChild(pv);
}
const setSplit = f => { f = Math.min(.75, Math.max(.3, f)); $("#v-foods").style.setProperty("--split", `${(f * 100).toFixed(1)}%`); return f; };
setSplit(+store.get("split", .5));
SPLIT_MQ.addEventListener("change", () => {   // rotating a tablet: only Foods and Plate change layout, so a half-typed form elsewhere is kept
  const v = location.hash.slice(1).split("/")[0] || "foods";
  if (v === "foods" || v === "plate") route(); else placePlate();
});
(() => {
  const bar = $("#splitter"); let drag = null;
  bar.addEventListener("pointerdown", e => { drag = { id: e.pointerId }; bar.setPointerCapture(e.pointerId); bar.classList.add("on"); });
  bar.addEventListener("pointermove", e => {
    if (!drag || e.pointerId !== drag.id) return;
    const r = $("#v-foods").getBoundingClientRect(); drag.f = setSplit((e.clientX - r.left) / r.width);
  });
  const end = () => { if (!drag) return; if (drag.f) store.set("split", drag.f); drag = null; bar.classList.remove("on"); };
  bar.addEventListener("pointerup", end); bar.addEventListener("pointercancel", end);
  bar.addEventListener("keydown", e => {
    const d = { ArrowLeft: -.05, ArrowRight: .05 }[e.key]; if (!d) return;
    e.preventDefault(); store.set("split", setSplit(+store.get("split", .5) + d));
  });
  bar.addEventListener("dblclick", () => store.set("split", setSplit(.5)));
})();
function addToPlate(foodId, portionId) {
  const f = foodById(foodId), p = f?.portions.find(x => x.id === portionId); if (!p) return;
  const same = S.plate.find(x => x.portion_id === p.id);
  if (same) same.grams = Math.min(2000, r1(same.grams + p.grams * stateFactor(same)));
  else {   // weighed as served: cooked when the food has a measured ratio (okf/domain/plate.md)
    const x = { key: uid(), food_id: f.id, food_name: f.name, portion_id: p.id, portion_label: p.label, base: p.grams, qty: 1, photo: shownPhoto(p),
                basis: f.basis || "as-sold", state: startState(f.basis, f.cook_ratio), cp_basis: f.carbs_per_100g, ratio: f.cook_ratio, ratio_day: f.cook_measured_at };
    x.grams = r1(p.grams * stateFactor(x)); x.carbs_per_100g = cpFor(x);
    S.plate.push(x);
  }
  S.justAdded = (same || S.plate[S.plate.length - 1]).key;
  savePlate(); toast(`Added ${f.name}, ${p.label}`);
}
const r1 = g => Math.round(g * 10) / 10;
const startState = (basis, ratio) => !basis || basis === "as-sold" ? null : ratio && basis === "raw" ? "cooked" : basis;
/* Dry / raw or cooked: the same food weighed another way, so the grams convert and the carbs stay (okf/domain/plate.md) */
function setState(x, s) { const inBasis = x.grams / stateFactor(x); x.state = s; x.grams = r1(inBasis * stateFactor(x)); x.carbs_per_100g = cpFor(x); }
/* Rows follow their food: a new cooking ratio, state or carbs reach rows already on the plate, keeping the amount of food */
function syncPlate() {
  let changed = false;
  for (const x of S.plate) {
    const f = foodById(x.food_id); if (!f) continue;
    const basis = f.basis || "as-sold", ratio = f.cook_ratio || null;
    if (basis === x.basis && ratio === (x.ratio || null) && f.carbs_per_100g === x.cp_basis && f.cook_measured_at === x.ratio_day) continue;
    const inBasis = x.grams / stateFactor(x), hadRatio = !!x.ratio;
    Object.assign(x, { basis, cp_basis: f.carbs_per_100g, ratio, ratio_day: f.cook_measured_at });
    x.state = !ratio || !hadRatio || !x.state ? startState(basis, ratio) : x.state;
    x.grams = r1(inBasis * stateFactor(x)); x.carbs_per_100g = cpFor(x); changed = true;
  }
  if (changed) store.set("plate", S.plate);
}
/* '90 g dry / raw = about 216 g cooked': both weights of what's on the row */
function bothWeights(x) {
  const other = x.state === "cooked" ? x.grams / x.ratio : x.grams * x.ratio;
  return `${fmtG(x.grams)} ${STATE[x.state]} = about ${Math.round(other)} g ${STATE[x.state === "cooked" ? "raw" : "cooked"]}`;
}
/* carbs per 100 g of the weight actually entered: cooked = dry ÷ ratio, dry = cooked × ratio (okf/rules/cooking-ratio-measured.md) */
const cpFor = x => x.state === x.basis || !x.ratio ? x.cp_basis : x.state === "cooked" ? x.cp_basis / x.ratio : x.cp_basis * x.ratio;
/* How many of the portion this weight is, to the nearest quarter (okf/domain/plate.md) */
function portionCount(x) {   // { approx, num, unit }, kept apart so each sits in its own fixed slot
  let g = itemG(x);
  if (x.state && x.ratio && x.state !== x.basis) g = x.state === "cooked" ? g / x.ratio : g * x.ratio;   // into the portion's own state
  const a = portionAmount(x.portion_label), count = g / (x.base || x.grams) * (a ? a.n : 1), q = Math.round(count * 4) / 4;
  if (!q) return { approx: "<", num: "¼", unit: a ? unitFor(0.25, a.unit) : `× ${x.portion_label}` };
  return { approx: Math.abs(count - q) < 0.01 ? "" : "≈", num: fmtAmount(q), unit: a ? unitFor(q, a.unit) : `× ${x.portion_label}` };
}
const pcountLabel = x => Object.values(portionCount(x)).join(" ").replace("≈", "about").replace("<", "under").trim();
// the ≈ and the number have fixed widths, so the unit doesn't shift as the count changes (okf/domain/plate.md)
const pcountHTML = x => { const c = portionCount(x);
  return `<i class="pa" aria-hidden="${!c.approx}">${c.approx}</i><b class="pn">${c.num}</b> <span class="pu">${esc(c.unit)}</span>`; };
/* Slider ticks at ½, 1, 1½ and 2 of the portion, and snapping to them while dragging (okf/domain/plate.md) */
const stateFactor = x => !x.state || x.state === x.basis || !x.ratio ? 1 : x.state === "cooked" ? x.ratio : 1 / x.ratio;   // portion grams -> grams as weighed
const TICKS = [0.5, 1, 1.5, 2];
const ticks = x => TICKS.map(m => ({ m, g: Math.round((x.base || x.grams) * stateFactor(x) * m * 10) / 10 }));
function snap(row, g) {   // within 2 % of the slider's range of a tick: that tick
  const item = S.plate.find(x => x.key === row.dataset.key), r = row.querySelector(".wRange"); if (!item) return g;
  const near = ticks(item).find(t => Math.abs(t.g - g) <= (+r.max - +r.min) * 0.02);
  if (near && row.dataset.snap !== String(near.g)) navigator.vibrate?.(8);   // a small tap as it lands
  row.dataset.snap = near ? near.g : "";
  return near ? near.g : g;
}
const stateLabel = x => x.state ? `, ${STATE[x.state]} weight` : "";
const plateExact = () => S.plate.reduce((s, x) => s + (x.entered ?? exact(x.grams, x.carbs_per_100g, x.qty)), 0);   // entered: typed carbs, no weight
const plateGrams = () => S.plate.reduce((s, x) => s + itemG(x), 0);

function renderPlatebar(v = location.hash.slice(1) || "foods") {
  const n = S.plate.length;
  $("#plateCount").textContent = n ? `(${n})` : "";
  $("#platebar").hidden = !n || v !== "foods";
  $("#pbItems").textContent = `${n} item${n === 1 ? "" : "s"} · ${fmtG(plateGrams())} of food`;
  $("#pbTotal").textContent = `${whole(plateExact())} g`;
}

/* Carbs entered by hand, with what it was: no food and no weight behind it (okf/domain/plate.md) */
const handAdd = () => `<div class="handadd"><button class="linkbtn" data-act="hand-open">+ Add carbs by hand</button>
  <form id="handForm" class="handform" hidden><label class="field"><span>What was it?</span><input id="hName" maxlength="80" required placeholder="e.g. party cake at school" autocomplete="off"></label>
    <label class="field"><span>Carbs</span><span class="unitin"><input id="hCarbs" type="number" inputmode="decimal" min="0.5" max="300" step="any" required> g</span></label>
    <div class="actions"><button class="btn small primary">Add to plate</button><button type="button" class="btn small quiet" data-act="hand-cancel">Cancel</button></div></form></div>`;
const handRow = x => `<div class="pitem hand" data-key="${x.key}">
    <span class="noimg pphoto handimg" aria-hidden="true">By hand</span>
    <div class="t"><input class="hName" maxlength="80" value="${esc(x.food_name)}" aria-label="What it was"><span>Carbs entered by hand, no weight</span></div>
    <div class="c"><span class="cn">${whole(x.entered)}</span><span class="cu">g carbs</span></div>
    <button class="rm" data-act="remove" aria-label="Remove ${esc(x.food_name)}">×</button>
    <div class="wt"><label class="wnum"><span class="wl">Carbs</span><input type="number" class="hCarbs" min="0.5" max="300" step="any" inputmode="decimal" value="${x.entered}" aria-label="Carbs for ${esc(x.food_name)}"><span>g</span></label></div></div>`;

/* A food this account hasn't checked: its carbs as the source gives them, and Confirm (okf/features/confirm-food.md) */
function unconfirmedHTML(x) {
  const f = S.foods.find(f => f.id === x.food_id);
  if (!S.confirm.enabled || !f || S.confirm.foods.includes(f.id)) return "";
  const src = SOURCE[f.source_kind] || f.source_kind, ref = f.source_ref.toLowerCase().startsWith(src.toLowerCase()) ? f.source_ref : `${src}: ${f.source_ref}`;
  const carbs = f.serving_grams != null ? `${+f.serving_carbs} g carbs per ${+f.serving_grams} g` : `${f.carbs_per_100g} g carbs per 100 g`;
  return `<div class="unconf"><p><b>Not checked by you.</b> ${carbs}${f.basis && f.basis !== "as-sold" ? ` ${STATE[f.basis]}` : ""}${f.cook_ratio ? `, cooked ×${+f.cook_ratio.toFixed(2)}` : ""}
      · ${esc(ref)}</p>
    <button class="btn small" data-act="confirm" aria-label="Confirm the carbs for ${esc(f.name)}">Confirm</button></div>`;
}
function renderPlate() {
  const el = $("#plateView");
  if (!S.plate.length) { el.innerHTML = scaleBar() + `<div class="empty"><h2>The plate is empty</h2><p>Tap a food to add it, then set its weight here.</p>${splitMode() ? "" : `<p><a class="btn" href="#foods">Go to foods</a></p>`}${handAdd()}</div>`; paintScale(); setTimeout(tryScale); return; }
  S.plateTime = S.plateTime || hhmm();
  syncPlate();
  el.innerHTML = scaleBar() + S.plate.map(x => {
    if (x.entered != null) return handRow(x);
    // drag to the weight actually served (okf/domain/plate.md); the mark is the portion's own weight
    const base = (x.base || x.grams) * stateFactor(x), hi = Math.max(Math.ceil(base * 3), Math.ceil(x.grams * 1.5), 30), step = hi > 80 ? 1 : 0.5;
    return `<div class="pitem ${x.key === S.justAdded ? "justadded" : ""} ${x.locked ? "locked" : ""}" data-key="${x.key}">
      ${x.photo ? `<img class="pphoto" ${sized(x.photo, "(max-width: 680px) 112px, 160px")} alt="">` : `<span class="noimg pphoto"></span>`}
      <div class="t"><b>${esc(x.food_name)}</b><span class="pcount" aria-label="${esc(pcountLabel(x))}">${pcountHTML(x)}</span>
        ${!x.state ? "" : x.ratio ? `<div class="wstate"><span>Weighed</span><div class="seg neutral" role="group" aria-label="Weight entered for ${esc(x.food_name)}">${["raw", "cooked"].map(k =>
            `<button data-act="wstate" data-s="${k}" class="${x.state === k ? "on" : ""}" aria-pressed="${x.state === k}">${k === "raw" ? "Dry / raw" : "Cooked"}</button>`).join("")}</div>
            </div><p class="both"><span class="bw">${bothWeights(x)}</span> · <span title="Measured cooking ratio${x.ratio_day ? `, weighed ${dayLabel(x.ratio_day)}` : ""}">×${+x.ratio.toFixed(2)}</span></p>`
          : `<div class="wstate"><span class="wonly">Weigh it ${x.state === "raw" ? "dry / raw, before cooking" : "after cooking"}</span></div>
             <p class="both">Add a cooking ratio to this food in Manage to weigh it ${x.state === "raw" ? "cooked" : "dry / raw"} instead.</p>`}
        ${unconfirmedHTML(x)}</div>
      <div class="c"><span class="cn">${whole(exact(x.grams, x.carbs_per_100g, x.qty))}</span><span class="cu">g carbs</span></div>
      <button class="rm" data-act="remove" aria-label="Remove ${esc(x.food_name)}">×</button>
      <div class="wt"><div class="wtrack">${ticks(x).filter(t => t.g <= hi).map(t =>
            `<i class="mark" style="--m:${((t.g - step) / (hi - step)).toFixed(4)}" title="${fmtAmount(t.m)} × ${esc(x.portion_label)}, ${t.g} g"><span>${fmtAmount(t.m)}</span></i>`).join("")}
          <input type="range" class="wRange" min="${step}" max="${hi}" step="${step}" value="${x.grams}" style="--fill:${fillPct(x.grams, step, hi)}" aria-label="Weight of ${esc(x.food_name)} in grams"${x.locked ? " disabled" : ""}></div>
        <button class="lock" data-act="lock" aria-pressed="${!!x.locked}" aria-label="Lock the slider for ${esc(x.food_name)}" title="${x.locked ? "Slider locked. Tap to unlock" : "Lock the slider"}">${lockIcon(x.locked)}</button>
        <label class="wnum"><span class="wl">Weight</span><input type="number" class="wNum" min="0.5" max="2000" step="0.5" inputmode="decimal" value="${x.grams}" aria-label="Weight of ${esc(x.food_name)} in grams"><span>g</span></label>
        <div class="stepper" role="group" aria-label="Adjust weight"><button data-act="step" data-by="-1" aria-label="1 gram less">−</button><button data-act="step" data-by="1" aria-label="1 gram more">+</button></div>
        <button class="btn small usescale" data-act="use-scale" hidden>Use</button></div></div>`;
  }).join("") + `
    ${handAdd()}
    <div class="total"><div><div class="label">Plate total</div><span class="n">${whole(plateExact())}</span> <span class="u">g carbs</span>
      <div class="meta" id="plateGrams">${fmtG(plateGrams())} of food</div></div>
      <div class="right"><label class="timefield">Time <input type="time" id="plateTime" value="${S.plateTime}"></label>
      <button class="btn primary" data-act="save">Save to log</button></div></div>
    <p class="note">Save to log shows the meal summary first. Enter the total in the pump or meter as usual.
      <span class="plinks"><button class="linkbtn" data-act="clear">Clear plate</button> · <button class="linkbtn" data-act="pin">Pin as favorite</button></span></p>
    <form class="cmtform" id="pinPlate" hidden style="margin-top:8px"><input id="pinName" maxlength="60" value="${suggestName(S.plateTime)}" aria-label="Favorite name"><button class="btn small">Pin</button></form>`;
  paintScale(); setTimeout(tryScale);
}

/* Kitchen scale strip (okf/design/components/scale-bar.md). Drawn empty here, then filled in place on every reading,
   so a reading never redraws the rows or interrupts a drag. */
const scaleBar = () => Scale.supported ? `<div class="scalebar" id="scaleBar" aria-live="off"></div>` : "";
const scaleUsable = st => st.status === "on" && st.steady && st.grams > 0 && st.grams <= 2000;   // okf/rules/scale-reading-needs-tap.md
function paintScale(st = Scale.state()) {
  const bar = $("#scaleBar"); if (!bar) return;
  const on = st.status === "on", g = st.grams == null ? null : +st.grams.toFixed(1);
  if (bar.dataset.status !== st.status) {   // the buttons change only with the connection, not with each reading
    bar.dataset.status = st.status;
    bar.innerHTML = on ? `<span class="sname">${esc(st.name)}</span><span class="sread"><i class="sdot"></i><b class="sg"></b><span class="su">g</span></span>
        <span class="sbtns"><button class="btn small" data-act="scale-zero">Zero</button><button class="btn small quiet" data-act="scale-off">Disconnect</button></span>`
      : st.status === "connecting" ? `<span class="sname">Connecting to the scale…</span>`
      : `${st.status === "lost" ? `<span class="sname warn">Scale disconnected.</span>` : ""}<button class="btn small quiet" data-act="scale-connect">${st.status === "lost" ? "Reconnect" : "Connect scale"}</button>`;
  }
  if (on) {
    bar.querySelector(".sg").textContent = g == null ? "–" : g;
    bar.classList.toggle("steady", st.steady);
    bar.querySelector(".sdot").title = st.steady ? "Steady" : "Changing";
  }
  const ok = scaleUsable(st);
  document.querySelectorAll("#plateView .usescale").forEach(b => {
    b.hidden = !on; b.disabled = !ok; b.textContent = ok ? `Use ${fmtG(g)}` : "Use scale";
    b.title = ok ? "" : g > 2000 ? "Over 2000 g" : "Waiting for a steady reading above zero";
  });
}
Scale.on(st => paintScale(st));
/* Auto-connect while the plate is on screen (okf/features/kitchen-scale.md): now, and every 15 s for a scale switched on later */
const plateShowing = () => !!$("#scaleBar") && !!$("#plateView").offsetParent && document.visibilityState === "visible";
const tryScale = () => { if (Scale.supported && plateShowing()) Scale.autoConnect(); };
setInterval(tryScale, 15000);
document.addEventListener("visibilitychange", tryScale);
async function scaleAction(act, row) {
  try {
    if (act === "scale-connect") await Scale.connect();
    else if (act === "scale-off") Scale.disconnect();
    else if (act === "scale-zero") await Scale.zero();
    else if (act === "use-scale") {   // only on this tap, and only a steady reading (okf/rules/scale-reading-needs-tap.md)
      const st = Scale.state(), item = S.plate.find(x => x.key === row?.dataset.key);
      if (!item || !scaleUsable(st)) return;
      const g = Math.round(st.grams * 10) / 10;
      setItemGrams(row, g, "scale"); savePlate(); renderPlate();
      toast(`${item.food_name}: ${fmtG(g)} from the scale`);
    }
  } catch (e) { if (e.name !== "NotFoundError") toast(e.message); }   // NotFoundError: the chooser was closed
}
$("#plateView").addEventListener("click", async e => {
  const t = e.target.closest("[data-act]"); if (!t) return;
  const item = S.plate.find(x => x.key === t.closest("[data-key]")?.dataset.key);
  if (t.dataset.act === "step") {   // the stepper beside the weight field (Apple HIG: slider + text field + stepper)
    const row = t.closest("[data-key]"); setItemGrams(row, Math.max(0.5, Math.round(item.grams + +t.dataset.by)), "step"); savePlate();
  }
  else if (t.dataset.act === "confirm") {
    t.disabled = true;
    try {
      await api(`/api/foods/${encodeURIComponent(item.food_id)}/confirm`, { method: "POST" });
      S.confirm.foods.push(item.food_id); store.set("confirm", S.confirm); renderPlate(); toast(`${item.food_name} confirmed`);
    } catch (err) { t.disabled = false; toast(err.message); }
  }
  else if (t.dataset.act === "lock") { item.locked = !item.locked; savePlate(); renderPlate(); $(`#plateView [data-key="${item.key}"] .lock`)?.focus(); }
  else if (t.dataset.act === "remove") { S.plate = S.plate.filter(x => x !== item); savePlate(); renderPlate(); }
  else if (t.dataset.act === "clear") { S.plate = []; S.plateTime = null; savePlate(); renderPlate(); }
  else if (t.dataset.act === "save") openSummary();
  else if (t.dataset.act === "wstate") { if (item.state !== t.dataset.s) setState(item, t.dataset.s); savePlate(); renderPlate(); }
  else if (t.dataset.act.startsWith("scale-") || t.dataset.act === "use-scale") scaleAction(t.dataset.act, t.closest("[data-key]"));
  else if (t.dataset.act === "pin") { $("#pinPlate").hidden = false; $("#pinName").select(); }
  else if (t.dataset.act === "hand-open") { t.hidden = true; $("#handForm").hidden = false; $("#hName").focus(); }
  else if (t.dataset.act === "hand-cancel") { renderPlate(); }
});
$("#plateView").addEventListener("submit", async e => {
  if (e.target.id === "handForm") {
    e.preventDefault();
    const name = $("#hName").value.trim(), carbs = +$("#hCarbs").value;
    if (!name) { toast("Say what it was, so the log shows it."); return; }
    if (!(carbs >= 0.5 && carbs <= 300)) { toast("Carbs entered by hand are between 0.5 and 300 g."); return; }
    S.plate.push({ key: uid(), food_id: null, portion_id: null, food_name: name, entered: carbs, grams: 0, qty: 1 });
    S.plateTime = S.plateTime || hhmm(); savePlate(); renderPlate(); toast(`Added ${name}, ${fmtG(carbs)} carbs`); return;
  }
  if (e.target.id !== "pinPlate") return; e.preventDefault();
  const name = $("#pinName").value.trim(); if (!name) return;
  const weighed = S.plate.filter(x => x.entered == null);   // carbs entered by hand have no food to keep (okf/domain/plate.md)
  if (!weighed.length) { toast("Only carbs entered by hand are on the plate, so there's nothing to pin."); return; }
  if (await pinFavorite("/api/favorites", { name, items: weighed.map(x => ({ portion_id: x.portion_id, qty: Math.round(itemG(x) / (x.base || x.grams) * 100) / 100 })) })) {
    $("#pinPlate").hidden = true;
    if (weighed.length < S.plate.length) toast("Pinned. Carbs entered by hand aren't kept in favorites.");
  }
});
$("#plateView").addEventListener("change", e => {
  if (e.target.id === "plateTime") S.plateTime = e.target.value;
  if (e.target.matches(".hName,.hCarbs")) {   // a hand-entered row changed: kept only when it still makes sense
    const x = S.plate.find(i => i.key === e.target.closest("[data-key]").dataset.key), v = e.target.value.trim();
    if (e.target.matches(".hName")) { if (v) x.food_name = v; else toast("Say what it was, so the log shows it."); }
    else if (+v >= 0.5 && +v <= 300) x.entered = +v; else toast("Carbs entered by hand are between 0.5 and 300 g.");
    savePlate(); renderPlate();
  }
  if (e.target.matches(".wRange,.wNum")) { savePlate(); renderPlate(); }   // drawn again so the slider's range fits the new weight
});
// a padlock, open or shut (okf/domain/plate.md: weight lock)
const lockIcon = shut => `<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="5" y="11" width="14" height="10" rx="2" fill="${shut ? "currentColor" : "none"}"/><path d="${shut ? "M8 11V7a4 4 0 0 1 8 0v4" : "M8 11V7a4 4 0 0 1 7.5-1.9"}"/></svg>`;
const fillPct = (g, min, max) => `${Math.max(0, Math.min(100, (g - min) / (max - min) * 100)).toFixed(2)}%`;
function setItemGrams(row, g, from) {   // live while dragging: only the numbers change, so the drag isn't interrupted
  const item = S.plate.find(x => x.key === row.dataset.key);
  if (!item || !(g > 0) || g > 2000) return;
  item.grams = g;
  const r = row.querySelector(".wRange");
  if (from !== "range") r.value = g;
  r.style.setProperty("--fill", fillPct(g, +r.min, +r.max));
  if (from !== "num") row.querySelector(".wNum").value = g;
  row.querySelector(".c .cn").textContent = whole(exact(item.grams, item.carbs_per_100g, item.qty));
  const pc = row.querySelector(".pcount"); pc.innerHTML = pcountHTML(item); pc.setAttribute("aria-label", pcountLabel(item));
  const bw = row.querySelector(".bw"); if (bw) bw.textContent = bothWeights(item);
  $("#plateView .total .n").textContent = whole(plateExact()); $("#plateGrams").textContent = `${fmtG(plateGrams())} of food`;
  store.set("plate", S.plate); renderPlatebar();
}
$("#plateView").addEventListener("input", e => {
  if (e.target.matches(".wNum")) setItemGrams(e.target.closest("[data-key]"), parseFloat(e.target.value), "num");   // typed: never snapped
  if (e.target.matches(".wRange")) {
    const row = e.target.closest("[data-key]"), g = snap(row, parseFloat(e.target.value));
    setItemGrams(row, g, g === parseFloat(e.target.value) ? "range" : "snap");
  }
});
/* Drag anywhere on a row, left or right, to set its weight (okf/domain/plate.md). Same scale as the row's slider;
   a mostly vertical move is left to the page so it still scrolls. */
let rowDrag = null;
$("#plateView").addEventListener("pointerdown", e => {
  const row = e.target.closest(".pitem[data-key]");
  if (!row || row.classList.contains("locked") || row.classList.contains("hand") || e.target.closest("button,input,a") || e.button > 0) return;
  const r = row.querySelector(".wRange"), w = r.getBoundingClientRect().width;
  rowDrag = { row, id: e.pointerId, x: e.clientX, y: e.clientY, g: +r.value, perPx: (+r.max - +r.min) / w, min: +r.min, max: +r.max, step: +r.step, on: false };
});
$("#plateView").addEventListener("pointermove", e => {
  const d = rowDrag; if (!d || e.pointerId !== d.id) return;
  const dx = e.clientX - d.x, dy = e.clientY - d.y;
  if (!d.on) {
    if (Math.abs(dx) < 6 && Math.abs(dy) < 6) return;
    if (Math.abs(dy) > Math.abs(dx)) { rowDrag = null; return; }   // scrolling the page
    d.on = true; d.row.setPointerCapture(e.pointerId); d.row.classList.add("dragging");
  }
  e.preventDefault();
  const g = Math.min(d.max, Math.max(d.min, Math.round((d.g + dx * d.perPx) / d.step) * d.step));
  setItemGrams(d.row, snap(d.row, +g.toFixed(1)));
});
const endRowDrag = e => {
  const d = rowDrag; if (!d || e.pointerId !== d.id) return;
  rowDrag = null;
  if (d.on) { d.row.classList.remove("dragging"); savePlate(); renderPlate(); }
};
$("#plateView").addEventListener("pointerup", endRowDrag);
$("#plateView").addEventListener("pointercancel", endRowDrag);

/* Meal summary before saving, with the dose from the parent's own settings (okf/features/meal-dose-summary.md).
   The server does the maths (okf/rules/no-dosing.md); this only shows each step. Nothing about the dose is saved. */
const doseDlg = $("#doseDialog");
const ARROWS = { DoubleUp: "⇈", SingleUp: "↑", FortyFiveUp: "↗", Flat: "→", FortyFiveDown: "↘", SingleDown: "↓", DoubleDown: "⇊" };
const u2 = x => (+x).toFixed(2);
const agoMin = m => m < 1 ? "just now" : m < 120 ? `${m} min ago` : m < 2880 ? `${Math.round(m / 60)} hours ago` : `${Math.round(m / 1440)} days ago`;
function openSummary() {
  S.sum = { carbs: whole(plateExact()), day: localDay(), at: S.plateTime || hhmm(), bg: "", typed: false, data: null, err: null };
  doseDlg.innerHTML = `<div class="dlghead"><b id="sumHead">${sumHead()}</b><button class="rm" data-sum="close" aria-label="Back to plate">×</button></div>
    <div class="dlgbody">
      <ul class="summeal">${S.plate.map(x => `<li><span class="t">${esc(x.food_name)}<small>${x.entered != null ? "Entered by hand" : fmtG(x.grams) + stateLabel(x)}</small></span>
        <span class="c">${whole(x.entered ?? exact(x.grams, x.carbs_per_100g, x.qty))} g</span></li>`).join("")}
        <li class="sumtotal"><span class="t">Total carbs</span><span class="c">${S.sum.carbs} g</span></li></ul>
      <div class="sumwhen"><span class="label">When</span>
        <input type="date" id="sumDay" value="${S.sum.day}" max="${localDay()}" required aria-label="Date">
        <input type="time" id="sumAt" value="${S.sum.at}" required aria-label="Time"></div>
      <label class="field sumbg"><span>Blood glucose (mg/dL)</span>
        <input id="sumBg" type="number" inputmode="numeric" min="20" max="600" step="1" placeholder="Meter reading"></label>
      <div id="sumCalc" aria-live="polite"><p class="meta">Working it out…</p></div>
      <div class="sumgiven"><span class="label">What was given · optional</span>${detailFields()}</div>
      <div class="actions sumacts"><button class="btn primary" data-sum="save">Save to log</button><button class="btn quiet" data-sum="close">Back to plate</button></div>
    </div>`;
  doseDlg.showModal(); loadDose();
}
let doseTimer = null;
const sumHead = () => `Meal summary · ${S.sum.day === localDay() ? "" : dayLabel(S.sum.day) + ", "}${S.sum.at}`;
/* A meal set away from now can't take the CGM's current reading as its BG (okf/features/meal-dose-summary.md) */
const sumAway = () => Math.abs(Date.now() - new Date(`${S.sum.day}T${S.sum.at}`).getTime()) > 15 * 60e3;
async function loadDose() {
  const s = S.sum; if (!s) return;
  const bg = s.typed && s.bg !== "" ? `&bg=${encodeURIComponent(s.bg)}` : s.typed || sumAway() ? "&use_cgm=false" : "";
  try { s.data = await api(`/api/dose?carbs=${s.carbs}&at=${s.at}${bg}`); s.err = null; }
  catch (err) { s.data = null; s.err = err.status === 422 ? "Blood glucose must be between 20 and 600 mg/dL." : err.message || "Couldn't reach the server."; }
  if (S.sum !== s) return;
  if (!s.typed) $("#sumBg").value = s.data?.bg_source === "cgm" ? s.data.cgm.sgv : "";   // filled in only from a fresh reading
  drawDose();
}
function bgNote(d) {
  const c = d.cgm, cgm = c ? `${c.sgv} mg/dL ${ARROWS[c.direction] || ""}` : "";
  if (d.bg_source === "cgm") return `From the CGM: ${cgm}, ${agoMin(c.age_min)}. Type over it to use a meter reading.`;
  if (!S.sum.typed && sumAway()) return `The meal is set for ${S.sum.day === localDay() ? "" : dayLabel(S.sum.day) + ", "}${S.sum.at}, so the CGM reading from now isn't used. Type the meter reading from then. Insulin on board is from now.`;
  if (d.bg_source === "typed") return c ? `Typed in. The CGM showed ${cgm}, ${agoMin(c.age_min)}.` : "Typed in.";
  if (c && !d.cgm_fresh) return `The last CGM reading was ${agoMin(c.age_min)} (${cgm}), too old to use. Type a meter reading.`;
  if (S.sum.typed && c) return "No BG, so no correction is added.";
  return d.nightscout ? "No CGM reading. Type a meter reading." : "Nightscout isn't connected. Type a meter reading.";
}
function drawDose() {
  const s = S.sum, d = s.data, el = $("#sumCalc"); if (!el) return;
  if (!d) { el.innerHTML = `<p class="err">${esc(s.err)}</p><p class="meta">No dose was worked out. The meal can still be saved.</p>`; return; }
  const note = `<p class="meta bgnote">${esc(bgNote(d))}</p>`;
  if (!d.ready) { el.innerHTML = note + `<p class="sumnone">Insulin settings aren't set up, so no dose is worked out.
    <a href="#manage/settings" data-sum="settings">Add the carb ratio, correction factor and target in Manage → Settings</a>.</p>`; return; }
  const k = d.calc, i = d.iob;
  const iobLine = !d.nightscout ? "Nightscout isn't connected, so nothing is taken off."
    : !i ? `Not available from Nightscout${d.ns_error ? ` (${esc(d.ns_error)})` : ""}, so nothing is taken off.`
    : !d.iob_fresh ? `Nightscout's is ${i.age_min} min old (${u2(i.units)} u), so nothing is taken off.`
    : k.correction_u == null ? `${u2(i.units)} u (${esc(i.source)}, ${agoMin(i.age_min)}). No correction to take it off.`
    : !k.iob_used ? `${u2(i.units)} u (${esc(i.source)}, ${agoMin(i.age_min)}). Not used: BG is at or below target.`
    : `${u2(i.units)} u (${esc(i.source)}, ${agoMin(i.age_min)}): <b>−${u2(k.iob_off)} u</b> off the correction${k.iob_off < i.units ? ", which can't go below zero" : ""}.`;
  el.innerHTML = note + (k.bg != null && k.bg < 70 ? `<p class="sumlow">BG is low: ${k.bg} mg/dL.</p>` : "") + `
    <div class="sumdose"><span class="label">Insulin for this meal</span><span class="n">${u2(k.dose)}</span> <span class="u">u</span></div>
    <span class="label">How it's worked out</span>
    <dl class="sumcalc">
      <dt>Carbs</dt><dd>${k.carbs} g ÷ ${k.carb_ratio} g per u = <b>${u2(k.carb_u)} u</b></dd>
      <dt>Correction</dt><dd>${k.correction_u == null ? "No BG, so none added."
        : `(${k.bg} − ${k.target}) ÷ ${k.isf} = <b>${k.correction_u < 0 ? "−" : ""}${u2(Math.abs(k.correction_u))} u</b>${k.correction_u < 0 ? " (BG under target lowers the dose)" : ""}`}</dd>
      <dt>Insulin on board</dt><dd>${iobLine}</dd>
      <dt>Total</dt><dd>${(+k.total_exact).toFixed(3).replace(/0$/, "")} u, rounded down to 0.05 u</dd>
    </dl>
    <p class="meta">Worked out from your settings${d.updated ? ` (changed ${esc(dayLabel(d.updated))})` : ""}. Check it against the pump before giving.</p>`;
}
doseDlg.addEventListener("change", e => {   // date or time of the meal: heading, plate time and the dose follow
  if (!["sumDay", "sumAt"].includes(e.target.id) || !S.sum) return;
  const day = $("#sumDay").value, at = $("#sumAt").value;
  if (!day || !at || day > localDay()) return;
  Object.assign(S.sum, { day, at }); S.plateTime = at; savePlate();
  $("#sumHead").textContent = sumHead(); loadDose();
});
doseDlg.addEventListener("input", e => {
  if (e.target.id !== "sumBg" || !S.sum) return;
  S.sum.typed = true; S.sum.bg = e.target.value.trim();
  clearTimeout(doseTimer); doseTimer = setTimeout(loadDose, 400);
});
doseDlg.addEventListener("click", async e => {
  if (e.target === doseDlg) return doseDlg.close();   // a tap on the backdrop
  const t = e.target.closest("[data-sum]"); if (!t) return;
  if (t.dataset.sum === "close") doseDlg.close();
  else if (t.dataset.sum === "settings") doseDlg.close();
  else if (t.dataset.sum === "save") {
    let extra;
    try {
      const day = $("#sumDay").value, time = $("#sumAt").value;
      if (!day || !time) throw new Error("Choose the meal's date and time.");
      if (day > localDay()) throw new Error("A meal can't be logged for a future day.");
      extra = { day, time, ...readDetails(doseDlg) };
      const bg = $("#sumBg").value.trim();
      if (bg !== "") {
        if (!(+bg >= 20 && +bg <= 600 && Number.isInteger(+bg))) throw new Error("Blood glucose must be a whole number between 20 and 600 mg/dL.");
        Object.assign(extra, { bg: +bg, bg_source: !S.sum.typed && S.sum.data?.bg_source === "cgm" ? "cgm" : "meter" });
      }
    } catch (err) { toast(err.message); return; }
    await saveMeal(t, extra); if (!S.plate.length) doseDlg.close();
  }
});
doseDlg.addEventListener("close", () => { S.sum = null; clearTimeout(doseTimer); doseDlg.innerHTML = ""; });

/* Optional BG, insulin and timings that go with a meal (okf/domain/meal.md). Insulin is only what was typed, never the
   worked-out dose (okf/rules/no-dosing.md). Used in the meal summary and when editing a meal in the log. */
function detailFields(d = {}) {
  const off = d.insulin != null ? d.insulin_offset_min : 15, when = !off ? "start" : off > 0 ? "before" : "after";   // new: the usual 15 min pre-bolus
  return `<div class="mdet">
    <div class="mrow"><label class="field"><span>Insulin given</span><span class="unitin"><input class="dIns" type="number" inputmode="decimal" min="0.05" max="100" step="0.05" value="${d.insulin ?? ""}" placeholder="Units"> u</span></label>
      <div class="seg neutral" role="group" aria-label="Insulin type">${["bolus", "basal"].map(k =>
        `<button type="button" data-dkind="${k}" class="${(d.insulin_kind || "bolus") === k ? "on" : ""}" aria-pressed="${(d.insulin_kind || "bolus") === k}">${cap(k)}</button>`).join("")}</div></div>
    <div class="mrow"><span class="mlab">Given</span><div class="seg neutral" role="group" aria-label="When the insulin was given">${[["before", "Before eating"], ["start", "At the start"], ["after", "After starting"]].map(([k, l]) =>
        `<button type="button" data-dwhen="${k}" class="${when === k ? "on" : ""}" aria-pressed="${when === k}">${l}</button>`).join("")}</div>
      <span class="unitin dMinWrap" ${when === "start" ? "hidden" : ""}><input class="dMin" type="number" inputmode="numeric" min="1" max="120" step="1" value="${off ? Math.abs(off) : ""}" aria-label="Minutes"> min</span></div>
    <div class="mrow"><label class="field"><span>Time to eat the meal</span><span class="unitin"><input class="dEat" type="number" inputmode="numeric" min="1" max="240" step="1" value="${d.eat_min ?? ""}" placeholder="Minutes"> min</span></label></div>
  </div>`;
}
function readDetails(root) {
  const v = sel => root.querySelector(sel).value.trim(), on = sel => root.querySelector(`${sel}.on`)?.dataset;
  const out = { insulin: null, insulin_kind: null, insulin_offset_min: null, eat_min: null };
  if (v(".dIns") !== "") {
    const u = +v(".dIns");
    if (!(u > 0 && u <= 100) || Math.abs(u * 20 - Math.round(u * 20)) > 1e-6) throw new Error("Insulin is between 0.05 and 100 units, in steps of 0.05.");
    const when = on("[data-dwhen]").dwhen, min = v(".dMin");
    if (when !== "start" && !(Number.isInteger(+min) && +min >= 1 && +min <= 120)) throw new Error(`Enter how many minutes ${when === "before" ? "before" : "after"} eating it was given (1 to 120).`);
    Object.assign(out, { insulin: u, insulin_kind: on("[data-dkind]").dkind, insulin_offset_min: when === "start" ? 0 : when === "before" ? +min : -min });
  }
  if (v(".dEat") !== "") {
    if (!(Number.isInteger(+v(".dEat")) && +v(".dEat") >= 1 && +v(".dEat") <= 240)) throw new Error("Time to eat is between 1 and 240 minutes.");
    out.eat_min = +v(".dEat");
  }
  return out;
}
document.addEventListener("click", e => {   // the Bolus / Basal and before / after switches
  const b = e.target.closest(".mdet [data-dkind], .mdet [data-dwhen]"); if (!b) return;
  b.parentElement.querySelectorAll("button").forEach(x => { x.classList.toggle("on", x === b); x.setAttribute("aria-pressed", x === b); });
  if (b.dataset.dwhen) { const w = b.closest(".mrow").querySelector(".dMinWrap"); w.hidden = b.dataset.dwhen === "start"; if (!w.hidden) w.querySelector("input").focus(); }
});
const detailSummary = m => [
  m.bg != null && `BG ${m.bg}${m.bg_source === "cgm" ? " (CGM)" : " (meter)"}`,
  m.insulin != null && `${fmtU(m.insulin)} ${m.insulin_kind}${!m.insulin_offset_min ? " at the start" : m.insulin_offset_min > 0 ? `, ${m.insulin_offset_min} min before eating` : `, ${-m.insulin_offset_min} min after starting`}`,
  m.eat_min != null && `eaten in ${m.eat_min} min`].filter(Boolean).join(" · ");

async function saveMeal(btn, extra = {}) {
  const meal = { client_id: uid(), day: localDay(), time: S.plateTime || hhmm(), ...extra,
    items: S.plate.map(x => x.entered != null ? { food_name: x.food_name, portion_label: "Carbs entered by hand", entered_carbs: x.entered } : ({ food_id: x.food_id, portion_id: x.portion_id, food_name: x.food_name, grams: x.grams, carbs_per_100g: x.carbs_per_100g, qty: x.qty,
      portion_label: (x.portion_label.slice(0, 40 - stateLabel(x).length) + stateLabel(x)) })) };   // the log keeps which weight it was (okf/rules/cooking-ratio-measured.md)
  btn.disabled = true;
  try { await api("/api/meals", { method: "POST", body: meal }); toast(`Saved ${whole(plateExact())} g to the log`); }
  catch (err) {
    if (err.status) { btn.disabled = false; toast(err.message); return; }
    S.queue.push(meal); store.set("queue", S.queue); renderStatus();       // okf/rules/offline-queue.md
    toast("Saved on this tablet. It will sync when the server is back.");
  }
  S.plate = []; S.plateTime = null; savePlate();
  S.log.day = meal.day; S.log.sel = null; location.hash = "log";
}

async function syncQueue() {
  for (const m of [...S.queue]) {
    const { kind, ...body } = m;
    try { await api(kind === "entry" ? "/api/entries" : "/api/meals", { method: "POST", body }); S.queue = S.queue.filter(x => x !== m); }
    catch (err) { if (!err.status) break; m.error = err.message; }
  }
  store.set("queue", S.queue); renderStatus();
}

/* ---------- log (okf/features/review-log.md, annotate-meal.md, glucose-*.md) ---------- */
async function loadLog(day) {
  S.log.day = day;
  try { S.log.data = await api("/api/log?day=" + day); }
  catch (err) { $("#logList").innerHTML = `<div class="empty">${esc(err.message)}</div>`; $("#mealDetail").innerHTML = ""; return; }
  const meals = S.log.data.meals;
  if (S.log.selEntry && !S.log.data.entries.some(e => e.id === S.log.selEntry)) S.log.selEntry = null;
  if (!S.log.selEntry && !S.log.adding && !meals.find(m => m.id === S.log.sel)) S.log.sel = meals.length ? meals[meals.length - 1].id : null;
  if (S.log.period !== "day") await loadPeriod();
  renderLog();
}
async function loadPeriod() {
  try { S.log.stats = await api(`/api/stats?days=${S.log.period}&end=${S.log.day}`); } catch { S.log.stats = null; }
}

function statsStrip(g, label) {
  if (!g || !g.count) return `<div class="strip"><span class="meta">${label}: no sensor data.</span></div>`;
  const cover = Math.round(g.coverage * 100);
  return `<div class="strip">
    <div class="tir" aria-hidden="true"><i class="lo" style="width:${g.below}%"></i><i class="in" style="width:${g.in_range}%"></i><i class="hi" style="width:${g.above}%"></i></div>
    <div class="tirl"><span><b>${Math.round(g.in_range)}%</b> in range</span><span class="${g.below ? "warn" : ""}"><b>${Math.round(g.below)}%</b> below</span><span><b>${Math.round(g.above)}%</b> above</span></div>
    <div class="tirl"><span>Avg <b>${g.mean}</b> mg/dL</span><span class="${g.lows ? "warn" : ""}">${g.lows} low${g.lows === 1 ? "" : "s"}</span>
      ${g.cv != null ? `<span>CV <b>${g.cv}%</b></span>` : ""}${g.gmi != null ? `<span>GMI <b>${g.gmi}%</b></span>` : ""}
      <span class="${g.complete ? "" : "warn"}">Sensor ${cover}%${g.complete ? "" : ", incomplete"}</span></div></div>`;
}

function renderLog() {
  const d = S.log.data, isToday = d.day === localDay();
  const period = S.log.period;
  let strip = "";
  if (S.session?.glucose) {
    const g = period === "day" ? d.glucose : S.log.stats?.glucose;
    const label = period === "day" ? (isToday ? "Today so far" : "This day") : `${period} days`;
    strip = `<div class="periods" role="group" aria-label="Statistics period">${[["day", "Day"], [7, "7 days"], [14, "14 days"]].map(([k, l]) =>
      `<button data-period="${k}" class="${String(k) === String(period) ? "on" : ""}">${l}</button>`).join("")}</div>` + statsStrip(g, label)
      + (period !== "day" && S.log.stats ? `<p class="meta" style="padding:6px 0">${S.log.stats.meals} meals · ${S.log.stats.carbs_per_day} g carbs a day on average</p>` : "");
  }
  $("#logList").innerHTML = `
    <div class="daynav"><button data-day="-1" aria-label="Previous day">‹</button><b>${isToday ? "Today, " : ""}${dayLabel(d.day)}</b>
      <span class="meta">${d.total} g</span><button data-day="1" aria-label="Next day" ${isToday ? "disabled" : ""}>›</button></div>
    ${strip}
    ${Object.keys(d.insulin || {}).length ? `<p class="meta insline">Insulin given: ${Object.entries(d.insulin).map(([k, u]) => `<b>${fmtU(u)}</b> ${KIND[k]}`).join(" · ")}</p>` : ""}
    ${d.editable ? `<button class="btn small addentry ${S.log.adding ? "on" : ""}" data-act="add-entry">Add entry${isToday ? "" : ` to ${dayLabel(d.day)}`}: carbs, BG or insulin</button>` : ""}
    ${logRows(d)}
    ${deletedList(d)}
    <div class="dayfoot">
      ${isToday ? "" : `<p class="meta">${d.editable ? "Changes to an earlier day are marked ✎ Modified." : "Earlier days are read-only. A parent can allow changes in Manage → Settings."} <button class="linkbtn" data-day="today">Go to today</button></p>`}
      <div class="exportrow"><span class="meta">Export</span>
        <input type="date" id="exFrom" value="${shiftDay(d.day, -13)}" aria-label="From"><input type="date" id="exTo" value="${d.day}" aria-label="To">
        <button class="btn small" data-act="export" data-fmt="pdf">PDF</button><button class="btn small quiet" data-act="export" data-fmt="csv">CSV</button></div>
    </div>`;
  renderMeal();
}
const cap = s => s[0].toUpperCase() + s.slice(1);
const KIND = { rapid: "rapid-acting", long: "long-acting", bolus: "bolus", basal: "basal" };
const fmtU = u => `${(+u).toFixed(2).replace(/0$/, "")} u`;           // 2.5 -> "2.50" -> "2.5 u"; 0.05 stays
const entrySummary = e => [e.bg != null && `BG ${e.bg}`, e.insulin != null && `${fmtU(e.insulin)} ${KIND[e.insulin_kind]}`,
  e.carbs != null && `${+e.carbs} g carbs`].filter(Boolean).join(" · ") || "Note";

/* Date and time can change on any day; the log only marks that it changed, the export keeps when (okf/rules/same-day-edits.md) */
const modMark = x => x.moved_from || x.edited_at ? `<i class="modmark" title="Modified" aria-label="Modified">✎</i>` : "";
const movedLabel = s => `${dayLabel(s.slice(0, 10))}, ${s.slice(11)}`;
const whenBox = (x, kind) => `<div class="glab"><span class="label">When</span></div>
    <form class="whenform" id="whenForm" data-what="${kind}" data-id="${x.id}">
      <input type="date" id="whDay" value="${x.day}" max="${localDay()}" required aria-label="Date">
      <input type="time" id="whTime" value="${x.time}" required aria-label="Time"></form>
    ${x.moved_from || x.edited_at ? `<p class="meta moved"><span aria-hidden="true">✎</span> Modified</p>` : ""}`;

/* Deleted meals and entries stay listed on their day and can be restored (okf/domain/meal-log.md) */
const deletedList = d => !d.deleted?.length ? "" : `<details class="deleted"><summary>Deleted (${d.deleted.length})</summary>
  ${d.deleted.map(x => `<div class="delrow"><span class="tm">${x.time}</span>
    <span class="it"><b>${esc(x.kind === "meal" ? x.what || "Meal" : entrySummary(x.what))}</b><span>${x.carbs != null ? `${whole(x.carbs)} g carbs · ` : ""}deleted ${movedLabel(x.deleted_at)}</span></span>
    ${d.editable ? `<button class="btn small" data-restore="${x.kind}:${x.id}">Restore</button>` : ""}</div>`).join("")}
  ${d.editable ? "" : `<p class="meta">Earlier days are read-only, so these can't be restored unless a parent allows changes in Manage → Settings.</p>`}</details>`;

/* Meals and manual entries in one timeline (okf/design/components/entry-row.md). */
function logRows(d) {
  const rows = [...d.meals.map(m => ({ t: m.time, m })), ...d.entries.map(e => ({ t: e.time, e }))].sort((a, b) => a.t.localeCompare(b.t));
  if (!rows.length) return `<div class="empty">Nothing logged${d.day === localDay() ? " yet today" : " this day"}.</div>`;
  return rows.map(({ m, e }) => m
    ? `<button class="lrow ${m.id === S.log.sel && !S.log.selEntry && !S.log.adding ? "on" : ""}" data-meal="${m.id}">
      <span class="tm">${m.time}${modMark(m)}</span><span class="it"><b>${esc(m.items.map(i => `${i.food_name} ${i.carbs} g carbs${i.entered_carbs != null ? " (by hand)" : ""}`).join(" · "))}</b>
      <span>Eaten: ${m.eaten ? cap(m.eaten) : "not set"}${m.bg != null ? ` · BG&nbsp;${m.bg}` : ""}${m.insulin != null ? ` · ${fmtU(m.insulin)} ${m.insulin_kind}` : ""}${m.two_h != null ? ` · 2&nbsp;h&nbsp;${m.two_h}` : ""}${m.carbs_corrected != null ? ` · <i class="moved">Carbs edited</i>` : ""}</span>
      ${m.comments.length ? `<span class="lcmt">${esc(m.comments.map(c => c.text).join(" · "))}</span>` : ""}</span>
      <span class="c">${m.total}</span></button>`
    : `<button class="lrow entry ${e.id === S.log.selEntry ? "on" : ""}" data-entry="${e.id}">
      <span class="tm">${e.time}${modMark(e)}</span><span class="it"><b>${esc(entrySummary(e))}</b>${e.note ? `<span>${esc(e.note)}</span>` : ""}</span>
      <span class="c">${e.carbs != null ? whole(e.carbs) : ""}</span></button>`).join("");
}

function renderEntryForm() {
  $("#mealDetail").innerHTML = `<form class="form" id="entryForm">
    <h2>Add entry${S.log.data.day === localDay() ? "" : ` to ${dayLabel(S.log.data.day)}`}</h2>
    <p class="meta">Record what happened. Leave out anything you don't have.${S.log.data.day === localDay() ? "" : " It will be marked ✎ Modified."}</p>
    <label class="timefield">Time <input type="time" id="enTime" value="${hhmm()}" required></label>
    <div class="fieldrow">
      <label class="field"><span>BG from the meter, mg/dL</span><input id="enBg" type="number" inputmode="numeric" min="20" max="600" step="1"></label>
      <label class="field"><span>Carbs, g (not from the food list)</span><input id="enCarbs" type="number" inputmode="decimal" min="0" max="500" step="0.5"></label></div>
    <div class="fieldrow">
      <label class="field"><span>Insulin given, units</span><input id="enIns" type="number" inputmode="decimal" min="0.05" max="100" step="0.05"></label>
      <fieldset class="field tagpick"><legend>Insulin type</legend><div class="seg neutral" role="radiogroup">
        <button type="button" data-kind="rapid">Rapid-acting</button><button type="button" data-kind="long">Long-acting</button></div></fieldset></div>
    <label class="field"><span>Note</span><input id="enNote" maxlength="500" placeholder="e.g. juice for a low, pump site change"></label>
    <p class="err" id="enErr"></p>
    <div class="actions"><button class="btn primary" id="enSave" disabled>Save</button><button type="button" class="btn quiet" data-act="entry-cancel">Cancel</button></div>
    <p class="note">The app records what you enter. It doesn't calculate or check insulin amounts.</p></form>`;
  S.log.kind = null; entryPreview();
}
function entryPreview() {
  const v = id => $(id).value.trim(), e = { bg: v("#enBg") ? +v("#enBg") : null, carbs: v("#enCarbs") ? +v("#enCarbs") : null,
    insulin: v("#enIns") ? +v("#enIns") : null, insulin_kind: S.log.kind };
  const needKind = e.insulin != null && !e.insulin_kind;
  const any = e.bg != null || e.carbs != null || e.insulin != null || v("#enNote");
  $("#enSave").disabled = !any || needKind;
  // The button repeats exactly what will be saved, so a typo like 25 for 2.5 is visible before saving.
  $("#enSave").textContent = !any ? "Save" : needKind ? "Choose the insulin type" : `Save: ${entrySummary(e)}`;
  document.querySelectorAll("#entryForm [data-kind]").forEach(b => b.classList.toggle("on", b.dataset.kind === S.log.kind));
}
let confirmEntry = 0;
function renderEntry(e) {
  const ed = S.log.data.editable;
  const val = v => v ?? "";
  $("#mealDetail").innerHTML = `<div class="mdh"><b>${e.time}</b>${e.carbs != null ? `<span class="c">${+e.carbs} <small>g carbs</small></span>` : ""}</div>
    ${ed ? `<form class="form entval" id="entValForm">
      <div class="fieldrow">
        <label class="field"><span>BG from the meter, mg/dL</span><input id="evBg" type="number" inputmode="numeric" min="20" max="600" step="1" value="${val(e.bg)}"></label>
        <label class="field"><span>Carbs, g (not from the food list)</span><input id="evCarbs" type="number" inputmode="decimal" min="0" max="500" step="0.5" value="${e.carbs != null ? +e.carbs : ""}"></label></div>
      <div class="fieldrow">
        <label class="field"><span>Insulin given, units</span><input id="evIns" type="number" inputmode="decimal" min="0.05" max="100" step="0.05" value="${val(e.insulin)}"></label>
        <fieldset class="field tagpick"><legend>Insulin type</legend><div class="seg neutral" role="radiogroup">
          ${["rapid", "long"].map(k => `<button type="button" data-ekind="${k}" class="${e.insulin_kind === k ? "on" : ""}" aria-pressed="${e.insulin_kind === k}">${k === "rapid" ? "Rapid-acting" : "Long-acting"}</button>`).join("")}</div></fieldset></div>
      <label class="field"><span>Note</span><input id="evNote" maxlength="500" value="${esc(e.note || "")}"></label>
      <p class="note">The app records what you enter. It doesn't calculate or check insulin amounts.</p></form>`
    : `<div class="entryfacts">${e.bg != null ? `<div><span class="label">BG (meter)</span><b>${e.bg}</b> mg/dL</div>` : ""}
      ${e.insulin != null ? `<div><span class="label">Insulin given</span><b>${fmtU(e.insulin)}</b> ${KIND[e.insulin_kind]}</div>` : ""}</div>
    ${e.note ? `<p class="notes">${esc(e.note)}</p>` : ""}`}
    ${whenBox(e, "entries")}
    ${ed ? `<div class="actions"><button class="btn quiet small" data-act="del-entry">Delete entry</button></div>` : `<p class="meta">Read-only, except the date and time</p>`}
    ${saveBar}`;
  logBaseline();
}

/* One Save for every change to a logged meal or entry (okf/features/review-log.md): nothing is saved as it's typed;
   a bar floats up as soon as anything differs from what's saved. */
const saveBar = `<div class="savebar" id="logSave" hidden role="region" aria-label="Unsaved changes">
    <span class="sbtext">Unsaved changes</span><p class="err" id="logErr" role="alert"></p>
    <div class="actions"><button type="button" class="btn primary" data-act="log-save">Save changes</button><button type="button" class="btn quiet" data-act="log-discard">Discard</button></div></div>`;
function logSnap() {
  const v = id => $(id)?.value ?? null, f = $("#mdetForm");
  const ev = $("#entValForm");
  return { day: v("#whDay"), time: v("#whTime"), ent: ev ? JSON.stringify([v("#evBg"), v("#evCarbs"), v("#evIns"), ev.querySelector("[data-ekind].on")?.dataset.ekind ?? "", v("#evNote").trim()]) : null, eaten: $(".eatseg .on")?.dataset.eaten ?? "", total: v("#cfTotal"), cmt: (v("#cmtText") || "").trim(),
    det: f ? JSON.stringify([...f.querySelectorAll("input")].map(i => i.value).concat([...f.querySelectorAll("button.on")].map(b => b.dataset.dkind || b.dataset.dwhen))) : null };
}
function logBaseline() { S.log.base = logSnap(); S.log.done = new Set(); document.body.classList.remove("unsaved"); logDirty(); }
function logDirty() {
  const b = S.log.base, n = logSnap(), bar = $("#logSave"); if (!b || !bar) return false;
  const parts = { "#whenForm": n.day !== b.day || n.time !== b.time, "#entValForm": n.ent !== b.ent, "#mdetForm": n.det !== b.det, ".eatseg": n.eaten !== b.eaten,
    "#carbsFix": n.total !== b.total, "#cmtForm": !!n.cmt };
  for (const [sel, on] of Object.entries(parts)) $(sel)?.classList.toggle("dirty", on);
  const any = Object.values(parts).some(Boolean);
  if (bar.hidden === any) { bar.hidden = !any; if (!any) $("#logErr").textContent = ""; }
  document.body.classList.toggle("unsaved", any);
  return any;
}
async function saveLogEdits(btn) {
  const b = S.log.base, n = logSnap(), err = $("#logErr"), entry = !!S.log.selEntry, id = entry ? S.log.selEntry : S.log.sel;
  const steps = [];
  err.textContent = "";
  try {   // everything is checked before anything is saved
    if (!n.day || !n.time) throw new Error("Choose a date and a time.");
    if (n.day > localDay()) throw new Error("It can't be moved to a future day.");
    if (!entry && n.det !== b.det) {
      const m = S.log.data.meals.find(x => x.id === id), bg = $("#mdBg").value.trim(), body = readDetails($("#mdetForm"));
      if (bg !== "" && !(Number.isInteger(+bg) && +bg >= 20 && +bg <= 600)) throw new Error("Blood glucose must be a whole number between 20 and 600 mg/dL.");
      Object.assign(body, { bg: bg === "" ? null : +bg, bg_source: bg === "" ? null : +bg === m.bg ? m.bg_source : "meter" });
      steps.push(["details", () => api(`/api/meals/${id}/details`, { method: "PUT", body })]);
    }
    if (entry && n.ent !== b.ent) {   // the same checks as adding an entry (okf/domain/manual-entry.md)
      const [bg, carbs, ins, kind, note] = JSON.parse(n.ent), num = x => x === "" ? null : +x;
      const body = { bg: num(bg), carbs: num(carbs), insulin: num(ins), insulin_kind: ins === "" ? null : kind || null, note };
      if (body.bg != null && !(Number.isInteger(body.bg) && body.bg >= 20 && body.bg <= 600)) throw new Error("BG must be a whole number between 20 and 600 mg/dL.");
      if (body.carbs != null && !(body.carbs >= 0 && body.carbs <= 500)) throw new Error("Carbs are between 0 and 500 g.");
      if (body.insulin != null) {
        if (!(body.insulin > 0 && body.insulin <= 100) || Math.abs(body.insulin * 20 - Math.round(body.insulin * 20)) > 1e-6) throw new Error("Insulin is between 0.05 and 100 units, in steps of 0.05.");
        if (!body.insulin_kind) throw new Error("Choose rapid or long-acting for the insulin.");
      }
      if (body.bg == null && body.carbs == null && body.insulin == null && !note) throw new Error("An entry needs carbs, a BG reading, insulin or a note. To remove it, delete the entry.");
      steps.push(["entry", () => api(`/api/entries/${id}`, { method: "PUT", body })]);
    }
    if (!entry && n.eaten !== b.eaten) steps.push(["eaten", () => api(`/api/meals/${id}`, { method: "PATCH", body: { eaten: n.eaten } })]);
    if (!entry && n.total !== b.total) {   // a corrected total, with its reason (okf/domain/meal.md)
      const total = +n.total, reason = $("#cfReason").value.trim();
      if (n.total === "" || !(total >= 0 && total <= 1000)) throw new Error("Total carbs are between 0 and 1000 g.");
      if (reason.length < 3) { $("#cfReason").focus(); throw new Error("Say why the carbs changed."); }
      steps.push(["carbs", () => api(`/api/meals/${id}/carbs`, { method: "PUT", body: { total, reason } })]);
    }
    if (!entry && n.cmt) steps.push(["cmt", () => api(`/api/meals/${id}/comments`, { method: "POST", body: { text: n.cmt } })]);
    if (n.day !== b.day || n.time !== b.time)   // last: it can move the meal to another day (okf/rules/same-day-edits.md)
      steps.push(["when", () => api(`/api/${entry ? "entries" : "meals"}/${id}/when`, { method: "PUT", body: { day: n.day, time: n.time } })]);
  } catch (e) { err.textContent = e.message; return; }
  btn.disabled = true;
  for (const [k, run] of steps) {
    if (S.log.done.has(k)) continue;   // a retry after a failure doesn't repeat what was saved
    try { await run(); S.log.done.add(k); }
    catch (e) { err.textContent = (S.log.done.size ? "Some changes were saved. " : "") + e.message; btn.disabled = false; return; }
  }
  toast("Changes saved");
  if (entry) S.log.selEntry = id; else { S.log.sel = id; S.log.selEntry = null; }
  S.log.base = null; loadLog(n.day);   // follow it to its day
}

async function renderMeal() {
  if (S.log.adding) return renderEntryForm();
  if (S.log.selEntry) return renderEntry(S.log.data.entries.find(e => e.id === S.log.selEntry));
  const el = $("#mealDetail"), d = S.log.data, m = d.meals.find(x => x.id === S.log.sel);
  if (!m) { el.innerHTML = `<div class="empty">${d.meals.length ? "Choose a meal." : "Meals you save from the plate appear here."}</div>`; return; }
  const ed = d.editable;
  el.innerHTML = `
    <div class="mdh"><b>${m.time}</b><span class="c">${m.total} <small>g carbs</small></span></div>
    ${m.carbs_corrected != null ? `<p class="meta moved">Corrected from ${m.items_total} g, the foods' own total. The reason is in the comments.</p>` : ""}
    ${ed ? `<button class="linkbtn fixlink" data-act="fix-carbs">Change total carbs</button>
      <form id="carbsFix" class="carbsfix" hidden><p class="meta">For a discrepancy found later. The foods keep their saved carbs; the meal's total, the day's totals and the export use the new number.</p>
        <label class="field"><span>Total carbs</span><span class="unitin"><input id="cfTotal" type="number" inputmode="decimal" min="0" max="1000" step="any" required value="${m.total}"> g</span></label>
        <label class="field"><span>Why it changed (required)</span><input id="cfReason" maxlength="400" minlength="3" placeholder="e.g. only ate half the pasta, label was wrong" autocomplete="off"></label>
        <button type="button" class="linkbtn" data-act="fix-cancel">Keep the total as it was</button></form>` : ""}
    <span class="meta">${m.items.map(i => `${esc(i.food_name)}, ${i.carbs} g carbs (${i.entered_carbs != null ? "entered by hand" : fmtG(itemG(i))})`).join(" · ")}</span>
    ${whenBox(m, "meals")}
    <div class="glab"><span class="label">BG, insulin and time to eat</span></div>
    ${ed ? `<form id="mdetForm" class="mdetform"><label class="field"><span>Blood glucose (mg/dL)${m.bg != null && m.bg_source === "cgm" ? " · from the CGM" : ""}</span><input id="mdBg" type="number" inputmode="numeric" min="20" max="600" step="1" value="${m.bg ?? ""}" placeholder="Meter reading"></label>
        ${detailFields(m)}</form>`
      : `<p class="${detailSummary(m) ? "" : "meta"}">${esc(detailSummary(m)) || "None added"}</p>`}
    ${S.session?.glucose ? `<div class="glab"><span class="label">Glucose · mg/dL</span><span class="meta" id="gUpdated"></span></div><div id="gBox"><p class="meta">Loading glucose…</p></div>` : ""}
    <div class="glab"><span class="label">How much was eaten</span>${ed ? "" : `<span class="meta">Read-only</span>`}</div>
    ${ed ? `<div class="seg neutral eatseg" role="group" aria-label="How much was eaten">${EATEN.map(x => `<button type="button" data-eaten="${x}" class="${m.eaten === x ? "on" : ""}" aria-pressed="${m.eaten === x}">${cap(x)}</button>`).join("")}</div>
      <p class="note">This is a note. Carbs stay as served.</p>` : `<p>${m.eaten ? cap(m.eaten) : "Not set"}</p>`}
    <div class="glab"><span class="label">Comments</span></div>
    <div class="cmt">${m.comments.map(c => `<div><span class="tm">${c.time.length > 5 ? movedLabel(c.time) : c.time}</span>${esc(c.text)}</div>`).join("") || (ed ? "" : `<span class="meta">None</span>`)}
      ${ed ? `<form class="cmtform" id="cmtForm"><input id="cmtText" maxlength="500" placeholder="Add a comment" aria-label="Add a comment" autocomplete="off"></form>` : ""}</div>
    <div class="actions" style="padding-top:12px"><button class="btn quiet small" data-act="pin-meal">Pin as favorite</button>
      ${ed ? `<button class="btn quiet small" data-act="del-meal">Delete meal</button>` : ""}</div>
    <form class="cmtform" id="pinMeal" hidden><input id="pinMealName" maxlength="60" value="${suggestName(m.time)}" aria-label="Favorite name"><button class="btn small">Pin</button></form>
    ${saveBar}`;
  logBaseline();
  if (S.session?.glucose) loadCurve(m);
}

async function loadCurve(m) {
  let w;
  try { w = await api(`/api/meals/${m.id}/glucose`); } catch (err) { $("#gBox") && ($("#gBox").innerHTML = `<p class="meta">${esc(err.message)}</p>`); return; }
  if (S.log.sel !== m.id || !$("#gBox")) return;
  $("#gBox").innerHTML = curveSvg(w) + `<div class="gvals">
    <span>At meal <b>${w.at_meal ?? "–"}</b></span>
    <span>Peak <b>${w.peak ? w.peak.sgv : "–"}</b>${w.peak ? ` at ${hhmm(new Date(w.peak.ms))}` : ""}</span>
    <span>2 h <b>${w.two_h ?? "–"}</b></span>
    ${w.lowest && w.lowest.sgv < w.low ? `<span class="warn">Lowest <b class="warn">${w.lowest.sgv}</b> at ${hhmm(new Date(w.lowest.ms))}</span>` : ""}
    <span class="${w.coverage < 0.7 ? "warn" : ""}">Sensor ${Math.round(w.coverage * 100)}%</span>
    ${w.in_progress ? `<span>In progress</span>` : ""}</div>
    ${w.overlapping_meals.length ? `<p class="note">Another meal falls in this window, so the curve shows both.</p>` : ""}
    ${(w.entries || []).length ? `<p class="note">Squares are meter readings; ticks along the bottom are insulin entries.</p>` : ""}`;
}

function curveSvg(w) {
  if (!w.points.length) return `<p class="meta">No sensor data for this meal.</p>`;
  const W = 640, H = 230, L = 44, R = 14, T = 16, B = 30;
  const maxV = Math.max(300, ...w.points.map(p => p[1] + 10)), minV = Math.min(40, ...w.points.map(p => p[1] - 10));
  const X = t => L + (t - w.start_ms) / (w.end_ms - w.start_ms) * (W - L - R);
  const Y = v => T + (1 - (v - minV) / (maxV - minV)) * (H - T - B);
  const o = [`<svg class="gcurve" viewBox="0 0 ${W} ${H}" role="img" aria-label="Glucose around the meal, mg/dL">`,
    `<rect x="${L}" y="${Y(w.high)}" width="${W - L - R}" height="${Y(w.low) - Y(w.high)}" fill="var(--sunk)"/>`];
  for (const v of [w.low, w.high, 250]) o.push(`<text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end" class="ax">${v}</text>`);
  o.push(`<line x1="${L}" x2="${W - R}" y1="${Y(250)}" y2="${Y(250)}" stroke="var(--line)" stroke-dasharray="2 3"/>`);
  const h0 = new Date(w.start_ms); h0.setMinutes(0, 0, 0);
  for (let t = h0.getTime() + 3600e3; t <= w.end_ms; t += 3600e3) if (X(t) < W - R - 18) o.push(`<text x="${X(t)}" y="${H - 8}" text-anchor="middle" class="ax">${hhmm(new Date(t))}</text>`);
  for (const om of w.overlapping_meals) o.push(`<line x1="${X(om)}" x2="${X(om)}" y1="${T}" y2="${H - B}" stroke="var(--vein)" stroke-dasharray="1 3"/><text x="${X(om) + 4}" y="${T + 24}" class="ax">meal ${hhmm(new Date(om))}</text>`);
  o.push(`<line x1="${X(w.meal_ms)}" x2="${X(w.meal_ms)}" y1="${T}" y2="${H - B}" stroke="var(--accent)"/><text x="${X(w.meal_ms) + 5}" y="${T + 10}" class="ax" fill="var(--accent)">meal ${hhmm(new Date(w.meal_ms))}</text>`);
  const t2 = w.meal_ms + 120 * 60e3;
  o.push(`<line x1="${X(t2)}" x2="${X(t2)}" y1="${T}" y2="${H - B}" stroke="var(--vein)" stroke-dasharray="3 3"/><text x="${X(t2) + 5}" y="${T + 10}" class="ax">2 h</text>`);
  // Gaps over 10 minutes break the line (okf/domain/glucose-reading.md: gaps stay gaps).
  let d = "", prev = null;
  for (const [t, v] of w.points) { d += `${!prev || t - prev > 10 * 60e3 ? "M" : "L"}${X(t).toFixed(1)},${Y(v).toFixed(1)} `; prev = t; }
  o.push(`<path d="${d}" fill="none" stroke="var(--ink)" stroke-width="2" stroke-linejoin="round"/>`);
  for (const en of w.entries || []) {
    if (en.bg != null) o.push(`<rect x="${X(en.ms) - 5}" y="${Y(en.bg) - 5}" width="10" height="10" fill="var(--paper)" stroke="var(--ink)" stroke-width="2"><title>Meter ${en.bg}</title></rect>`);
    if (en.insulin != null) o.push(`<line x1="${X(en.ms)}" x2="${X(en.ms)}" y1="${H - B}" y2="${H - B - 12}" stroke="var(--ink)" stroke-width="2"/><text x="${X(en.ms) + 4}" y="${H - B - 4}" class="ax">${fmtU(en.insulin)}</text>`);
  }
  for (const p of w.points) if (p[1] < w.low) o.push(`<circle cx="${X(p[0])}" cy="${Y(p[1])}" r="3" fill="var(--warn)"/>`);
  const mark = (t, v, dy) => `<circle cx="${X(t)}" cy="${Y(v)}" r="4" fill="var(--paper)" stroke="var(--ink)" stroke-width="2"/><text x="${X(t)}" y="${Y(v) + dy}" text-anchor="middle" class="vl">${v}</text>`;
  const near = target => w.points.reduce((b, p) => Math.abs(p[0] - target) < Math.abs(b[0] - target) ? p : b);
  if (w.at_meal != null) o.push(mark(near(w.meal_ms)[0], w.at_meal, 18));
  if (w.peak) o.push(mark(w.peak.ms, w.peak.sgv, -9));
  if (w.two_h != null && (!w.peak || Math.abs(near(t2)[0] - w.peak.ms) > 15 * 60e3)) o.push(mark(near(t2)[0], w.two_h, -9));
  o.push("</svg>");
  return o.join("");
}

let confirmDelete = 0;
$("#v-log").addEventListener("click", async e => {
  if (e.target.closest("#mealDetail")) setTimeout(logDirty);   // after the switches below have moved
  const t = e.target.closest("[data-day],[data-meal],[data-entry],[data-kind],[data-ekind],[data-eaten],[data-act],[data-period],[data-restore]"); if (!t) return;
  const d = S.log.data;
  if (t.matches("[data-day],[data-meal],[data-entry],[data-period],[data-restore],[data-act=add-entry]") && logDirty()) {
    toast("Save or discard the changes first");   // nothing typed is lost without a choice
    const bar = $("#logSave"); bar.classList.remove("nudge"); void bar.offsetWidth; bar.classList.add("nudge"); return;
  }
  if (t.dataset.act === "log-save") return saveLogEdits(t);
  if (t.dataset.act === "log-discard") { S.log.base = null; return renderMeal(); }
  if (t.dataset.restore) {
    const [kind, id] = t.dataset.restore.split(":");
    try {
      await api(`/api/${kind === "meal" ? "meals" : "entries"}/${id}/restore`, { method: "POST" });
      toast(kind === "meal" ? "Meal restored" : "Entry restored");
      if (kind === "meal") { S.log.sel = +id; S.log.selEntry = null; } else S.log.selEntry = +id;
      loadLog(d.day);
    } catch (err) { toast(err.message); }
    return;
  }
  if (t.dataset.day) { const day = t.dataset.day === "today" ? localDay() : shiftDay(d.day, +t.dataset.day); S.log.sel = null; loadLog(day); }
  else if (t.dataset.period) { S.log.period = t.dataset.period === "day" ? "day" : +t.dataset.period; if (S.log.period !== "day") await loadPeriod(); renderLog(); }
  else if (t.dataset.act === "add-entry") {   // the form opens below the list on a phone: bring it into view
    S.log.adding = true; S.log.selEntry = null; renderLog();
    $("#mealDetail").scrollTop = 0;
    $("#entryForm")?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  }
  else if (t.dataset.act === "entry-cancel") { S.log.adding = false; renderLog(); }
  else if (t.dataset.kind) { S.log.kind = S.log.kind === t.dataset.kind ? null : t.dataset.kind; entryPreview(); }
  else if (t.dataset.entry) { S.log.selEntry = +t.dataset.entry; S.log.adding = false; confirmEntry = 0; renderLog(); if (innerWidth <= 680) $("#mealDetail").scrollIntoView(); }
  else if (t.dataset.act === "del-entry") {
    if (Date.now() - confirmEntry > 4000) { confirmEntry = Date.now(); t.textContent = "Tap again to delete"; return; }
    try { await api(`/api/entries/${S.log.selEntry}`, { method: "DELETE" }); toast("Entry deleted. It can be restored from Deleted, below the day."); S.log.selEntry = null; loadLog(d.day); } catch (err) { toast(err.message); }
  }
  else if (t.dataset.act === "fix-carbs") { t.hidden = true; $("#carbsFix").hidden = false; $("#cfTotal").select(); }
  else if (t.dataset.act === "fix-cancel") { $("#carbsFix").reset(); $("#carbsFix").hidden = true; $(".fixlink").hidden = false; logDirty(); }
  else if (t.dataset.meal) { S.log.sel = +t.dataset.meal; S.log.selEntry = null; S.log.adding = false; confirmDelete = 0; renderLog(); if (innerWidth <= 680) $("#mealDetail").scrollIntoView(); }
  else if (t.dataset.ekind) {   // an entry's insulin type, saved with the rest
    const on = !t.classList.contains("on");
    t.parentElement.querySelectorAll("button").forEach(b => { b.classList.toggle("on", on && b === t); b.setAttribute("aria-pressed", on && b === t); });
    logDirty();
  }
  else if (t.dataset.eaten) {   // chosen here, saved with the rest; tapping the chosen one clears it
    const on = !t.classList.contains("on");
    t.parentElement.querySelectorAll("button").forEach(b => { b.classList.toggle("on", on && b === t); b.setAttribute("aria-pressed", on && b === t); });
    logDirty();
  }
  else if (t.dataset.act === "pin-meal") { $("#pinMeal").hidden = false; $("#pinMealName").select(); }
  else if (t.dataset.act === "del-meal") {
    if (Date.now() - confirmDelete > 4000) { confirmDelete = Date.now(); t.textContent = "Tap again to delete"; return; }
    try { await api(`/api/meals/${S.log.sel}`, { method: "DELETE" }); toast("Meal deleted. It can be restored from Deleted, below the day."); S.log.sel = null; loadLog(d.day); } catch (err) { toast(err.message); }
  }
  else if (t.dataset.act === "export") {
    const from = $("#exFrom").value, to = $("#exTo").value;
    if (!from || !to || from > to) { toast("Choose a start date before the end date."); return; }
    // a formatted PDF to read or send, or the CSV for a spreadsheet (okf/features/export-log.md)
    if (t.dataset.fmt === "pdf" && (Date.parse(to) - Date.parse(from)) / 864e5 + 1 > 92) { toast("A PDF covers up to 92 days. Choose a shorter range."); return; }
    location.href = `/api/export.${t.dataset.fmt === "pdf" ? "pdf" : "csv"}?start=${from}&end=${to}`;
  }
});
$("#v-log").addEventListener("input", e => { if (e.target.closest("#entryForm")) entryPreview(); if (e.target.closest("#mealDetail")) logDirty(); });
$("#v-log").addEventListener("change", e => { if (e.target.closest("#mealDetail")) logDirty(); });
$("#v-log").addEventListener("submit", async e => {
  if (["carbsFix", "mdetForm", "whenForm", "cmtForm", "entValForm"].includes(e.target.id)) {   // Enter in any of them: the one Save
    e.preventDefault(); if (logDirty()) saveLogEdits($("[data-act=log-save]")); return;
  }
  if (e.target.id === "entryForm") {
    e.preventDefault();
    const v = id => $(id).value.trim();
    const body = { client_id: uid(), day: S.log.data.day, time: v("#enTime"), note: v("#enNote"),
      bg: v("#enBg") ? +v("#enBg") : null, carbs: v("#enCarbs") ? +v("#enCarbs") : null,
      insulin: v("#enIns") ? +v("#enIns") : null, insulin_kind: v("#enIns") ? S.log.kind : null };
    try { const r = await api("/api/entries", { method: "POST", body }); S.log.selEntry = r.id; toast("Entry saved"); }
    catch (err) {
      if (err.status) { $("#enErr").textContent = err.message; return; }
      S.queue.push({ kind: "entry", ...body }); store.set("queue", S.queue); renderStatus();
      toast("Saved on this tablet. It will sync when the server is back.");
    }
    S.log.adding = false; loadLog(body.day); return;
  }
  if (e.target.id === "pinMeal") {
    e.preventDefault(); const name = $("#pinMealName").value.trim();
    if (name && await pinFavorite(`/api/meals/${S.log.sel}/favorite`, { name })) $("#pinMeal").hidden = true;
    return;
  }
});

/* ---------- manage (parent PIN) ---------- */
/* ---------- Manage navigation (okf/design/guidelines/navigation.md) ---------- */
// Every step is a history entry; check screens keep their data in the entry so Back/Forward can re-open them.
const mSnap = () => ({ tab: S.m.tab, food: S.m.food, addTab: S.m.addTab,
  scan: S.m.scan?.stage === "review" ? S.m.scan : null, review: S.m.review || null });
const mHash = s => "#manage/" + [s.tab, s.tab === "foods" ? s.food : null, s.tab === "foods" && s.food === "add" ? s.addTab : null]
  .filter(Boolean).map(encodeURIComponent).join("/");
function mApply(s) {
  Object.assign(S.m, { tab: s.tab || "foods", food: s.food ?? null, addTab: ["new", "batch"].includes(s.addTab) ? s.addTab : "lookup", scan: s.scan || null, review: s.review || null, err: "" });
  S.m.look.scanning = false;
}
function mNav({ replace = false } = {}) {   // record the step, then draw it
  const depth = (history.state?.m?.depth ?? 0) + (replace ? 0 : 1);
  const snap = { ...mSnap(), depth };
  history[replace ? "replaceState" : "pushState"]({ m: snap }, "", mHash(snap));
  renderManage(); scanMath(); foodMath();
}
function mCancel(parent) {   // leave without saving: back one step if this session made it, else up a level
  if ((history.state?.m?.depth ?? 0) > 0) history.back();
  else { parent(); mNav({ replace: true }); }
}
let mBooted = false;
function mFromHash() {   // #manage/foods/pasta-cooked, #manage/foods/add/scan, #manage/style …
  const [, tab, food, addTab] = location.hash.split("/").map(decodeURIComponent);
  if (!tab) return;
  mApply({ tab, food: food || null, addTab, scan: null });
}
addEventListener("popstate", e => {
  if (!e.state?.m || !location.hash.startsWith("#manage")) return;
  mApply(e.state.m); route();
});

function renderManage() {
  stopScanner();
  queueMicrotask(startScanner);   // restarts only if the Look up tab is showing
  const el = $("#manageView");
  if (!S.session) { el.innerHTML = `<div class="empty">Can't reach the kitchen server. Managing foods needs the server.</div>`; return; }
  if (!S.session.pin_set) {
    el.innerHTML = `<form class="pinbox" id="pinCreate"><h2>Create a parent PIN</h2><p class="meta">The PIN protects foods, photos and Nightscout settings. 4 to 8 digits.</p>
      <input id="pin1" inputmode="numeric" pattern="\\d{4,8}" type="password" aria-label="New PIN" autocomplete="new-password">
      <input id="pin2" inputmode="numeric" pattern="\\d{4,8}" type="password" aria-label="Repeat PIN" autocomplete="new-password">
      <p class="err" id="pinErr"></p><div class="actions"><button class="btn primary">Save PIN</button><button type="button" class="btn quiet" data-act="pin-cancel">Cancel</button></div></form>`;
    return;
  }
  if (!pinStore.get()) {
    el.innerHTML = `<form class="pinbox" id="pinEnter"><h2>Parent PIN</h2>
      <input id="pin" inputmode="numeric" type="password" aria-label="PIN" autocomplete="current-password" autofocus>
      <p class="err" id="pinErr"></p><div class="actions"><button class="btn primary">Unlock</button><button type="button" class="btn quiet" data-act="pin-cancel">Cancel</button></div></form>`;
    return;
  }
  el.innerHTML = `<div class="subtabs">${[["foods", "Foods and photos"], ["style", "Photo style"], ["tags", "Tags"], ["nightscout", "Nightscout"], ["settings", "Settings"]].map(([k, l]) =>
      `<button data-mtab="${k}" class="${S.m.tab === k ? "on" : ""}">${l}</button>`).join("")}
      <button data-act="lock" style="margin-left:auto">Lock</button></div><div class="mbody" id="mbody"></div>`;
  ({ foods: renderManageFoods, style: loadStyle, tags: renderTags, nightscout: renderNightscout, settings: renderSettings })[S.m.tab]();
}

const $m = () => $("#mbody");
function renderManageFoods() {
  foodDirty = false;   // the form is drawn from the saved food
  const fibView = S.m.food === FIBER, f = S.m.food === "add" || fibView ? null : foodById(S.m.food), focus = S.m.food === "add" || fibView || f;
  $m().innerHTML = `<div class="split ${focus ? "focus" : ""}" style="flex:1;display:flex;min-width:0">
    <div class="list"><div class="rows" id="mRows">${manageRows()}</div></div>
    <div class="detail">${focus ? `<div class="mhead"><button type="button" class="btn quiet small" data-act="m-list">‹ Foods</button><b>${f ? esc(f.name) : fibView ? "Fill in fiber" : "Add a food"}</b></div>` : ""}${S.m.food === "add" ? addPanel() : fibView ? `<div id="fiberBox">${fiberPanel()}</div>` : f ? foodForm(f) + `<div id="portionsBox">${portionsEditor(f)}</div>` : addPrompt()}</div></div>`;
  foodMath();
  if (S.m.shown !== S.m.food) { S.m.shown = S.m.food; $("#v-manage").scrollTop = 0; }   // a new screen starts at the top on a phone
}
function manageRows() {
  return `<button class="row addrow ${S.m.food === "add" ? "on" : ""}" data-mfood="add"><span class="t"><b>+ Add a food</b><span>Look it up, scan a label, or type it in</span></span></button>
    ${S.foods.some(x => x.fiber_lookup) || S.m.food === FIBER ? `<button class="row addrow ${S.m.food === FIBER ? "on" : ""}" data-mfood="${FIBER}"><span class="t"><b>Fill in fiber</b>
      <span>${S.foods.filter(x => x.fiber_lookup).length} saved food${S.foods.filter(x => x.fiber_lookup).length === 1 ? "" : "s"} can get fiber from their source</span></span></button>` : ""}
    <button class="row addrow" data-act="quick-scan"><span class="t"><b>Scan a barcode</b><span>Check the label numbers, save, and a photo is made for you</span></span></button>
    ${S.foods.map(x => `<button class="row ${x.id === S.m.food ? "on" : ""}" data-mfood="${esc(x.id)}">
      ${x.portions[0] && shownPhoto(x.portions[0]) ? `<img ${sized(shownPhoto(x.portions[0]), "64px")} alt="">` : `<span class="noimg"></span>`}
      <span class="t"><b>${esc(x.name)}</b><span>${x.portions.length} portion${x.portions.length === 1 ? "" : "s"}</span>
      ${x.portions.some(p => p.job) ? `<em class="gen">Making a photo…</em>` : x.portions.some(p => p.photo.candidate) ? `<em class="gen">New photo to check</em>` : ""}
      ${x.trust !== "parent-verified" ? "<em>Not verified</em>" : ""}</span></button>`).join("")}`;
}

/* ---------- fill in fiber from each food's own source (okf/features/fill-in-fiber.md) ---------- */
const FIBER = "fill-in-fiber";
const fib = () => (S.m.fib ??= {});   // food id -> { status, fiber, per_grams, notes, warnings, conf }
const fibReady = r => r?.status === "ready" && r.fiber != null && r.fiber !== "" && r.conf;
function fiberPanel() {
  const st = fib(), foods = S.foods.filter(f => f.fiber_lookup || st[f.id]?.status === "saved");
  const waiting = foods.filter(f => !st[f.id]).length, ready = foods.filter(f => fibReady(st[f.id])).length;
  if (!foods.length) return `<div class="form"><p class="meta">Every food whose source can be read again has fiber now. Fiber for other foods can be typed on the food.</p></div>`;
  return `<div class="form fiberfill">
    <p class="meta">Fiber is read again from where each food came from: its barcode, FatSecret or USDA number, or its saved label photo.
      Check each number against the label or source and tick it. Only fiber is saved; carbs, portions and the log stay as they are.</p>
    ${waiting ? `<div class="actions"><button class="btn primary" data-act="fib-look" ${st.busy ? "disabled" : ""}>${st.busy ? "Looking up…" : `Look up fiber for ${waiting} food${waiting === 1 ? "" : "s"}`}</button></div>` : ""}
    <ul class="fiblist">${foods.map(f => fiberRow(f, st[f.id])).join("")}</ul>
    <p class="err" id="fibErr"></p>
    <div class="actions"><button class="btn primary" data-act="fib-save" ${ready ? "" : "disabled"}>Save ${ready} checked</button></div></div>`;
}
function fiberRow(f, r) {
  const src = f.source_kind === "label" ? `Label photo · ${esc(f.source_ref)}` : esc(f.source_ref), label = f.label_photo;
  const head = `<div class="fibhead"><b>${esc(f.name)}</b><span class="meta">${src}</span></div>`;
  if (!r || r.status === "loading") return `<li>${head}<span class="meta">${r ? "Looking it up…" : "Not looked up yet"}</span></li>`;
  if (r.status === "error") return `<li>${head}<p class="err">${esc(r.err)}</p><button class="btn small quiet" data-act="fib-retry" data-fid="${esc(f.id)}">Try again</button></li>`;
  if (r.status === "saved") return `<li class="saved">${head}<span class="meta">Saved: ${r.fiber} g fiber per ${r.per_grams} g</span></li>`;
  const where = label ? "the label" : f.source_kind === "openfoodfacts" ? "the package" : "the source";
  return `<li data-fid="${esc(f.id)}">${head}
    ${r.notes.length ? `<span class="meta">From the source: ${esc(r.notes.join("; "))}</span>` : ""}
    ${r.warnings.length ? `<ul class="warnlist">${r.warnings.map(w => `<li>${esc(w)}</li>`).join("")}</ul>` : ""}
    <div class="fibrow">${label ? `<a href="${photoUrl(label)}" target="_blank" rel="noopener"><img ${sized(label, "72px")} alt="Nutrition label"></a>` : ""}
      <div class="bnum"><input class="fibVal" type="number" step="0.1" min="0" inputmode="decimal" value="${r.fiber ?? ""}" placeholder="Not listed" aria-label="Grams of fiber">
        <span>g fiber per ${r.per_grams} g${r.per_serving ? " serving" : ""}</span></div></div>
    <label class="check"><input type="checkbox" class="fibConf" ${r.conf ? "checked" : ""} ${r.fiber == null || r.fiber === "" ? "disabled" : ""}><span>Matches ${where}</span></label></li>`;
}
const refreshFiber = () => { const box = $("#fiberBox"); if (box) box.innerHTML = fiberPanel(); };
async function fiberLook(ids) {
  const st = fib(); st.busy = true; ids.forEach(id => (st[id] = { status: "loading" })); refreshFiber();
  for (const id of ids) {   // one at a time: Gemini and the databases are asked gently
    try { const r = await api(`/api/foods/${encodeURIComponent(id)}/fiber-lookup`, { parent: true }); st[id] = { status: "ready", ...r, conf: false }; }
    catch (err) { st[id] = { status: "error", err: err.message }; }
    refreshFiber();
    await new Promise(r => setTimeout(r, 1200));   // Open Food Facts limits quick repeat requests
  }
  st.busy = false; refreshFiber();
}
async function fiberSave() {
  const st = fib(), problems = [];
  for (const f of S.foods.filter(f => fibReady(st[f.id]))) {   // each row ticked on its own (okf/features/fill-in-fiber.md)
    try { await api(`/api/foods/${encodeURIComponent(f.id)}/fiber`, { method: "PUT", parent: true, body: { fiber: +st[f.id].fiber, confirmed: true } }); st[f.id].status = "saved"; }
    catch (err) { problems.push(`${f.name}: ${err.message}`); }
  }
  await loadFoods(); refreshFiber(); if ($("#mRows")) $("#mRows").innerHTML = manageRows();
  if ($("#fibErr")) $("#fibErr").textContent = problems.join(" · ");
  toast(problems.length ? `${problems.length} couldn't be saved` : "Fiber saved");
}

/* ---------- live photo jobs (okf/features/photo-pipeline.md) ---------- */
const jobsRunning = () => S.foods.some(f => f.portions.some(p => p.job));
const sinceText = iso => { const s = Math.max(0, Math.round((Date.now() - new Date(iso)) / 1000)); return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`; };
let jobPoll = null;
function watchJobs() {
  if (jobPoll || !jobsRunning()) return;
  jobPoll = setInterval(async () => {
    const before = new Map(S.foods.flatMap(f => f.portions.map(p => [p.id, { job: p.job, f, p }])));
    try { S.foods = await api("/api/foods"); store.set("foods", S.foods); } catch { return; }
    for (const f of S.foods) for (const p of f.portions) {   // tell the parent when one finishes, wherever they are
      const was = before.get(p.id);
      if (was?.job && !p.job) toast(p.job_error ? `Photo for ${f.name}, ${p.label} failed: ${p.job_error}` : `New photo ready to check: ${f.name}, ${p.label}`);
    }
    liveManage();
    if (!jobsRunning()) { clearInterval(jobPoll); jobPoll = null; }
  }, 1000);   // a fast photo takes about 3 s, so check often
}
function liveManage() {   // redraw only the list and the portions, so a half-typed food form is left alone
  if (S.m.tab !== "foods" || location.hash.slice(1).split("/")[0] !== "manage") return;
  if ($("#mRows")) $("#mRows").innerHTML = manageRows();
  const f = foodById(S.m.food), box = $("#portionsBox");
  if (f && box && !box.contains(document.activeElement)) box.innerHTML = portionsEditor(f);
}
setInterval(() => document.querySelectorAll("[data-since]").forEach(el => (el.textContent = sinceText(el.dataset.since))), 1000);

/* "X g carbs per Y g" → per 100 g, kept to 2 decimals so a portion of exactly Y g gives back X. */
function carbsPer100() {
  const c = parseFloat($("#fCarbs")?.value), b = parseFloat($("#fBase")?.value);
  if (!(c >= 0) || !(b > 0) || c > b) return null;
  return Math.round(c / b * 10000) / 100;
}
function foodMath() {
  cookExplain("f");
  const el = $("#fMath"); if (!el) return;
  const cp = carbsPer100(), c = parseFloat($("#fCarbs").value), b = parseFloat($("#fBase").value);
  el.innerHTML = cp == null ? (c > b ? `<span class="warn">Carbs can't be more than the amount of food.</span>` : "Enter both numbers.")
    : `= <b>${cp}</b> g carbs per 100 g${b !== 100 ? ` · ${b} g counts as <b>${whole(exact(b, cp))}</b> g carbs` : ""}`;
}

function addPrompt() {
  return `<div class="addprompt"><button class="btn primary big" data-mfood="add">Add a food</button>
    <p class="meta">Look it up, scan a label, or type it in. Or choose a food on the left to edit it.</p></div>`;
}

/* Portion labels: an amount, then a unit (okf/domain/portion.md); the server checks the same way (core.portion_amount) */
const FRACS = { "¼": 1 / 4, "½": 1 / 2, "¾": 3 / 4, "⅓": 1 / 3, "⅔": 2 / 3, "⅛": 1 / 8 };
const LABEL_RE = /^(\d+(?:\.\d+)?(?: \d+\/\d+)?|\d+\/\d+|\d*[¼½¾⅓⅔⅛])\s*([A-Za-z].*)$/;
const LABEL_PATTERN = String.raw`(\d+(\.\d+)?( \d+/\d+)?|\d+/\d+|\d*[¼½¾⅓⅔⅛])\s*[A-Za-z].*`;   // for pattern="" on inputs
const LABEL_HINT = "A number, then the unit: 1 cup, 2 slices, ½ serving";
const PLURAL = new Set(["serving", "cup", "slice", "piece", "package", "bowl", "bar", "cookie", "cracker", "nugget", "egg", "scoop",
  "pouch", "stick", "can", "bottle", "glass", "handful", "spoon", "tablespoon", "teaspoon", "bag", "box", "wrap"]);
function portionAmount(label) {
  const m = LABEL_RE.exec((label || "").trim()); if (!m) return null;
  let n = 0;
  for (const part of m[1].split(" ")) {
    if (part.includes("/")) { const [a, b] = part.split("/").map(Number); if (!b) return null; n += a / b; }
    else if (FRACS[part.at(-1)] != null) n += (+part.slice(0, -1) || 0) + FRACS[part.at(-1)];
    else n += +part;
  }
  return n > 0 ? { n, unit: m[2].trim() } : null;
}
function fmtAmount(n) {
  const whole = Math.floor(n + 1e-9);
  for (const [ch, v] of Object.entries(FRACS)) if (Math.abs(n - whole - v) < 0.01) return `${whole || ""}${ch}`;
  return Math.abs(n - whole) < 0.01 ? String(whole) : String(+n.toFixed(2));
}
function unitFor(n, unit) {
  const [first, ...rest] = unit.split(" ");
  const single = /s$/i.test(first) && PLURAL.has(first.slice(0, -1).toLowerCase()) ? first.slice(0, -1) : first;
  return [single + (n > 1 + 1e-9 && PLURAL.has(single.toLowerCase()) ? "s" : ""), ...rest].join(" ");
}
/* A portion from the package's serving text: '1 bar (40 g)' -> '1 bar'; plain grams -> '1 serving' (okf/features/food-lookup.md) */
function suggestPortion(text) {
  const t = (text || "").replace(/\(.*?\)/g, "").replace(/\s+/g, " ").trim(), a = portionAmount(t);
  return a && !/^(g|grams?|ml|oz)$/i.test(a.unit) && t.length <= 40 ? t : "1 serving";
}
/* Note for Gemini on the first portion, so the photo made right after saving uses it (okf/domain/photo-style.md) */
const noteField = id => `<label class="field"><span>Note for Gemini, for the photo (optional)</span><input id="${id}" maxlength="300" placeholder="e.g. plain rice, no sauce, ignore the fork"></label>`;
const labelInput = (id, value, cls = "") => `<input ${id ? `id="${id}"` : ""} ${cls ? `class="${cls}"` : ""} required maxlength="40" pattern="${LABEL_PATTERN}" title="${LABEL_HINT}" placeholder="1 cup" value="${esc(value)}" aria-label="Portion: a number, then the unit">`;

/* Dry, raw or cooked carbs, and a measured cooking ratio (okf/domain/food.md, okf/rules/cooking-ratio-measured.md) */
const BASIS = { "as-sold": "food, as sold", raw: "dry / raw food", cooked: "cooked food" };
const STATE = { raw: "dry / raw", cooked: "cooked" };
// '42 g carbs per 56 g of [dry / raw food]': the state is part of the carbs sentence (okf/domain/food.md)
const basisSelect = (v, p) => `<select id="${p}Basis" class="basispick" aria-label="State of the food those grams are for">${Object.entries(BASIS).map(([k, l]) =>
    `<option value="${k}" ${(v?.basis || "as-sold") === k ? "selected" : ""}>${l}</option>`).join("")}</select>`;
// required for dry / raw or cooked food, right under the carbs line (okf/domain/food.md)
const cookRatio = (v, p) => `<div class="cookratio" ${(v?.basis || "as-sold") === "as-sold" ? "hidden" : ""}>
      <span class="clabel">Cooking ratio, needed for dry / raw or cooked food: weigh one batch before and after cooking</span>
      <div class="basebox"><input id="${p}CookRaw" type="number" step="0.1" min="0.1" inputmode="decimal" aria-label="Batch weight dry or raw, grams" value="${v?.cook_raw_g ?? ""}" placeholder="e.g. 100">
        <span>g dry / raw became</span><input id="${p}CookCooked" type="number" step="0.1" min="0.1" inputmode="decimal" aria-label="Same batch cooked, grams" value="${v?.cook_cooked_g ?? ""}" placeholder="e.g. 240"><span>g cooked</span></div>
      ${v?.cook_ratio ? `<p class="meta">Saved: ×${+v.cook_ratio.toFixed(2)}, weighed ${dayLabel(v.cook_measured_at)}</p>` : ""}</div>
    <p class="cookexplain" id="${p}CookExplain"></p>`;
function cookBody(p) {
  const basis = $(`#${p}Basis`)?.value || "as-sold";
  const raw = parseFloat($(`#${p}CookRaw`)?.value), cooked = parseFloat($(`#${p}CookCooked`)?.value);
  const none = basis === "as-sold" || (isNaN(raw) && isNaN(cooked));
  return { basis, cook_raw_g: none ? null : isNaN(raw) ? null : raw, cook_cooked_g: none ? null : isNaN(cooked) ? null : cooked };
}
/* What the scale should show, in plain words, for the numbers typed so far */
function cookExplain(p) {
  const el = $(`#${p}CookExplain`); if (!el) return;
  const n = x => +(+x).toFixed(1);
  const c = parseFloat($(p === "f" ? "#fCarbs" : "#sCarbs")?.value), g = parseFloat($(p === "f" ? "#fBase" : "#sGrams")?.value);
  const { basis, cook_raw_g: raw, cook_cooked_g: cooked } = cookBody(p), r = raw > 0 && cooked > 0 ? cooked / raw : null;
  const box = el.closest("form").querySelector(".cookratio");
  box.hidden = basis === "as-sold";
  box.querySelectorAll("input").forEach(i => (i.required = basis !== "as-sold"));   // a hidden field must not block saving
  if (!(g > 0) || !(c >= 0)) { el.textContent = ""; return; }
  el.innerHTML = basis === "as-sold"
    ? `Weigh it as it comes: <b>${n(g)} g</b> on the scale = <b>${n(c)} g carbs</b>.`
    : basis === "raw"
      ? `Weigh it <b>dry / raw, before cooking</b>: ${n(g)} g on the scale = ${n(c)} g carbs.` + (r
        ? ` Cooked (×${n(r)}), the same amount weighs about ${n(g * r)} g, so the plate can also take the cooked weight.`
        : ` <span class="warn">Add the batch weights above to save it.</span>`)
      : `Weigh it <b>after cooking</b>: ${n(g)} g cooked on the scale = ${n(c)} g carbs.` + (r
        ? ` Before cooking (×${n(r)}) that was about ${n(g / r)} g dry / raw, so the plate can also take the dry weight.`
        : ` <span class="warn">Add the batch weights above to save it.</span>`);
}
document.addEventListener("change", e => { const m = e.target.id?.match(/^(f|s)Basis$/); if (m) cookExplain(m[1]); });
document.addEventListener("input", e => {
  if (/^(fCarbs|fBase|fCookRaw|fCookCooked)$/.test(e.target.id)) cookExplain("f");
  if (/^(sCarbs|sGrams|sCookRaw|sCookCooked)$/.test(e.target.id)) cookExplain("s");
});

function foodForm(f) {
  const v = f || { name: "", tags: [], carbs_per_100g: "", source_kind: "label", source_ref: "", notes: "", trust: "draft" };
  return `<form class="form" id="foodForm">
    ${f ? `<h2>${esc(f.name)}</h2>` : ""}
    ${f?.label_photo ? `<a class="labelthumb" href="${photoUrl(f.label_photo)}" target="_blank" rel="noopener"><img ${sized(f.label_photo, "72px")} alt="Nutrition label photo"><span class="meta">Label photo · open full size</span></a>` : ""}
    <label class="field"><span>Name</span><input id="fName" required maxlength="80" value="${esc(v.name)}"></label>
    <fieldset class="field tagpick"><legend>Tags (choose any)</legend><div>${S.tags.map(t =>
      `<label class="check"><input type="checkbox" name="fTag" value="${t.id}" ${v.tags.includes(t.id) ? "checked" : ""}>${esc(t.name)}</label>`).join("")}</div></fieldset>
    <fieldset class="field carbbase"><legend>Carbs, for the amount your source gives</legend>
      <div class="basebox"><input id="fCarbs" required type="number" step="0.1" min="0" inputmode="decimal" aria-label="Grams of carbs" value="${f ? f.serving_carbs ?? f.carbs_per_100g : ""}" placeholder="22">
        <span>g carbs per</span><input id="fBase" required type="number" step="0.1" min="0.1" inputmode="decimal" aria-label="Amount of food in grams" value="${f ? f.serving_grams ?? 100 : ""}" placeholder="30"><span>g of</span>${basisSelect(f, "f")}</div>
      ${cookRatio(f, "f")}
      <div class="basebox fiberbox"><span>including</span><input id="fFiber" type="number" step="0.1" min="0" inputmode="decimal" aria-label="Grams of fiber in that amount" value="${f ? f.serving_fiber ?? f.fiber_per_100g ?? "" : ""}" placeholder="–"><span>g fiber (optional, for reference)</span></div>
      <p class="scanmath" id="fMath"></p></fieldset>
    ${f ? "" : `<label class="field"><span>This serving as a number and unit (it becomes the first portion)</span>${labelInput("fPortion", "1 serving")}</label>
      ${noteField("fNote")}`}
    <div class="fieldrow">
      <label class="field"><span>Source</span><select id="fKind">${Object.entries(SOURCE).map(([k, l]) => `<option value="${k}" ${v.source_kind === k ? "selected" : ""}>${l}</option>`).join("")}</select></label></div>
    <label class="field"><span>Source reference (FDC number, product name, or who advised it)</span><input id="fRef" required maxlength="200" value="${esc(v.source_ref)}"></label>
    <fieldset class="field codebox"><legend>Barcode (optional)</legend>
      <div class="coderow"><input id="fCode" inputmode="numeric" maxlength="14" value="${esc(v.barcode || "")}" placeholder="None" aria-label="Barcode digits">
        <button type="button" class="btn small" data-act="code-scan">Scan</button>
        <label class="btn quiet small">Photo<input type="file" accept="image/*" data-codefile hidden></label></div>
      <div id="fScanBox"></div><p class="meta" id="fCodeNote" aria-live="polite"></p></fieldset>
    <label class="field"><span>Notes</span><textarea id="fNotes" maxlength="1000">${esc(v.notes)}</textarea></label>
    <label class="check"><input type="checkbox" id="fVer" ${v.trust === "parent-verified" ? "checked" : ""}>I checked the carbs and fiber against the source</label>
    <p class="err" id="fErr"></p>
    <div class="actions"><button class="btn primary">${f ? "Save food" : "Add food"}</button>
      <button type="button" class="btn quiet" data-act="${f ? "food-cancel" : "form-reset"}">Cancel</button></div>
    ${f ? `<div><button type="button" class="btn quiet small" data-act="del-food">Delete food</button></div>` : ""}
  </form>`;
}

const DISHES = { plate: "Plate", bowl: "Bowl", dressing: "Dressing container" };
const dishPick = (id, v) => `<label class="field"><span>Goes with</span><select id="${id}"><option value="">Any dish</option>${Object.entries(DISHES).map(([k, l]) =>
  `<option value="${k}" ${v === k ? "selected" : ""}>${l}</option>`).join("")}</select></label>`;
const refFor = dish => S.sizeRefs.find(r => r.container === dish);   // first reference for that dish (okf/domain/size-reference.md)
/* The portion another is estimated from: the serving first, then one with a styled photo, then any photo.
   Its styled photo is what gets sent (okf/features/photo-pipeline.md). */
const hasPhoto = x => x.photo.styled || x.photo.original;
const photoSource = (f, p) => f.portions.find(x => x.id !== p.id && x.grams === f.serving_grams && hasPhoto(x))
  || f.portions.find(x => x.id !== p.id && x.photo.styled) || f.portions.find(x => x.id !== p.id && x.photo.original);
function portionsEditor(f) {
  const gramsHead = f.basis && f.basis !== "as-sold" ? `Grams, ${STATE[f.basis]}` : "Grams";   // portions are in the food's own state (okf/domain/food.md)
  const rows = f.portions.map(p => {
    const img = p.photo.styled || p.photo.original;
    const status = p.photo.styled ? (p.photo.estimated ? `<span class="warn">Estimated photo</span>` : "Styled") : p.photo.original ? "Your photo" : "No photo";
    const sibling = photoSource(f, p);
    const busy = S.m.busy[p.id];
    const job = p.job && `<div class="jobbar" role="progressbar" aria-label="Making the photo"><i></i></div>
      <span class="meta">${{ estimate: "Making an estimated photo", generate: "Generating a photo" }[p.job.kind] || "Styling with Gemini"} · <span data-since="${esc(p.job.started)}">${sinceText(p.job.started)}</span></span>`;
    return `<tr data-pid="${p.id}">
      <td data-l="Portion">${labelInput("", p.label, "pLabel")}${portionAmount(p.label) ? "" : `<span class="warn small">Needs a number and unit</span>`}</td>
      <td data-l="${gramsHead}"><input class="pGrams" type="number" step="1" min="1" inputmode="decimal" value="${p.grams}" aria-label="${gramsHead}">${f.cook_ratio && f.basis !== "as-sold"
        ? `<span class="meta small">about ${fmtG(r1(f.basis === "raw" ? p.grams * f.cook_ratio : p.grams / f.cook_ratio))} ${f.basis === "raw" ? "cooked" : "dry / raw"}</span>` : ""}</td>
      <td class="c" data-l="Carbs" data-live>${p.carbs} g</td>
      <td data-l="Served in · size"><div class="servedin"><select class="pContainer" aria-label="Served in">${Object.entries(CONTAINERS).map(([k, l]) => `<option value="${k}" ${p.container === k ? "selected" : ""}>${l}</option>`).join("")}</select>
        <select class="pSizeRef" aria-label="Size reference"><option value="">No size reference</option>${S.sizeRefs.map(r =>
          `<option value="${r.id}" ${p.size_ref_id === r.id ? "selected" : ""}>Size: ${esc(r.name)} (${esc(r.measurement)})${r.container ? ` · ${DISHES[r.container].toLowerCase()}` : ""}</option>`).join("")}</select></div></td>
      <td data-l="Photo" class="${p.job ? "generating" : ""}">${img ? `<img ${sized(img, "72px")} alt="">` : ""}<span class="meta">${status}</span></td>
      <td><div class="photoacts ${busy ? "busy" : ""}">${job ? job : busy ? `<span class="meta">${busy}</span>` : `
        ${p.job_error ? `<p class="err">Last try failed: ${esc(p.job_error)}</p>` : ""}
        <label class="btn small">Upload photo<input type="file" accept="image/*" data-upload hidden></label>
        ${p.photo.original ? `<button class="btn small" data-pact="style">Style with Gemini</button>` : ""}
        ${!p.photo.original ? `<button class="btn small" data-pact="generate">Generate a photo</button>` : ""}
        ${!p.photo.original && sibling ? `<button class="btn small quiet" data-pact="estimate" data-from="${sibling.id}">Estimate from ${esc(sibling.label)}</button>` : ""}
        <button class="btn small quiet" data-pact="del" aria-label="Delete portion">Delete</button>`}</div></td></tr>
      <tr class="noterow" data-of="${p.id}"><td colspan="6"><label class="field"><span>Note for Gemini (optional)</span>
        <input class="pNote" maxlength="300" value="${esc(p.photo_note || "")}" placeholder="e.g. plain rice, no sauce, ignore the fork"></label></td></tr>
      ${p.photo.candidate ? `<tr data-of="${p.id}"><td colspan="6">${reviewPanel(f, p)}</td></tr>` : ""}`;
  }).join("");
  return `<div class="glab" style="margin-top:12px"><span class="label">Portions</span><span class="meta">${f.basis && f.basis !== "as-sold" ? `Portion weights are <b>${f.basis === "raw" ? "dry / raw, before cooking" : "cooked"}</b>, like the carbs. ` : ""}Carbs = grams × ${f.carbs_per_100g} ÷ 100, rounded. "Served in: Auto" lets Gemini match the dish in your photo.</span></div>
    <table class="portions"><thead><tr><th>Portion</th><th>${gramsHead}</th><th>Carbs</th><th>Served in · size</th><th>Photo</th><th></th></tr></thead><tbody>${rows}</tbody></table>
    ${quickAdd(f)}
    <form class="actions" id="addPortion" style="align-items:end">
      <label class="field"><span>New portion: number and unit</span>${labelInput("npLabel", "")}</label>
      <label class="field"><span>Grams weighed</span><input id="npGrams" type="number" min="1" step="1" inputmode="decimal" required></label>
      <button class="btn">Add portion</button><button type="button" class="btn quiet" data-act="form-reset">Cancel</button></form>
    <p class="err">${esc(S.m.err)}</p>`;
}

/* Portions as a multiple of a weighed one, the first by default (okf/domain/portion.md) */
const MULTS = [0.5, 1.5, 2];
const multText = m => ({ 0.5: "½", 1.5: "1½", 2.5: "2½" })[m] || String(+m.toFixed(2));
const multLabel = (m, p) => { const a = portionAmount(p.label), n = a && a.n * m;   // 1.5 × '4 Nuggets' = '6 Nuggets'
  return a ? `${fmtAmount(n)} ${unitFor(n, a.unit)}` : `${multText(m)} × ${p.label}`; };
const qaBase = f => f.portions.find(p => p.id === S.m.qaBase) || f.portions.find(p => p.grams === f.serving_grams) || f.portions[0];
function quickAdd(f) {
  if (!f.portions.length) return "";
  const base = qaBase(f);
  return `<form class="quickadd" id="quickAdd"><span class="label">Quick add</span>
    ${f.portions.length > 1 ? `<label class="field"><span>Multiple of</span><select id="qaBase">${f.portions.map(p =>
      `<option value="${p.id}" ${p === base ? "selected" : ""}>${esc(p.label)} (${p.grams} g)</option>`).join("")}</select></label>`
      : `<span class="meta">Multiples of ${esc(base.label)} (${base.grams} g)</span>`}
    <div class="qabtns">${MULTS.map(m => `<button type="button" class="btn small" data-mult="${m}">${multText(m)}× · ${+(base.grams * m).toFixed(1)} g</button>`).join("")}
      <span class="qaown"><input id="qaMult" type="number" min="0.1" max="10" step="0.1" inputmode="decimal" placeholder="3" aria-label="Your own multiple"><span>×</span>
      <button class="btn small">Add</button></span></div></form>`;
}
async function addMultiple(m) {
  const f = foodById(S.m.food), base = qaBase(f);
  if (!(m >= 0.1 && m <= 10)) { toast("Use a multiple from 0.1 to 10."); return; }
  const grams = Math.round(base.grams * m * 10) / 10;
  if (f.portions.some(p => p.grams === grams)) { toast(`There's already a ${grams} g portion.`); return; }
  await parentCall(`/api/foods/${f.id}/portions`, { method: "POST", body: { label: multLabel(m, base).slice(0, 40), grams, sort: f.portions.length,
    container: base.container, size_ref_id: base.size_ref_id, photo_note: base.photo_note || "" } });
  const added = foodById(f.id)?.portions.find(p => p.grams === grams);
  if (added && hasPhoto(base)) {   // start its photo from the serving's (okf/features/photo-pipeline.md)
    await parentCall(`/api/portions/${added.id}/estimate`, { method: "POST", body: { from_portion_id: base.id } }, added.id, "Starting…");
    toast(`Added ${multLabel(m, base)}, ${grams} g. Making its photo from ${base.label}…`); watchJobs();
  } else toast(`Added ${multLabel(m, base)}, ${grams} g`);
}

function reviewPanel(f, p) {
  if (p.photo.candidate_kind === "generated") return `<div class="review"><b>Check the new photo</b>
    <p class="meta">Gemini made this from the name and ${p.grams} g, with no photo of this food. Check it is the right food and looks like ${esc(p.label)}. It is labelled "Estimated photo" until you upload a real one.</p>
    <div class="cmp"><figure><img ${sized(p.photo.candidate, "(min-width: 1100px) 40vw, 90vw")} alt=""><figcaption>Generated · ${esc(p.label)}, ${p.grams} g</figcaption></figure></div>
    <div class="actions"><button class="btn primary small" data-pact="accept">Use this photo</button>
      <button class="btn small" data-pact="generate">Try again</button>
      <button class="btn small quiet" data-pact="discard">Discard</button></div></div>`;
  const ref = p.photo.candidate_estimated ? photoSource(f, p) : p;
  return `<div class="review"><b>Check the new photo</b>
    <p class="meta">${p.photo.candidate_estimated ? `Estimated from ${esc(ref?.label || "another portion")}. Gemini can get the amount wrong; it will be labelled "Estimated photo" until you upload a real one.` : "Gemini can change the amount or add things. Use it only if the plate matches your photo."}</p>
    <div class="cmp"><figure><img ${sized(p.photo.candidate_estimated ? ref?.photo.styled || ref?.photo.original : ref?.photo.original, "(min-width: 1100px) 40vw, 90vw")} alt=""><figcaption>${p.photo.candidate_estimated && ref?.photo.styled ? "Styled photo" : "Your photo"}${ref && ref !== p ? ` (${esc(ref.label)}, ${ref.grams} g)` : ` · ${p.grams} g`}</figcaption></figure>
      <figure><img ${sized(p.photo.candidate, "(min-width: 1100px) 40vw, 90vw")} alt=""><figcaption>${p.photo.candidate_estimated ? `Estimated · ${p.grams} g` : "Styled by Gemini"}</figcaption></figure></div>
    <div class="actions"><button class="btn primary small" data-pact="accept">Use this photo</button>
      <button class="btn small" data-pact="${p.photo.candidate_estimated ? "estimate" : "style"}" ${p.photo.candidate_estimated && ref ? `data-from="${ref.id}"` : ""}>Try again</button>
      <button class="btn small quiet" data-pact="discard">Discard</button>
      ${p.photo.original ? `<button class="btn small quiet" data-pact="use_original">Use my photo instead</button>` : ""}</div></div>`;
}

async function refreshFoods() {   // with unsaved changes in the food form, redraw only the list and portions around it
  await loadFoods();
  if (foodDirty && $("#foodForm") && foodById(S.m.food)) { if ($("#mRows")) $("#mRows").innerHTML = manageRows(); $("#portionsBox").innerHTML = portionsEditor(foodById(S.m.food)); }
  else renderManage();
  watchJobs();
}
async function parentCall(path, opts, pid, busyText) {
  S.m.err = "";
  if (pid) { S.m.busy[pid] = busyText; renderManage(); }
  try { await api(path, { ...opts, parent: true }); }
  catch (err) { if (err.status === 401) { pinStore.set(""); } S.m.err = err.message; toast(err.message); }
  finally { if (pid) delete S.m.busy[pid]; }
  await refreshFoods();
}

/* The food form; true when saved. 'Use this photo' calls it too, so typed changes aren't lost (okf/features/manage-foods.md) */
let foodDirty = false;   // the food form has changes not yet saved
async function saveFoodForm({ quiet = false } = {}) {
  const per100 = carbsPer100();   // worked out from "X g carbs per Y g" on save
  if (per100 == null) { $("#fErr").textContent = "Enter the carbs and the amount they're for, in grams (carbs can't be more than the amount)."; return false; }
  const isNew = S.m.food === "add", old = foodById(S.m.food), grams = parseFloat($("#fBase").value), carbs = parseFloat($("#fCarbs").value);
  // the serving is kept as typed (okf/domain/food.md); a per-100 g food left at 100 g stays per 100 g
  const fv = $("#fFiber").value === "" ? null : parseFloat($("#fFiber").value);   // fiber for the same amount (okf/domain/food.md)
  const serving = isNew || old?.serving_grams != null || grams !== 100 ? { serving_grams: grams, serving_carbs: carbs, serving_fiber: fv } : { carbs_per_100g: per100, fiber_per_100g: fv };
  const body = { name: $("#fName").value, tags: [...document.querySelectorAll("input[name=fTag]:checked")].map(x => +x.value), ...serving,
    source_kind: $("#fKind").value, source_ref: $("#fRef").value, notes: $("#fNotes").value, verified: $("#fVer").checked, ...cookBody("f"),
    barcode: $("#fCode").value.replace(/\D/g, "") || null };
  if (body.barcode && !/^\d{8,14}$/.test(body.barcode)) { $("#fErr").textContent = "A barcode has 8 to 14 digits."; return false; }
  try {
    const f = await api(isNew ? "/api/foods" : `/api/foods/${S.m.food}`, { method: isNew ? "POST" : "PUT", body, parent: true });
    if (isNew)   // the serving is the first, default portion
      await api(`/api/foods/${f.id}/portions`, { method: "POST", parent: true, body: { label: $("#fPortion").value.trim() || "1 serving", grams, sort: 0, photo_note: $("#fNote").value } });
    S.m.food = f.id; foodDirty = false;
    if (!quiet) toast(isNew ? `Food added with its serving: ${carbs} g carbs per ${grams} g. Add more portions as multiples below.` : "Food saved");
    if (isNew) { await loadFoods(); mNav(); } else if (!quiet) await refreshFoods();
    return true;
  } catch (err) { $("#fErr").textContent = err.message; return false; }
}
/* Portion names, grams and notes still being typed when a photo is accepted */
async function savePortionEdits() {
  const f = foodById(S.m.food); if (!f) return true;
  for (const p of f.portions) {
    const tr = $(`tr[data-pid="${p.id}"]`), note = $(`.noterow[data-of="${p.id}"] .pNote`); if (!tr) continue;
    const label = tr.querySelector(".pLabel").value.trim(), grams = parseFloat(tr.querySelector(".pGrams").value), photo_note = note ? note.value.trim() : p.photo_note || "";
    if (label === p.label && grams === p.grams && photo_note === (p.photo_note || "")) continue;
    if (!(grams > 0) || !label) { toast("A portion needs a name and grams above 0."); return false; }
    try { await api(`/api/portions/${p.id}`, { method: "PUT", parent: true, body: { label, grams, sort: p.sort, container: p.container, size_ref_id: p.size_ref_id, photo_note } }); }
    catch (err) { toast(err.message); return false; }
  }
  return true;
}
async function acceptPhoto(pid, action) {
  if (foodDirty && $("#foodForm") && !(await saveFoodForm({ quiet: true }))) {   // the photo waits until the food can be saved
    $("#fErr").scrollIntoView({ block: "center", behavior: "smooth" }); toast("The food's changes couldn't be saved, so the photo is still waiting. See the note in the form.");
    return;
  }
  if (!(await savePortionEdits())) return;
  await parentCall(`/api/portions/${pid}/review`, { method: "POST", body: { action } });
  if (!S.m.err) toast(action === "accept" ? "Photo accepted and changes saved" : "Using your photo; changes saved");
}
const mSubmit = async e => {
  e.preventDefault();
  const id = e.target.id;
  if (id === "pinCreate") {
    const a = $("#pin1").value, b = $("#pin2").value;
    if (!/^\d{4,8}$/.test(a)) { $("#pinErr").textContent = "Use 4 to 8 digits."; return; }
    if (a !== b) { $("#pinErr").textContent = "The two PINs don't match."; return; }
    try { await api("/api/pin", { method: "POST", body: { pin: a } }); pinStore.set(a); S.session.pin_set = true; mNav({ replace: true }); }
    catch (err) { $("#pinErr").textContent = err.message; }
  } else if (id === "pinEnter") {
    pinStore.set($("#pin").value);
    try { await api("/api/pin/check", { method: "POST", parent: true }); mNav({ replace: true }); }
    catch (err) { pinStore.set(""); $("#pinErr").textContent = err.message; }
  } else if (id === "foodForm") {
    await saveFoodForm();
  } else if (id === "batchCode") {
    addBatchCode($("#bCode").value); $("#bCode").value = "";
  } else if (id === "quickAdd") {
    await addMultiple(parseFloat($("#qaMult").value));
  } else if (id === "addPortion") {
    const f = foodById(S.m.food);
    await parentCall(`/api/foods/${f.id}/portions`, { method: "POST", body: { label: $("#npLabel").value, grams: parseFloat($("#npGrams").value), sort: f.portions.length } });
  } else if (id === "usdaForm") {
    await saveUsda();
  } else if (id === "lkCodeForm") {
    const code = $("#lkCode").value.replace(/\D/g, "");
    if (code.length < 8) { S.m.look.err = "A barcode has 8 to 14 digits."; refreshLookup(); return; }
    openLookup("off", code);
  } else if (id === "tpForm") {   // the login is checked with Tidepool before it's saved
    const btn = e.target.querySelector(".btn.primary"); btn.disabled = true;
    try {
      await api("/api/tidepool", { method: "PUT", parent: true, body: { server: $("[data-tpserver].on")?.dataset.tpserver || "test",
        email: $("#tpEmail").value.trim(), password: $("#tpPw").value, target: $("#tpTarget").value.trim(), send_from: $("#tpFrom").value,
        carbs: $("#tpCarbs").checked, bg: $("#tpBg").checked, insulin: $("#tpIns").checked, basal_hours: +$("#tpHours").value || 24 } });
      toast("Tidepool connected. Sending within a minute."); renderTidepool();
    } catch (err) { renderTidepool(err.message); }
  } else if (id === "approveDevice") {
    try { await api("/api/accounts/approve-device", { method: "POST", parent: true, body: { code: $("#devCode").value } }); e.target.reset(); S.accounts = null; renderAccounts(); toast("Approved. The other device signs in within a few seconds."); }
    catch (err) { toast(err.message); }
  } else if (id === "accountsForm") {
    try { S.accounts = await api("/api/accounts", { method: "PUT", parent: true, body: { emails: $("#accEmails").value.split(/[\s,;]+/).filter(Boolean) } });
      renderAccounts(); toast("Family accounts saved"); } catch (err) { toast(err.message); }
  } else if (id === "doseForm") {
    try { const d = await api("/api/dose-settings", { method: "PUT", parent: true, body: doseCollect() });
      S.doseEdit = d.settings; S.doseUpdated = d.updated; $("#doseBox").innerHTML = doseForm(); toast("Insulin settings saved"); }
    catch (err) { toast(err.message); }
  } else if (id === "offContact") {
    try { S.settings = await api("/api/settings", { method: "PUT", parent: true, body: { off_contact: $("#offContactEmail").value.trim() } }); toast("Contact saved"); }
    catch (err) { toast(err.message); }
  } else if (id === "scanForm") {
    await saveScanned();
  } else if (id === "refAdd") {
    const form = new FormData(); form.append("name", $("#raName").value); form.append("measurement", $("#raMeas").value); form.append("container", $("#raDish").value); form.append("file", $("#raFile").files[0]);
    const btn = e.target.querySelector("button"); btn.disabled = true;
    try { S.style = await api("/api/size-refs", { method: "POST", form, parent: true }); S.sizeRefs = S.style.size_refs; renderStyle(); toast("Size reference added"); }
    catch (err) { toast(err.message); btn.disabled = false; }
  } else if (id === "refEdit") {
    try { S.style = await api(`/api/size-refs/${e.target.dataset.rid}`, { method: "PUT", parent: true, body: { name: $("#reName").value, measurement: $("#reMeas").value, container: $("#reDish").value || null } });
      S.sizeRefs = S.style.size_refs; S.editRef = null; renderStyle(); toast("Size reference saved"); }
    catch (err) { toast(err.message); }
  } else if (id === "styleForm") {
    try { S.style = await api("/api/style", { method: "PUT", parent: true, body: { prompt: $("#stylePrompt").value } }); renderStyle(); toast("Style saved"); }
    catch (err) { toast(err.message); }
  } else if (id === "tagAdd") {
    try { S.tags = await api("/api/tags", { method: "POST", parent: true, body: { name: $("#tagNew").value } }); store.set("tags", S.tags); renderTags(); }
    catch (err) { $("#tagErr").textContent = err.message; }
  } else if (id === "nsForm") {
    const btn = e.target.querySelector("button"); btn.disabled = true; $("#nsErr").textContent = "";
    try { const r = await api("/api/nightscout", { method: "POST", parent: true, body: { url: $("#nsUrl").value.trim(), token: $("#nsToken").value.trim() } });
      toast(`Connected. Latest reading ${r.latest.sgv} mg/dL.`); S.session.glucose = true; renderNightscout(); }
    catch (err) { $("#nsErr").textContent = err.message; btn.disabled = false; }
  } else if (id === "tgForm") {
    try { await api("/api/targets", { method: "PUT", parent: true, body: { low: +$("#tgLow").value, high: +$("#tgHigh").value } }); toast("Target range saved"); S.session.targets = [+$("#tgLow").value, +$("#tgHigh").value]; }
    catch (err) { toast(err.message); }
  } else if (id === "pinChange") {
    try { await api("/api/pin", { method: "POST", body: { pin: $("#newPin").value, old_pin: $("#oldPin").value } }); pinStore.set($("#newPin").value); toast("PIN changed"); e.target.reset(); }
    catch (err) { toast(err.message); }
  }
};

let confirmFood = 0;
const mClick = async e => {
  const t = e.target.closest("[data-mtab],[data-mfood],[data-addtab],[data-lk],[data-pact],[data-act],[data-tact],[data-mult],[data-quality],[data-bact],[data-pushdel],[data-tpserver]"); if (!t) return;
  if (t.dataset.addtab || t.dataset.mfood || t.dataset.mtab) S.m.look.scanning = false;   // the camera closes when you move away
  if (t.dataset.mtab) { if (S.m.tab !== t.dataset.mtab) { S.m.tab = t.dataset.mtab; mNav(); } return; }
  if (t.dataset.lk) { const [src, ...id] = t.dataset.lk.split(":"); openLookup(src, id.join(":")); return; }
  if (t.dataset.addtab) {   // leaving a check screen for another tab starts that tab fresh
    if (S.m.scan && t.dataset.addtab !== "lookup") S.m.scan = null;
    if (S.m.addTab !== t.dataset.addtab || S.m.scan) { S.m.addTab = t.dataset.addtab; mNav(); } return;
  }
  if (t.dataset.mfood) { if (S.m.food !== t.dataset.mfood) { S.m.food = t.dataset.mfood; S.m.err = ""; S.m.scan = null; S.m.review = null; mNav(); } return; }
  if (t.dataset.mult) { addMultiple(+t.dataset.mult); return; }
  if (t.dataset.bact) { await batchAct(t); return; }
  if (t.dataset.act === "fib-look") { fiberLook(S.foods.filter(f => f.fiber_lookup && !fib()[f.id]).map(f => f.id)); return; }
  if (t.dataset.act === "fib-retry") { fiberLook([t.dataset.fid]); return; }
  if (t.dataset.act === "fib-save") { t.disabled = true; await fiberSave(); return; }
  if (t.dataset.quality) {
    try { S.style = await api("/api/style/quality", { method: "PUT", parent: true, body: { quality: t.dataset.quality } }); renderStyle(); toast("Photo speed saved"); }
    catch (err) { toast(err.message); }
    return;
  }
  if (t.dataset.act === "scan-again") { S.m.scan = null; mNav(); return; }
  if (t.dataset.act === "check-cancel") { mCancel(() => { S.m.scan = null; }); return; }
  if (t.dataset.act === "m-list") { S.m.food = null; S.m.scan = null; S.m.review = null; mNav(); return; }
  if (t.dataset.act === "food-cancel") { mCancel(() => { S.m.food = null; }); return; }
  if (t.dataset.act === "form-reset") { t.closest("form").reset(); scanMath(); return; }
  if (t.dataset.act === "dose-add" || t.dataset.act === "dose-rm") {
    const d = doseCollect(), k = t.closest(".doseset").dataset.k;
    if (t.dataset.act === "dose-add") d[k].push({ start: "", value: "" }); else d[k].splice(+t.dataset.i, 1);
    S.doseEdit = d; $("#doseBox").innerHTML = doseForm(); return;
  }
  if (t.dataset.act === "lk-everywhere") { S.m.look.everywhere = true; lookupSearch(S.m.look.q); return; }
  if (t.dataset.act === "sign-out") { await api("/api/auth/logout", { method: "POST" }).catch(() => { }); location.reload(); return; }
  if (t.dataset.tpserver) {
    t.parentElement.querySelectorAll("button").forEach(b => { b.classList.toggle("on", b === t); b.setAttribute("aria-pressed", b === t); }); return;
  }
  if (["tp-sync", "tp-off", "tp-remove"].includes(t.dataset.act)) {
    if (t.dataset.act === "tp-remove" && Date.now() - confirmTpRemove > 4000) { confirmTpRemove = Date.now(); t.textContent = "Tap again to remove"; return; }
    t.disabled = true;
    try {
      if (t.dataset.act === "tp-sync") { const r = await api("/api/tidepool/sync", { method: "POST", parent: true }); toast(`Sent ${r.sent}, removed ${r.removed}`); }
      else if (t.dataset.act === "tp-off") { await api("/api/tidepool/off", { method: "POST", parent: true }); toast("Tidepool sending off"); }
      else { confirmTpRemove = 0; await api("/api/tidepool/data", { method: "DELETE", parent: true }); toast("Removed what Kitchen Carbs sent to Tidepool"); }
      renderTidepool();
    } catch (err) { renderTidepool(err.message); }
    return;
  }
  if (["push-on", "push-off", "push-test"].includes(t.dataset.act) || t.dataset.pushdel) {
    t.disabled = true;
    try {
      if (t.dataset.act === "push-on") await pushOn();
      else if (t.dataset.act === "push-test") { await api("/api/push/test", { method: "POST", body: { endpoint: store.get("push", "") } }); toast("Test sent"); }
      else if (t.dataset.act === "push-off") {
        const sub = await (await pushReg())?.pushManager.getSubscription();
        const endpoint = sub?.endpoint || store.get("push", "");
        await sub?.unsubscribe(); if (endpoint) await api("/api/push/unsubscribe", { method: "POST", body: { endpoint } });
        store.set("push", ""); toast("Notifications off for this device");
      } else await api(`/api/push/devices/${t.dataset.pushdel}`, { method: "DELETE", parent: true });
      renderPush();
    } catch (err) { renderPush(err.message); }
    return;
  }
  if (t.dataset.act === "scale-raw") {   // okf/features/kitchen-scale.md: read an unknown scale's format
    const log = $("#rawLog"), lines = [], add = l => { lines.push(l); if (lines.length > 300) lines.shift(); log.textContent = lines.join("\n"); log.scrollTop = log.scrollHeight; };
    log.hidden = false; S.rawStop?.();
    try { S.rawStop = await Scale.inspect(add); } catch (err) { if (err.name !== "NotFoundError") add(`Error: ${err.message}`); }
    return;
  }
  if (t.dataset.act === "sign-out-others") {
    try { const r = await api("/api/accounts/sign-out-others", { method: "POST", parent: true }); S.accounts = null; renderAccounts(); toast(`${r.signed_out} other device${r.signed_out === 1 ? "" : "s"} signed out`); }
    catch (err) { toast(err.message); }
    return;
  }
  if (t.dataset.act === "quick-scan") { Object.assign(S.m, { food: "add", addTab: "lookup", scan: null, review: null }); mNav(); S.m.look.scanning = true; renderManage(); return; }
  if (t.dataset.act === "code-scan") {   // the food form's own scanner (okf/features/manage-foods.md)
    $("#fScanBox").innerHTML = `<div class="scanner" id="scanner"><video id="scanVideo" playsinline muted></video><div class="scanbox"></div>
      <p class="scanmsg" id="scanMsg">Starting the camera…</p></div><div><button type="button" class="btn quiet small" data-act="code-stop">Stop scanning</button></div>`;
    startScanner(); return;
  }
  if (t.dataset.act === "code-stop") { stopScanner(); $("#fScanBox").innerHTML = ""; return; }
  if (t.dataset.act === "scan-start") { S.m.look.scanning = true; renderManage(); return; }
  if (t.dataset.act === "scan-stop") { S.m.look.scanning = false; renderManage(); return; }
  if (t.dataset.act === "lock") { pinStore.set(""); mNav({ replace: true }); return; }
  if (t.dataset.act === "pin-cancel") { location.hash = "foods"; return; }
  if (t.dataset.act === "ref-edit") { S.editRef = +t.dataset.rid; renderStyle(); return; }
  if (t.dataset.act === "ref-edit-cancel") { S.editRef = null; renderStyle(); return; }
  if (t.dataset.act === "ref-del") {
    const rid = +t.dataset.rid;
    if (S.delRef?.id !== rid || Date.now() - S.delRef.at > 4000) { S.delRef = { id: rid, at: Date.now() }; renderStyle(); return; }
    try { S.style = await api(`/api/size-refs/${rid}`, { method: "DELETE", parent: true }); S.sizeRefs = S.style.size_refs; S.delRef = null; await loadFoods(); renderStyle(); toast("Size reference removed"); }
    catch (err) { toast(err.message); }
    return;
  }
  if (t.dataset.act === "style-reset") { $("#stylePrompt").value = S.style.default_prompt; return; }
  if (t.dataset.act === "base-clear") {
    try { S.style = await api(`/api/style/base/${t.dataset.kind}`, { method: "DELETE", parent: true }); renderStyle(); } catch (err) { toast(err.message); }
    return;
  }
  if (t.dataset.tact === "del") {
    const tid = +t.closest("[data-tid]").dataset.tid;
    if (confirmTag.id !== tid || Date.now() - confirmTag.at > 4000) { confirmTag = { id: tid, at: Date.now() }; renderTags(); return; }
    try { S.tags = await api(`/api/tags/${tid}`, { method: "DELETE", parent: true }); store.set("tags", S.tags); await loadFoods(); } catch (err) { toast(err.message); }
    confirmTag = { id: null, at: 0 }; renderTags(); return;
  }
  if (t.dataset.act === "ns-off") { await api("/api/nightscout", { method: "DELETE", parent: true }).catch(err => toast(err.message)); renderNightscout(); return; }
  if (t.dataset.act === "del-food") {
    if (Date.now() - confirmFood > 4000) { confirmFood = Date.now(); t.textContent = "Tap again to delete. Logged meals are kept."; return; }
    await parentCall(`/api/foods/${S.m.food}`, { method: "DELETE" }); S.m.food = null; mNav({ replace: true }); return;
  }
  const pid = +t.closest("[data-pid]")?.dataset.pid || +t.closest("[data-of]")?.dataset.of;
  const a = t.dataset.pact;
  if (a === "style") parentCall(`/api/portions/${pid}/style`, { method: "POST" }, pid, "Starting…");
  else if (a === "generate") parentCall(`/api/portions/${pid}/generate`, { method: "POST" }, pid, "Starting…");
  else if (a === "estimate") parentCall(`/api/portions/${pid}/estimate`, { method: "POST", body: { from_portion_id: +t.dataset.from } }, pid, "Starting…");
  else if (a === "accept" || a === "use_original") acceptPhoto(pid, a);
  else if (a === "discard") parentCall(`/api/portions/${pid}/review`, { method: "POST", body: { action: a } });
  else if (a === "del") parentCall(`/api/portions/${pid}`, { method: "DELETE" });
};

const mChange = async e => {
  if (e.target.closest("#foodForm")) foodDirty = true;
  if (e.target.id === "pastEdits") {   // okf/rules/same-day-edits.md
    try { S.settings = await api("/api/settings/past-edits", { method: "PUT", parent: true, body: { allowed: e.target.checked } });
      toast(S.settings.past_edits ? "Earlier days can be changed" : "Earlier days are read-only"); }
    catch (err) { e.target.checked = !e.target.checked; toast(err.message); }
    return;
  }
  if (e.target.matches("[data-labelfile]") && e.target.files[0]) { readLabel(e.target.files[0]); return; }
  if (e.target.matches("#sConfServ,#sConfCarb")) { scanConfirms(); return; }
  if (e.target.matches("#uConf")) { usdaConfirm(); return; }
  if (e.target.matches("[data-codefile]") && e.target.files[0]) {
    const form = new FormData(); form.append("file", e.target.files[0]); e.target.value = "";
    $("#fCodeNote").textContent = "Reading the barcode…";
    try { newBarcode((await api("/api/lookup/barcode", { method: "POST", form, parent: true })).code); }
    catch (err) { $("#fCodeNote").textContent = err.message; }
    return;
  }
  if (e.target.matches("[data-barcodefile]") && e.target.files[0]) {
    const form = new FormData(); form.append("file", e.target.files[0]);
    S.m.look.busy = "Reading the barcode…"; S.m.look.err = ""; refreshLookup();
    try { const { code } = await api("/api/lookup/barcode", { method: "POST", form, parent: true }); openLookup("off", code); }
    catch (err) { S.m.look.busy = false; S.m.look.err = err.message; refreshLookup(); }
    return;
  }
  if (e.target.matches("[data-basefile]") && e.target.files[0]) {
    const form = new FormData(); form.append("file", e.target.files[0]);
    try { S.style = await api(`/api/style/base/${e.target.dataset.basefile}`, { method: "POST", form, parent: true }); renderStyle(); toast("Base photo saved"); }
    catch (err) { toast(err.message); }
    return;
  }
  if (e.target.matches(".pContainer")) {
    const f = foodById(S.m.food), p = f.portions.find(x => x.id === +e.target.closest("tr[data-pid]").dataset.pid);
    const dish = e.target.value, cur = S.sizeRefs.find(r => r.id === p.size_ref_id);
    // no reference yet, or one for another dish: take the one that goes with this dish
    const sref = (!cur || (cur.container && cur.container !== dish)) && refFor(dish) ? refFor(dish).id : p.size_ref_id;
    parentCall(`/api/portions/${p.id}`, { method: "PUT", body: { label: p.label, grams: p.grams, sort: p.sort, container: dish, size_ref_id: sref } });
    return;
  }
  if (e.target.id === "qaBase") { S.m.qaBase = +e.target.value; $("#portionsBox").innerHTML = portionsEditor(foodById(S.m.food)); return; }
  if (batchEdit(e)) return;
  const fr = e.target.closest(".fiblist li[data-fid]");
  if (fr) {   // a changed number clears its tick
    const r = fib()[fr.dataset.fid];
    if (e.target.matches(".fibVal")) { r.fiber = e.target.value === "" ? null : +e.target.value; r.conf = false; }
    if (e.target.matches(".fibConf")) r.conf = e.target.checked;
    refreshFiber(); return;
  }
  if (e.target.id === "offCountry") {
    try { S.settings = await api("/api/settings/country", { method: "PUT", parent: true, body: { country: e.target.value } });
      S.m.look.res = null; toast(`Packaged search: ${S.settings.countries[e.target.value]}`); } catch (err) { toast(err.message); }
    return;
  }
  if (e.target.matches(".pSizeRef")) {
    const f = foodById(S.m.food), p = f.portions.find(x => x.id === +e.target.closest("tr[data-pid]").dataset.pid);
    parentCall(`/api/portions/${p.id}`, { method: "PUT", body: { label: p.label, grams: p.grams, sort: p.sort, container: p.container, size_ref_id: e.target.value ? +e.target.value : null } });
    return;
  }
  if (e.target.matches(".tName")) {
    const tid = +e.target.closest("[data-tid]").dataset.tid, name = e.target.value.trim(); if (!name) return;
    try { S.tags = await api(`/api/tags/${tid}`, { method: "PUT", parent: true, body: { name } }); store.set("tags", S.tags); toast("Tag renamed"); }
    catch (err) { toast(err.message); renderTags(); }
    return;
  }
  if (e.target.matches(".pNote")) {   // sent with every photo made for this portion (okf/domain/photo-style.md)
    const p = foodById(S.m.food).portions.find(x => x.id === +e.target.closest("[data-of]").dataset.of);
    try { await api(`/api/portions/${p.id}`, { method: "PUT", parent: true, body: { label: p.label, grams: p.grams, sort: p.sort,
      container: p.container, size_ref_id: p.size_ref_id, photo_note: e.target.value } }); p.photo_note = e.target.value.trim(); toast("Note saved"); }
    catch (err) { toast(err.message); }
    return;
  }
  const tr = e.target.closest("tr[data-pid]");
  if (e.target.matches("[data-upload]") && e.target.files[0]) {
    const form = new FormData(); form.append("file", e.target.files[0]);
    parentCall(`/api/portions/${tr.dataset.pid}/original`, { method: "POST", form }, +tr.dataset.pid, "Uploading…");
  } else if (tr && e.target.matches(".pLabel,.pGrams")) {
    const f = foodById(S.m.food), p = f.portions.find(x => x.id === +tr.dataset.pid);
    const grams = parseFloat(tr.querySelector(".pGrams").value), label = tr.querySelector(".pLabel").value.trim();
    if (!(grams > 0) || !label) { toast("A portion needs a name and grams above 0."); return; }
    parentCall(`/api/portions/${p.id}`, { method: "PUT", body: { label, grams, sort: p.sort, container: p.container, size_ref_id: p.size_ref_id } });
  }
};
const mInput = e => {
  if (e.target.closest("#foodForm")) foodDirty = true;
  if (e.target.id === "lkQ") { lookupSearch(e.target.value); return; }
  if (e.target.matches("#fCarbs,#fBase")) { foodMath(); return; }
  if (e.target.id === "uCp") { $("#uConf").checked = false; usdaConfirm(); return; }
  if (e.target.matches("#sGrams,#sCarbs,#sFiber")) {   // a changed number needs confirming again (fiber goes with the carbs tick)
    $(e.target.id === "sGrams" ? "#sConfServ" : "#sConfCarb").checked = false;
    scanMath();
  }
  const tr = e.target.closest("tr[data-pid]");
  if (tr && e.target.matches(".pGrams")) {
    const f = foodById(S.m.food), g = parseFloat(e.target.value);
    tr.querySelector("[data-live]").textContent = g > 0 ? `${whole(exact(g, f.carbs_per_100g))} g` : "–";
  }
};
/* ---------- add a food from a search with no match, in a modal over the foods (okf/features/browse-foods.md) ---------- */
const dlg = $("#addDialog");
function openAddDialog(q) {
  S.dlg = { q }; S.m.scan = null; dlg.showModal(); dlgFind();
}
function dlgDraw(body) {
  dlg.innerHTML = `<div class="dlghead"><b>Add “${esc(S.dlg.q)}”</b><button class="rm" data-dlg="close" aria-label="Close">×</button></div><div class="dlgbody">${body}</div>`;
}
async function dlgFind() {
  if (!pinStore.get()) return dlgDraw(`<form class="form" id="dlgPin"><p class="meta">Adding a food needs the parent PIN.</p>
    <input id="dlgPinIn" inputmode="numeric" type="password" aria-label="Parent PIN" autocomplete="current-password" autofocus>
    <p class="err" id="dlgPinErr">${esc(S.dlg.pinErr || "")}</p><div class="actions"><button class="btn primary">Unlock</button></div></form>`);
  dlgDraw(`<p class="meta">Searching for “${esc(S.dlg.q)}”…</p>`);
  try { S.dlg.res = await api("/api/lookup/search?q=" + encodeURIComponent(S.dlg.q), { parent: true }); }
  catch (err) { if (err.status === 401) { pinStore.set(""); S.dlg.pinErr = err.message; return dlgFind(); } return dlgDraw(`<p class="err">${esc(err.message)}</p>`); }
  if (!S.dlg) return;
  const all = [...S.dlg.res.fatsecret, ...S.dlg.res.off];   // the same order as Manage's lookup: FatSecret, then packaged
  S.dlg.all = all;
  if (!all.length) return dlgDraw(`<p>Nothing found for “${esc(S.dlg.q)}”.</p><p class="meta">Try fewer words, or add it in Manage → Add a food.</p>`);
  dlgOpen(all[0]);
}
async function dlgOpen(r) {
  S.dlg.pick = r; S.dlg.others = false;
  dlgDraw(`<p class="meta">Getting the details for ${esc(r.name)}…</p>`);
  try {
    const d = await api(`/api/lookup/${r.source === "fatsecret" ? "fatsecret" : "off"}/${encodeURIComponent(r.id)}`, { parent: true });
    if (!S.dlg) return;
    S.m.scan = { stage: "review", ...d }; dlgReview();
  } catch (err) { dlgDraw(`<p class="err">${esc(err.message)}</p>${dlgOthers()}`); }
}
function dlgOthers() {
  const rest = S.dlg.all.filter(x => x !== S.dlg.pick);
  return rest.length ? `<div class="dlgothers"><span class="label">Other results</span>${rest.slice(0, 8).map((x, i) => `<button class="row lkrow" data-dlgpick="${S.dlg.all.indexOf(x)}">
    ${x.image ? `<img src="${esc(x.image)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : ""}<span class="t"><b>${esc(x.name)}</b>${x.brand ? `<span class="brand">${esc(x.brand)}</span>` : ""}
    <span>${x.source === "fatsecret" ? "FatSecret" : "Packaged"}${x.carbs_per_100g != null ? ` · ${x.carbs_per_100g} g carbs per 100 g` : ""}</span></span></button>`).join("")}</div>` : "";
}
function dlgReview() {
  const r = S.dlg.pick;
  dlgDraw(`<p class="meta dlgtop">Top result: <b>${esc(r.name)}</b>${r.brand ? ` · ${esc(r.brand)}` : ""}.
      <button class="linkbtn" data-dlg="others">${S.dlg.others ? "Hide other results" : "Not this one?"}</button></p>
    ${S.dlg.others ? dlgOthers() : ""}${scanPanel()}`);
  scanMath();
}
function closeAddDialog() { if (dlg.open) dlg.close(); }
dlg.addEventListener("close", () => { S.dlg = null; S.m.scan = null; dlg.innerHTML = ""; });
dlg.addEventListener("click", e => {   // the modal's own buttons, before Manage's shared handlers
  const t = e.target.closest("[data-dlg],[data-dlgpick],[data-act=check-cancel],[data-act=scan-again]");
  if (e.target === dlg) { closeAddDialog(); return; }   // a tap on the backdrop
  if (!t) return;
  e.stopImmediatePropagation();
  if (t.dataset.dlgpick) dlgOpen(S.dlg.all[+t.dataset.dlgpick]);
  else if (t.dataset.dlg === "others") { S.dlg.others = !S.dlg.others; dlgReview(); }
  else closeAddDialog();
});
dlg.addEventListener("submit", async e => {
  if (e.target.id !== "dlgPin") return;
  e.preventDefault(); e.stopImmediatePropagation();
  pinStore.set($("#dlgPinIn").value);
  try { await api("/api/pin/check", { method: "POST", parent: true }); S.dlg.pinErr = ""; }
  catch (err) { pinStore.set(""); S.dlg.pinErr = err.message; }
  dlgFind();
});
async function dlgSaved(f) {   // the new food shows under the search the parent typed
  closeAddDialog(); toast(`${f.name} added`); await loadFoods(); renderFoods(); watchJobs();
}
// Manage's handlers serve the add-food modal on the Foods page too (okf/features/browse-foods.md)
for (const el of [$("#v-manage"), $("#addDialog")]) {
  el.addEventListener("submit", mSubmit); el.addEventListener("click", mClick); el.addEventListener("change", mChange); el.addEventListener("input", mInput);
}

/* ---------- look up a food (okf/features/food-lookup.md) ---------- */
/* Add a food: three tabs in the middle panel; check screens (barcode, FatSecret, label photo) open inside Look up. */
function addPanel() {
  const tab = S.m.addTab, sc = S.m.scan, open = sc && sc.stage !== "pick" && tab === "lookup";
  const tabs = [["lookup", "Look up"], ["batch", "Scan several"], ["new", "Type it in"]];
  return `<div class="addtabs" role="tablist">${tabs.map(([k, l]) =>
      `<button role="tab" aria-selected="${k === tab}" class="${k === tab ? "on" : ""}" data-addtab="${k}">${l}</button>`).join("")}</div>
    <div class="addbody">${tab === "lookup" ? (open ? scanPanel() : lookupPanel()) : tab === "batch" ? batchPanel() : foodForm(null)}</div>`;
}
function lookupPanel() {
  return `<div class="form">
    ${S.m.look.scanning
      ? `<div class="scanner" id="scanner"><video id="scanVideo" playsinline muted></video><div class="scanbox"></div>
          <p class="scanmsg" id="scanMsg">Starting the camera…</p></div>
         <div><button type="button" class="btn quiet small" data-act="scan-stop">Stop scanning</button></div>`
      : `<div class="actions"><button type="button" class="btn primary" data-act="scan-start">Scan a barcode</button>
          <label class="btn">Photograph the nutrition label<input type="file" accept="image/*" data-labelfile hidden></label></div>
         <p class="meta">For the label: straight on, good light, the Nutrition Facts panel filling the frame. You check every number before it's saved.</p>
         ${S.m.scan?.err ? `<p class="err">${esc(S.m.scan.err)}</p>` : ""}`}
    <label class="search lksearch"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>
      <input id="lkQ" type="search" placeholder="Or search by name, e.g. rice cooked or cheerios" value="${esc(S.m.look.q)}" autocomplete="off"></label>
    <div class="actions" style="align-items:end">
      <label class="btn quiet small">Photograph a barcode instead<input type="file" accept="image/*" data-barcodefile hidden></label>
      <form class="cmtform" id="lkCodeForm"><input id="lkCode" inputmode="numeric" placeholder="or type the barcode digits" aria-label="Barcode digits"><button class="btn small">Look up</button></form></div>
    <div id="lkResults">${lookupResults()}</div>
  </div>`;
}
function lookupResults() {
  const L = S.m.look, res = L.res;
  const group = (title, rows, empty) => `<div class="glab"><span class="label">${title}</span></div>${rows.length ? rows.map(r => `
    <button class="row lkrow" data-lk="${r.source}:${esc(r.id)}">${r.source === "off" ? (r.image ? `<img src="${esc(r.image)}" alt="Package of ${esc(r.name)}" loading="lazy" referrerpolicy="no-referrer">` : `<span class="noimg">No photo</span>`) : ""}
      <span class="t"><b>${esc(r.name)}</b>${r.brand ? `<span class="brand">${esc(r.brand)}</span>` : ""}
      <span>${r.source === "fatsecret" ? (r.carbs_per_100g != null ? `${r.carbs_per_100g} g carbs per 100 g` : r.serving ? esc(r.serving) : "Carbs on the next screen")
        : r.carbs_per_100g == null ? `<span class="warn">Carbs not listed: you'll enter them from the package</span>` : `${r.carbs_per_100g} g carbs per 100 g`}${r.source === "off" && r.serving ? ` · serving ${esc(r.serving)}` : ""}${r.source === "fatsecret" ? (r.kind && r.kind !== "Generic" ? ` · ${esc(r.kind)}` : "") : ` · ${esc(r.id)}`}</span></span></button>`).join("")
    : `<p class="meta">${empty}</p>`}`;
  return `${L.err ? `<p class="err">${esc(L.err)}</p>` : ""}${L.busy ? `<p class="meta">${esc(L.busy)}</p>` : ""}
    ${res ? `${res.errors.map(e => `<p class="err">${esc(e)}</p>`).join("")}
      ${group("Foods · FatSecret", res.fatsecret, "No FatSecret match. Try fewer words, e.g. “rice cooked”.")}
      <p class="meta"><a href="https://www.fatsecret.com" target="_blank" rel="noopener">Powered by FatSecret</a></p>
      ${group(`Packaged foods · Open Food Facts${res.country ? ` · sold in ${esc(res.country_name)}` : " · all countries"}`, res.off,
        res.country ? `Nothing sold in ${esc(res.country_name)} matches. Try all countries, or the barcode.` : "No packaged match. Try the barcode instead.")}
      ${res.country ? `<button type="button" class="linkbtn" data-act="lk-everywhere">Search all countries</button>` : ""}
      <p class="meta">Packaged data © Open Food Facts contributors (ODbL). Every result is checked before it's saved.</p>` : ""}`;
}

/* A scanned barcode for the food in the form: filled in, then compared with Open Food Facts so a changed recipe shows.
   The food's carbs and source stay as they are (okf/features/manage-foods.md). */
async function newBarcode(code) {
  const box = $("#fCode"), note = $("#fCodeNote"); if (!box) return;
  const f = S.foods.find(x => x.id === S.m.food), old = f?.barcode;
  box.value = code; foodDirty = true;
  if (code === old) { note.textContent = "That's the barcode this food already has."; return; }
  note.textContent = `Scanned ${code}. Checking Open Food Facts…`;
  try {
    const x = (await api(`/api/lookup/off/${code}?check=true`, { parent: true })).reading;
    const per100 = x.carbs_g_per_100g ?? (x.serving_grams && x.total_carbs_g_per_serving != null ? x.total_carbs_g_per_serving / x.serving_grams * 100 : null);
    const theirs = per100 == null ? "no carbs listed" : `${+per100.toFixed(1)} g carbs per 100 g`;
    const differs = f && per100 != null && Math.abs(per100 - f.carbs_per_100g) > Math.max(0.5, f.carbs_per_100g * 0.05);
    note.innerHTML = `New barcode ${code}${old ? ` (was ${old})` : ""}: Open Food Facts says <b>${esc(x.product_name || "an unnamed product")}</b>, ${theirs}.
      ${!f ? "" : differs ? `<span class="warn">That's different from this food's ${f.carbs_per_100g} g per 100 g: check the package, the recipe may have changed.</span>`
        : per100 != null ? `Same carbs as this food (${f.carbs_per_100g} g per 100 g).` : "Check the carbs against the package."}
      Save food to keep the new barcode. The carbs aren't changed.`;
  } catch (err) {
    note.textContent = `New barcode ${code}${old ? ` (was ${old})` : ""}. ${err.status === 404 ? "Open Food Facts doesn't have it, so check the carbs against the package." : err.message} Save food to keep it.`;
  }
}

/* ---------- live barcode scanner (okf/features/food-lookup.md, okf/architecture/https.md) ---------- */
let scanner = null, detectorPromise = null;
const SCAN_FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e"];
function makeDetector() {
  detectorPromise ??= (async () => {
    if ("BarcodeDetector" in window) {
      try { if ((await BarcodeDetector.getSupportedFormats()).includes("ean_13")) return new BarcodeDetector({ formats: SCAN_FORMATS }); } catch { }
    }
    // iPad Safari and others: the bundled reader, with its engine served from this app, not a CDN.
    const { BarcodeDetector: Ponyfill, prepareZXingModule } = await import("/vendor/barcode.js");
    prepareZXingModule({ overrides: { locateFile: (path, prefix) => path.endsWith(".wasm") ? "/vendor/zxing_reader.wasm" : prefix + path }, fireImmediately: true });
    return new Ponyfill({ formats: SCAN_FORMATS });
  })();
  return detectorPromise;
}
const scanMsg = t => { const m = $("#scanMsg"); if (m) m.textContent = t; };
async function startScanner() {
  if (scanner || !$("#scanVideo")) return;
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    $("#scanner").classList.add("off");
    $("#scanner").innerHTML = `<p>The live scanner needs the secure address (the https name, or localhost). Here you can photograph the barcode or type its digits.</p>`;
    return;
  }
  const s = scanner = { stopped: false };
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: false, video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } } });
    if (s.stopped) { stream.getTracks().forEach(t => t.stop()); return; }
    s.stream = stream;
    const video = $("#scanVideo"); video.srcObject = stream; await video.play();
    const detector = await makeDetector();
    scanMsg("Hold the barcode inside the box");
    let last = null;
    const tick = async () => {
      if (s.stopped) return;
      try {
        const code = (await detector.detect(video)).map(r => (r.rawValue || "").replace(/\D/g, "")).find(v => v.length >= 8 && v.length <= 14);
        if (code && code === last && $("#fScanBox #scanVideo")) {   // a new barcode for the food being edited
          stopScanner(); $("#fScanBox").innerHTML = ""; newBarcode(code); return;
        }
        if (code && code === last && S.m.addTab === "batch") {   // scanning several: add it and keep going
          if (code !== s.lastAdded) { s.lastAdded = code; addBatchCode(code); }
          last = null; s.timer = setTimeout(tick, 250); return;
        }
        if (code && code === last) {           // the same code twice in a row, so a smudge isn't taken for a barcode
          stopScanner(); S.m.look.scanning = false; scanMsg(`Found ${code}`); openLookup("off", code); return;
        }
        last = code || null;
      } catch { /* a frame that can't be read; try the next one */ }
      s.timer = setTimeout(tick, 120);
    };
    tick();
  } catch (err) {
    stopScanner();
    const box = $("#scanner"); if (!box) return;
    box.classList.add("off");
    box.innerHTML = `<p>${err?.name === "NotAllowedError" ? "Camera access was refused. Allow the camera for this site in the browser settings, or photograph the barcode instead."
      : "No camera is available. Photograph the barcode or type its digits instead."}</p>`;
  }
}
function stopScanner() {
  if (!scanner) return;
  scanner.stopped = true; clearTimeout(scanner.timer);
  scanner.stream?.getTracks().forEach(t => t.stop());
  scanner = null;
}
document.addEventListener("visibilitychange", () => document.hidden ? stopScanner() : startScanner());

let lkTimer;
function lookupSearch(q) {
  if (q !== S.m.look.q) S.m.look.everywhere = false;   // a new search starts in the home region again
  S.m.look.q = q; clearTimeout(lkTimer);
  lkTimer = setTimeout(async () => {
    if (q.trim().length < 2) { S.m.look.res = null; return refreshLookup(); }
    S.m.look.busy = "Searching…"; S.m.look.err = ""; refreshLookup();
    try { const r = await api("/api/lookup/search?q=" + encodeURIComponent(q) + (S.m.look.everywhere ? "&everywhere=1" : ""), { parent: true }); if (S.m.look.q === q) S.m.look.res = r; }
    catch (err) { S.m.look.err = err.message; }
    S.m.look.busy = false; refreshLookup();
  }, 450);
}
function refreshLookup() {   // only the results redraw, so the camera and the search box are left alone
  const el = $("#lkResults"); if (el) el.innerHTML = lookupResults();
}
async function openLookup(source, id) {
  S.m.look.busy = "Getting the details…"; S.m.look.err = ""; refreshLookup();
  try {
    const r = await api(`/api/lookup/${source === "fatsecret" ? "fatsecret" : source === "usda" ? "usda" : "off"}/${encodeURIComponent(id)}`, { parent: true });
    S.m.scan = { stage: "review", ...r }; S.m.look.busy = false; mNav();
  } catch (err) { if (err.status === 401) pinStore.set(""); S.m.look.busy = false; S.m.look.err = err.message; refreshLookup(); startScanner(); }
}
function usdaReview(sc) {
  const notes = sc.typical_portions.length ? `USDA typical portions (reference only, weigh your own): ${sc.typical_portions.join("; ")}` : "";
  return `<h2>Check the USDA values</h2>
    <p class="meta">${esc(sc.name)} · <a href="https://fdc.nal.usda.gov/food-details/${esc(sc.id)}/nutrients" target="_blank" rel="noopener">USDA FDC ${esc(sc.id)}</a></p>
    <form class="form" id="usdaForm">
      <label class="field"><span>Name</span><input id="uName" required maxlength="80" value="${esc(sc.name)}"></label>
      <fieldset class="field tagpick"><legend>Tags (choose any)</legend><div>${S.tags.map(t =>
        `<label class="check"><input type="checkbox" name="uTag" value="${t.id}">${esc(t.name)}</label>`).join("")}</div></fieldset>
      <label class="field"><span>Carbs per 100 g, as served <em class="from">from USDA</em></span><input id="uCp" type="number" step="0.1" min="0" max="100" inputmode="decimal" required value="${sc.carbs_per_100g ?? ""}"></label>
      <label class="field"><span>Fiber per 100 g, optional ${sc.fiber_per_100g != null ? `<em class="from">from USDA</em>` : ""}</span><input id="uFiber" type="number" step="0.1" min="0" max="100" inputmode="decimal" value="${sc.fiber_per_100g ?? ""}" placeholder="Not listed"></label>
      <label class="field"><span>Source reference</span><input id="uRef" required maxlength="200" value="${esc(sc.source_ref)}"></label>
      <label class="field"><span>Notes</span><textarea id="uNotes" maxlength="1000">${esc(notes)}</textarea></label>
      <div class="confirms"><span class="label">Confirm</span>
        <label class="check"><input type="checkbox" id="uConf"><span id="uConfText"></span></label></div>
      <p class="meta">Check the description matches what you serve (cooked or raw, with or without salt). After saving, add portions with the grams you weighed.</p>
      <p class="err" id="uErr"></p>
      <div class="actions"><button class="btn primary" id="uSave" disabled>Save food</button><button type="button" class="btn quiet" data-act="check-cancel">Cancel</button></div>
    </form>`;
}
function usdaConfirm() {
  const v = $("#uCp")?.value; if (v === undefined) return;
  $("#uConfText").textContent = v ? `Carbs per 100 g is ${v} g, and this USDA food matches what I serve` : "Enter carbs per 100 g first";
  $("#uConf").disabled = !v; if (!v) $("#uConf").checked = false;
  $("#uSave").disabled = !$("#uConf").checked;
}
async function saveUsda() {
  const body = { name: $("#uName").value, tags: [...document.querySelectorAll("input[name=uTag]:checked")].map(x => +x.value),
    carbs_per_100g: parseFloat($("#uCp").value), fiber_per_100g: $("#uFiber").value === "" ? null : parseFloat($("#uFiber").value), source_kind: "usda", source_ref: $("#uRef").value, notes: $("#uNotes").value, verified: true };
  try {
    const f = await api("/api/foods", { method: "POST", body, parent: true });
    S.m.scan = null; S.m.food = f.id; toast(`${f.name} added. Now add portions with the grams you weighed.`); await loadFoods(); mNav();
    $("#npLabel")?.focus();
  } catch (err) { $("#uErr").textContent = err.message; }
}

/* ---------- scan a nutrition label (okf/features/scan-label.md) ---------- */
function scanPanel() {
  const sc = S.m.scan;
  if (sc.stage === "reading") return `<div class="form"><h2>Reading the label…</h2><p class="meta">This takes a few seconds.</p></div>`;
  if (sc.mode === "per100") return usdaReview(sc);
  const r = sc.reading, today = localDay();
  const fs = sc.source === "fatsecret";
  const notes = [r.serving_size_text && `${fs ? "FatSecret serving" : "Serving on label"}: ${r.serving_size_text}`,
    r.total_sugars_g_per_serving != null && `sugars ${r.total_sugars_g_per_serving} g per serving`]
    .filter(Boolean).join("; ") + (sc.other_servings?.length ? `\nOther FatSecret servings (reference only, weigh your own): ${sc.other_servings.join("; ")}` : "");
  const from = v => v != null ? `<em class="from">${fs ? "from FatSecret" : "from label"}</em>` : "";
  return `<h2>${fs ? "Check the FatSecret values" : sc.code ? "Check against the package" : "Check the label"}</h2>
    ${fs ? `<p class="meta">${esc(sc.source_ref)} · <a href="https://www.fatsecret.com" target="_blank" rel="noopener">Powered by FatSecret</a>. Check the serving weight and carbs against the package or another trusted source.</p>` : ""}
    ${sc.code ? `<div class="offhead">${sc.product_image ? `<img src="${esc(sc.product_image)}" alt="Package photo from Open Food Facts" referrerpolicy="no-referrer">` : ""}
      <p class="meta">From Open Food Facts, barcode ${esc(sc.code)}. Volunteers enter this data: check the package photo is your product, then compare the numbers with your package.</p></div>` : ""}
    <div class="labelreview">
      ${sc.label_photo ? `<a href="${photoUrl(sc.label_photo)}" target="_blank" rel="noopener" class="labelimg"><img ${sized(sc.label_photo, "(min-width: 1100px) 40vw, 90vw")} alt="Nutrition label photo"></a>`
        : `<div class="labelimg nolabel"><p>${fs ? "FatSecret has no label photo." : "Open Food Facts has no photo of this product's nutrition panel."} Check the numbers against the package in your hand${fs ? " or a trusted source" : ""}.</p></div>`}
      <form class="form" id="scanForm">
        ${sc.warnings.length ? `<ul class="warnlist">${sc.warnings.map(w => `<li>${esc(w)}</li>`).join("")}</ul>` : `<p class="meta">Compare each number with the photo before saving.</p>`}
        <label class="field"><span>Name ${from(r.product_name)}</span><input id="sName" required maxlength="80" value="${esc(r.product_name || "")}"></label>
        <fieldset class="field tagpick"><legend>Tags (choose any)</legend><div>${S.tags.map(t =>
          `<label class="check"><input type="checkbox" name="sTag" value="${t.id}">${esc(t.name)}</label>`).join("")}</div></fieldset>
        <div class="fieldrow">
          <label class="field"><span>Grams per serving ${from(r.serving_grams)}</span><input id="sGrams" type="number" step="0.1" min="0.1" inputmode="decimal" required value="${r.serving_grams ?? ""}"></label>
          <label class="field"><span>Total carbohydrate per serving, g ${from(r.total_carbs_g_per_serving)}</span><input id="sCarbs" type="number" step="0.1" min="0" inputmode="decimal" required value="${r.total_carbs_g_per_serving ?? ""}"></label></div>
        <label class="field"><span>Fiber per serving, g, optional ${from(r.fiber_g_per_serving)}</span><input id="sFiber" type="number" step="0.1" min="0" inputmode="decimal" value="${r.fiber_g_per_serving ?? ""}" placeholder="Not listed"></label>
        ${r.total_carbs_g_per_serving == null && r.carbs_g_per_100g != null ? `<p class="meta">The label gives ${r.carbs_g_per_100g} g carbs per 100 g. Enter the serving grams and carbs per serving fills in.</p>` : ""}
        <p class="scanmath" id="sMath"></p>
        <label class="field"><span>Those grams are for the</span>${basisSelect(null, "s")}</label>
        ${cookRatio(null, "s")}
        <label class="field"><span>This portion as a number and unit</span>${labelInput("sPortion", suggestPortion(r.serving_size_text))}</label>
        <label class="field"><span>Source reference</span><input id="sRef" required maxlength="200" value="${esc(sc.source_ref || `Nutrition label photo, ${today}`)}"></label>
        <label class="field"><span>Notes</span><textarea id="sNotes" maxlength="1000">${esc(notes)}</textarea></label>
        <p class="meta">The plate uses total carbohydrate. Fiber is kept for reference and never subtracted; whether to count it is your care team's call.</p>
        ${noteField("sNote")}
        <label class="check"><input type="checkbox" id="sAutoPhoto" checked><span>Make a photo now. Gemini picks its own package, plate, bowl or dressing cup; you can change it after.</span></label>
        <div class="confirms"><span class="label">${fs ? "Confirm against the package or a trusted source" : "Confirm against the label photo"}</span>
          <label class="check"><input type="checkbox" id="sConfServ"><span id="sConfServText"></span></label>
          <label class="check"><input type="checkbox" id="sConfCarb"><span id="sConfCarbText"></span></label></div>
        <p class="err" id="sErr"></p>
        ${sc.code || sc.source ? "" : `<div><button type="button" class="linkbtn" data-act="scan-again">Wrong photo? Scan another one</button></div>`}
        <div class="actions"><button class="btn primary" id="sSave" disabled>Save food</button>
          <button type="button" class="btn quiet" data-act="check-cancel">Cancel</button></div>
      </form></div>`;
}
function scanConfirms() {
  const g = $("#sGrams").value, c = $("#sCarbs").value;
  $("#sConfServText").textContent = g ? `Serving size is ${g} g${S.m.scan?.source === "fatsecret" ? "" : " on the label"}` : "Serving size: enter the grams first";
  const where = S.m.scan?.source === "fatsecret" ? "" : " on the label";
  const fb = $("#sFiber")?.value;
  $("#sConfCarbText").textContent = c ? `Total carbohydrate is ${c} g per serving${fb !== "" ? `, including ${fb} g fiber` : ""}${where}` : "Total carbohydrate: enter it first";
  $("#sConfServ").disabled = !g; $("#sConfCarb").disabled = !c;
  if (!g) $("#sConfServ").checked = false;
  if (!c) $("#sConfCarb").checked = false;
  $("#sSave").disabled = !($("#sConfServ").checked && $("#sConfCarb").checked);
}
function scanMath() {
  cookExplain("s");
  if ($("#uCp")) return usdaConfirm();
  const g = parseFloat($("#sGrams")?.value), c = parseFloat($("#sCarbs")?.value), el = $("#sMath");
  if (!el) return;
  scanConfirms();
  const per100 = S.m.scan?.reading.carbs_g_per_100g;
  if (g > 0 && !$("#sCarbs").value && per100 != null) { $("#sCarbs").value = (per100 * g / 100).toFixed(1); return scanMath(); }
  if (!(g > 0) || !(c >= 0)) { el.textContent = "Enter grams and carbs per serving."; el.classList.remove("warn"); return; }
  const cp = Math.round(c / g * 1000) / 10;
  el.innerHTML = c > g ? `<span class="warn">Carbs can't be more than the serving weight.</span>`
    : `<b>${cp}</b> g carbs per 100 g · this portion counts as <b>${whole(exact(g, cp))}</b> g carbs`;
}
async function readLabel(file) {
  S.m.scan = { stage: "reading" }; renderManage();
  const form = new FormData(); form.append("file", file);
  try {
    const r = await api("/api/labels/read", { method: "POST", form, parent: true });
    S.m.scan = { stage: "review", ...r }; return mNav();
  } catch (err) { if (err.status === 401) pinStore.set(""); S.m.scan = { stage: "pick", err: err.message }; }
  renderManage(); scanMath();
}
async function saveScanned() {
  const g = parseFloat($("#sGrams").value), c = parseFloat($("#sCarbs").value);
  if (!(g > 0) || !(c >= 0) || c > g) { $("#sErr").textContent = "Check the grams and carbs per serving."; return; }
  if (!$("#sConfServ").checked || !$("#sConfCarb").checked) { $("#sErr").textContent = "Confirm the serving size and total carbohydrate against the label."; return; }
  const body = { name: $("#sName").value, tags: [...document.querySelectorAll("input[name=sTag]:checked")].map(x => +x.value),
    serving_grams: g, serving_carbs: c, serving_fiber: $("#sFiber").value === "" ? null : parseFloat($("#sFiber").value), source_kind: S.m.scan.source || (S.m.scan.code ? "openfoodfacts" : "label"), source_ref: $("#sRef").value, notes: $("#sNotes").value,
    verified: true, label_photo: S.m.scan.label_photo, package_photo: S.m.scan.package_photo || null, ...cookBody("s") };   // both confirmations ticked (okf/rules/label-reading-needs-check.md)
  try {
    const f = await api("/api/foods", { method: "POST", body, parent: true });
    const withPhoto = $("#sAutoPhoto").checked;
    const fp = await api(`/api/foods/${f.id}/portions`, { method: "POST", parent: true, body: { label: $("#sPortion").value, grams: g, sort: 0, photo_note: $("#sNote").value } });
    if (withPhoto)   // runs on the server in the background; the portion row shows progress (okf/features/food-lookup.md)
      await api(`/api/portions/${fp.portions[0].id}/generate`, { method: "POST", parent: true }).catch(err => toast(err.message));
    if (S.dlg) { S.m.scan = null; return dlgSaved(f); }
    S.m.scan = null; S.m.food = f.id;
    toast(withPhoto ? `${f.name} added. Making its photo…` : `${f.name} added. Add a photo when you have one.`);
    await loadFoods(); mNav(); watchJobs();
  } catch (err) { $("#sErr").textContent = err.message; }
}

/* ---------- scan several barcodes into a review table (okf/features/food-lookup.md) ----------
   Phones: the scanner and a short list; each new food opens its own check screen, and Done goes back to the scanner
   at the top. Wider screens: one table. Complete saves the checked foods and leaves. */
const batch = () => (S.m.batch ??= { rows: [], focus: null });
const PHONE_MQ = matchMedia("(max-width: 680px)");
const rowChecked = r => r.status === "ready" && r.confServ && r.confCarb && portionAmount(r.portion);
const fiberNum = v => v === "" || v == null ? null : +v;
function batchPanel() {
  const b = batch(), r = b.rows[b.focus];
  if (PHONE_MQ.matches && r?.status === "ready") return batchFocus(r, b.focus);
  return `<div class="form batch">
    <div class="scanner" id="scanner"><video id="scanVideo" playsinline muted></video><div class="scanbox"></div>
      <p class="scanmsg" id="scanMsg">Starting the camera…</p></div>
    <form class="cmtform" id="batchCode"><input id="bCode" inputmode="numeric" placeholder="or type the barcode digits" aria-label="Barcode digits"><button class="btn small">Add</button></form>
    <p class="meta">${PHONE_MQ.matches ? "Scan each package. Each food opens for you to check against its package, then the scanner comes back."
      : "Scan each package in turn; each one is added below. Check every row against its package: the serving size and the total carbohydrate each need a tick before that food can be saved."}</p>
    <div id="batchTable">${batchTable()}</div></div>`;
}
function batchTable() {
  const rows = batch().rows;
  if (!rows.length) return `<p class="meta">Nothing scanned yet.</p>${completeBar()}`;
  if (PHONE_MQ.matches) return batchList() + completeBar();
  return `<table class="batchtab"><thead><tr><th></th><th>Food</th><th>Serving</th><th>Carbs per serving</th><th>Label</th><th>Photo</th><th></th></tr></thead><tbody>
    ${rows.map((r, i) => r.status === "loading" ? `<tr><td></td><td colspan="6" class="meta">${esc(r.code)} · looking it up…</td></tr>`
      : r.status === "error" ? `<tr><td></td><td colspan="5"><b>${esc(r.code)}</b><p class="err">${esc(r.err)}</p></td><td><button class="rm" data-bact="remove" data-bi="${i}" aria-label="Remove">×</button></td></tr>`
      : r.status === "saved" ? `<tr class="saved"><td>${r.image ? `<img src="${esc(r.image)}" alt="" referrerpolicy="no-referrer">` : ""}</td><td colspan="5"><b>${esc(r.name)}</b><span class="meta"> · saved${r.photo ? ", photo on its way" : ""}</span></td>
          <td><button class="linkbtn" data-mfood="${esc(r.foodId)}">Open</button></td></tr>`
      : `<tr data-bi="${i}">
        <td data-l="Package">${r.image ? `<img src="${esc(r.image)}" alt="Package" referrerpolicy="no-referrer">` : `<span class="noimg">No photo</span>`}</td>
        <td data-l="Food"><input class="bName" value="${esc(r.name)}" maxlength="80" aria-label="Name"><span class="meta">${esc(r.code)}</span>
          ${r.warnings.length ? `<ul class="warnlist">${r.warnings.map(w => `<li>${esc(w)}</li>`).join("")}</ul>` : ""}${tagChecks(r)}</td>
        <td data-l="Serving">${servingInputs(r)}</td>
        <td data-l="Carbs per serving">${carbInputs(r)}</td>
        <td data-l="Label">${r.label ? `<a href="${photoUrl(r.label)}" target="_blank" rel="noopener"><img ${sized(r.label, "72px")} alt="Nutrition label"></a>` : `<span class="meta">No label photo</span>`}</td>
        <td data-l="Photo"><label class="check"><input type="checkbox" class="bPhoto" ${r.photo ? "checked" : ""}><span>Make one</span></label>
          <input class="bNote" maxlength="300" value="${esc(r.note || "")}" placeholder="Note for Gemini" aria-label="Note for Gemini, optional"></td>
        <td><button class="rm" data-bact="remove" data-bi="${i}" aria-label="Remove ${esc(r.name)}">×</button></td></tr>`).join("")}</tbody></table>
    ${completeBar()}`;
}
const tagChecks = r => S.tags.length ? `<div class="btags" role="group" aria-label="Tags">${S.tags.map(t =>   // okf/features/food-lookup.md
  `<label class="check"><input type="checkbox" class="bTag" value="${t.id}" ${r.tags?.includes(t.id) ? "checked" : ""}><span>${esc(t.name)}</span></label>`).join("")}</div>` : "";
const servingInputs = r => `<div class="bserv"><div class="bnum bportion">${labelInput("", r.portion || "1 serving", "bPortion")}<span>=</span></div>
  <div class="bnum"><input class="bGrams" type="number" step="0.1" min="0.1" inputmode="decimal" value="${r.grams ?? ""}" aria-label="Grams per serving"><span>g</span></div></div>
  <label class="check"><input type="checkbox" class="bConfServ" ${r.confServ ? "checked" : ""} ${r.grams ? "" : "disabled"}><span>Matches the package</span></label>`;
const carbInputs = r => `<div class="bnum"><input class="bCarbs" type="number" step="0.1" min="0" inputmode="decimal" value="${r.carbs ?? ""}" aria-label="Carbs per serving"><span>g</span></div>
  <div class="bnum bfiber"><span>including</span><input class="bFiber" type="number" step="0.1" min="0" inputmode="decimal" value="${r.fiber ?? ""}" placeholder="–" aria-label="Fiber per serving, grams"><span>g fiber</span></div>
  <label class="check"><input type="checkbox" class="bConfCarb" ${r.confCarb ? "checked" : ""} ${r.carbs != null && r.carbs !== "" ? "" : "disabled"}><span>Matches the package</span></label>`;
function batchList() {   // phones: one line per food; tap one to check it
  return `<ul class="blist">${batch().rows.map((r, i) => {
    const img = r.image ? `<img src="${esc(r.image)}" alt="" referrerpolicy="no-referrer">` : `<span class="noimg"></span>`;
    const state = r.status === "loading" ? `<span class="meta">Looking it up…</span>` : r.status === "error" ? `<span class="err">${esc(r.err)}</span>`
      : r.status === "saved" ? `<span class="meta">Saved</span>` : rowChecked(r) ? `<span class="ok">Checked · ${fmtG(r.carbs)} carbs</span>` : `<span class="warn">Needs checking</span>`;
    const name = esc(r.name || r.code);
    return `<li>${r.status === "ready" ? `<button class="brow" data-bact="focus" data-bi="${i}">${img}<span><b>${name}</b>${state}</span><i aria-hidden="true">›</i></button>`
      : `<div class="brow">${img}<span><b>${name}</b>${state}</span>${r.status === "error" ? `<button class="rm" data-bact="remove" data-bi="${i}" aria-label="Remove">×</button>` : ""}</div>`}</li>`;
  }).join("")}</ul>`;
}
function batchFocus(r, i) {   // phones: one food at a time, laid out top to bottom
  return `<div class="form bfocus" data-bi="${i}">
    <div class="bfhead">${r.image ? `<img src="${esc(r.image)}" alt="Package" referrerpolicy="no-referrer">` : `<span class="noimg">No photo</span>`}
      <div><span class="label">Check against the package</span><span class="meta">Barcode ${esc(r.code)}</span></div></div>
    ${r.warnings.length ? `<ul class="warnlist">${r.warnings.map(w => `<li>${esc(w)}</li>`).join("")}</ul>` : ""}
    <label class="field"><span>Name</span><input class="bName" value="${esc(r.name)}" maxlength="80"></label>
    ${S.tags.length ? `<fieldset class="field tagpick"><legend>Tags (choose any)</legend>${tagChecks(r)}</fieldset>` : ""}
    <div class="field"><span>Serving: a number and unit, and its grams</span>${servingInputs(r)}</div>
    <div class="field"><span>Total carbohydrate per serving</span>${carbInputs(r)}</div>
    ${r.label ? `<a class="labelthumb" href="${photoUrl(r.label)}" target="_blank" rel="noopener"><img ${sized(r.label, "72px")} alt="Nutrition label"><span class="meta">Label photo · open full size</span></a>` : `<p class="meta">No label photo: compare with the package in your hand.</p>`}
    <label class="check"><input type="checkbox" class="bPhoto" ${r.photo ? "checked" : ""}><span>Make a photo after saving</span></label>
    <label class="field"><span>Note for Gemini (optional)</span><input class="bNote" maxlength="300" value="${esc(r.note || "")}" placeholder="e.g. plain rice, no sauce, ignore the fork"></label>
    <div><button type="button" class="btn quiet small" data-bact="remove" data-bi="${i}">Remove this food</button></div>
    <div class="actions"><button type="button" class="btn quiet" data-bact="later">Later</button>
      <button type="button" class="btn primary" data-bact="done" ${rowChecked(r) ? "" : "disabled"}>${rowChecked(r) ? "Done, scan the next" : "Tick both to continue"}</button></div></div>`;
}
function completeBar() {
  const rows = batch().rows, ready = rows.filter(rowChecked).length, open = rows.filter(r => r.status === "ready" && !rowChecked(r) || r.status === "loading").length;
  const sure = Date.now() - (batch().confirmAt || 0) < 4000;
  return `<p class="err" id="bErr">${sure && open ? `${open} food${open > 1 ? "s aren't" : " isn't"} checked and won't be saved. Tap again to finish anyway.` : ""}</p>
    <div class="actions bcomplete"><button class="btn primary" data-bact="complete">${ready ? `Complete: save ${ready} food${ready === 1 ? "" : "s"}` : "Complete"}</button>
      ${rows.length ? `<button class="btn quiet" data-bact="clear">Clear all</button>` : ""}</div>`;
}
function redrawBatch(top) {   // the whole tab: scanner or check screen
  const body = $(".addbody"); if (!body || S.m.addTab !== "batch") return;
  stopScanner(); body.innerHTML = batchPanel(); queueMicrotask(startScanner);
  if (top) { $("#v-manage").scrollTop = 0; scrollTo(0, 0); }
}
const refreshBatch = () => {
  if ($(".bfocus") || (PHONE_MQ.matches && batch().rows[batch().focus]?.status === "ready")) return redrawBatch();
  const el = $("#batchTable"); if (el) el.innerHTML = batchTable();
};
PHONE_MQ.addEventListener("change", () => redrawBatch());
async function addBatchCode(code) {
  code = code.replace(/\D/g, "");
  if (code.length < 8) { toast("A barcode has 8 to 14 digits."); return; }
  if (batch().rows.some(r => r.code === code)) { scanMsg(`${code} is already in the list`); return; }
  const row = { code, status: "loading" }; batch().rows.push(row); refreshBatch(); scanMsg(`Added ${code}. Looking it up…`);
  try {
    const r = await api(`/api/lookup/off/${code}`, { parent: true }), x = r.reading;
    Object.assign(row, { status: "ready", name: x.product_name || "", grams: x.serving_grams, carbs: x.total_carbs_g_per_serving, fiber: x.fiber_g_per_serving,
      portion: suggestPortion(x.serving_size_text), warnings: r.warnings, label: r.label_photo, package: r.package_photo, image: r.product_image, ref: r.source_ref,
      notes: readingNotes(x), confServ: false, confCarb: false, photo: true, tags: [] });
    const b = batch();
    if (PHONE_MQ.matches && b.focus == null) { b.focus = b.rows.indexOf(row); return redrawBatch(true); }   // open it to check
  } catch (err) { Object.assign(row, { status: "error", err: err.message }); }
  if (!$(".bfocus")) refreshBatch();   // never redraw a check screen under the parent's fingers
}
function readingNotes(r) {   // fiber has its own field now (okf/domain/food.md)
  return [r.serving_size_text && `Serving on label: ${r.serving_size_text}`,
    r.total_sugars_g_per_serving != null && `sugars ${r.total_sugars_g_per_serving} g per serving`].filter(Boolean).join("; ");
}
function batchEdit(e) {   // a changed number clears its tick: the tick confirms that exact value
  const box = e.target.closest("[data-bi]:not(button)"); if (!box) return false;
  const row = batch().rows[+box.dataset.bi], v = e.target.value;
  if (e.target.matches(".bName")) row.name = v;
  else if (e.target.matches(".bPortion")) row.portion = v.trim();
  else if (e.target.matches(".bGrams")) { row.grams = v === "" ? null : +v; row.confServ = false; }
  else if (e.target.matches(".bCarbs")) { row.carbs = v === "" ? null : +v; row.confCarb = false; }
  else if (e.target.matches(".bFiber")) { row.fiber = fiberNum(v); row.confCarb = false; }
  else if (e.target.matches(".bConfServ")) row.confServ = e.target.checked;
  else if (e.target.matches(".bConfCarb")) row.confCarb = e.target.checked;
  else if (e.target.matches(".bPhoto")) row.photo = e.target.checked;
  else if (e.target.matches(".bNote")) row.note = v;
  else if (e.target.matches(".bTag")) { const id = +v; row.tags = e.target.checked ? [...new Set([...(row.tags || []), id])] : (row.tags || []).filter(x => x !== id); }
  else return false;
  refreshBatch(); return true;
}
async function batchAct(t) {
  const b = batch();
  if (t.dataset.bact === "focus") { b.focus = +t.dataset.bi; return redrawBatch(true); }
  if (t.dataset.bact === "done" || t.dataset.bact === "later") {   // back to the scanner, at the top
    b.focus = null; redrawBatch(true);
    if (t.dataset.bact === "done") scanMsg("Checked. Scan the next one");
    return;
  }
  if (t.dataset.bact === "remove") { b.rows.splice(+t.dataset.bi, 1); b.focus = null; return redrawBatch(true); }
  if (t.dataset.bact === "clear") { S.m.batch = { rows: [], focus: null }; if (scanner) scanner.lastAdded = null; return redrawBatch(); }
  if (t.dataset.bact === "complete") {
    const open = b.rows.filter(r => r.status === "ready" && !rowChecked(r) || r.status === "loading").length;
    if (open && Date.now() - (b.confirmAt || 0) > 4000) { b.confirmAt = Date.now(); return refreshBatch(); }   // a second tap confirms
    t.disabled = true;
    const problems = await saveBatch();
    if (problems.length) { b.confirmAt = 0; refreshBatch(); if ($("#bErr")) $("#bErr").textContent = problems.join(" · "); return; }
    S.m.batch = { rows: [], focus: null }; stopScanner(); S.m.look.scanning = false;
    if (S.batchFromFoods) { S.batchFromFoods = false; location.hash = "#foods"; }
    else { S.m.food = null; mNav(); }
  }
}
async function saveBatch() {   // saves the checked rows; returns what went wrong
  const todo = batch().rows.filter(rowChecked);
  let saved = 0, problems = [];
  for (const r of todo) {
    if (!(r.grams > 0) || !(r.carbs >= 0) || r.carbs > r.grams || !r.name.trim()) { problems.push(`${r.name || r.code}: check the name, grams and carbs`); continue; }
    if (r.fiber != null && r.fiber > r.grams) { problems.push(`${r.name}: fiber can't be more than the serving`); continue; }
    try {   // both values ticked for this row (okf/rules/label-reading-needs-check.md)
      const f = await api("/api/foods", { method: "POST", parent: true, body: { name: r.name, tags: r.tags || [], serving_grams: r.grams, serving_carbs: r.carbs, serving_fiber: r.fiber ?? null,
        source_kind: "openfoodfacts", source_ref: r.ref, notes: r.notes, verified: true, label_photo: r.label, package_photo: r.package } });
      const fp = await api(`/api/foods/${f.id}/portions`, { method: "POST", parent: true, body: { label: r.portion.trim(), grams: r.grams, sort: 0, photo_note: r.note || "" } });
      if (r.photo) await api(`/api/portions/${fp.portions[0].id}/generate`, { method: "POST", parent: true }).catch(err => toast(`${f.name} photo: ${err.message}`));
      Object.assign(r, { status: "saved", foodId: f.id }); saved++;
    } catch (err) { problems.push(`${r.name}: ${err.message}`); }
  }
  await loadFoods(); if ($("#mRows")) $("#mRows").innerHTML = manageRows(); watchJobs();
  if (saved || problems.length) toast(`${saved} food${saved === 1 ? "" : "s"} saved${problems.length ? `, ${problems.length} need a look` : ""}`);
  return problems;
}

/* ---------- photo style (okf/features/photo-style-setup.md) ---------- */
const stillOn = tab => S.m.tab === tab && $m();   // a slow reply mustn't draw over a tab the parent has left
async function loadStyle() {
  try { S.style = await api("/api/style", { parent: true }); } catch (err) { if (stillOn("style")) $m().innerHTML = `<div class="empty">${esc(err.message)}</div>`; return; }
  if (stillOn("style")) renderStyle();
}
function renderStyle() {
  const s = S.style, names = { plate: "Plate", bowl: "Bowl", dressing: "Dressing container" };
  $m().innerHTML = `<div class="pad"><div class="form">
    <h2>Photo style</h2>
    <p class="meta">Gemini restyles each of your portion photos using this description and photos of your own dishes. Existing photos don't change; use "Style with Gemini" on a portion to redo it.</p>
    <fieldset class="field tagpick"><legend>Speed</legend><div class="seg neutral" role="radiogroup">${[["fast", "Fast · about 3 s"], ["sharp", "Sharp · about 15 s"]].map(([k, l]) =>
      `<button type="button" role="radio" aria-checked="${s.quality === k}" class="${s.quality === k ? "on" : ""}" data-quality="${k}">${l}</button>`).join("")}</div>
      <p class="meta">${s.quality === "sharp" ? "2400 px wide, for big high-resolution screens." : "1200 px wide, sharp on the tablet and phones; a little soft on a large high-resolution monitor."}</p></fieldset>
    <div class="glab"><span class="label">Base photos</span><span class="meta">The empty dish on the counter, from your usual angle</span></div>
    <div class="bases">${Object.entries(names).map(([k, l]) => `<figure>
      ${s.bases[k] ? `<img ${sized(s.bases[k], "260px")} alt="${l}">` : `<span class="noimg">No photo yet</span>`}
      <figcaption><b>${l}</b><span class="actions">
        <label class="btn small">${s.bases[k] ? "Replace" : "Add photo"}<input type="file" accept="image/*" data-basefile="${k}" hidden></label>
        ${s.bases[k] ? `<button class="btn small quiet" data-act="base-clear" data-kind="${k}">Remove</button>` : ""}</span></figcaption></figure>`).join("")}</div>
    <div class="glab"><span class="label">Size references</span><span class="meta">Something of known size, so Gemini knows how much food to show</span></div>
    ${s.size_refs.length ? `<div class="bases">${s.size_refs.map(r => S.editRef === r.id ? `<form class="form sizeedit" id="refEdit" data-rid="${r.id}">
        <img ${sized(r.photo, "260px")} alt="">
        <label class="field"><span>Name</span><input id="reName" required maxlength="60" value="${esc(r.name)}"></label>
        <label class="field"><span>Measurement</span><input id="reMeas" required maxlength="40" value="${esc(r.measurement)}"></label>
        ${dishPick("reDish", r.container)}
        <div class="actions"><button class="btn small">Save</button><button type="button" class="btn small quiet" data-act="ref-edit-cancel">Cancel</button></div></form>`
      : `<figure><img ${sized(r.photo, "260px")} alt="${esc(r.name)}"><figcaption><b>${esc(r.name)}</b><span class="meta">${esc(r.measurement)} · ${r.container ? DISHES[r.container] : "Any dish"}</span>
        <span class="actions"><button class="btn small" data-act="ref-edit" data-rid="${r.id}">Edit</button>
        <button class="btn small quiet" data-act="ref-del" data-rid="${r.id}">${S.delRef?.id === r.id ? "Tap again to remove" : "Remove"}</button></span></figcaption></figure>`).join("")}</div>`
      : `<p class="meta">None yet. For example: your 1-cup measuring cup filled with rice, a tablespoon, or your son's usual bowl filled.</p>`}
    <form class="form refadd" id="refAdd"><h3>Add a size reference</h3>
      <div class="fieldrow"><label class="field"><span>Name</span><input id="raName" required maxlength="60" placeholder="Measuring cup, filled"></label>
        <label class="field"><span>Measurement</span><input id="raMeas" required maxlength="40" placeholder="1 cup (240 mL)"></label>
        ${dishPick("raDish", "")}</div>
      <label class="field"><span>Photo, on the counter from your usual angle</span><input id="raFile" type="file" accept="image/*" required></label>
      <p class="meta">Choose it on a portion under "Served in · size". One that goes with a dish is picked for you when a portion is served in that dish. It only guides how big the food looks; carbs always come from the grams you weighed.</p>
      <div class="actions"><button class="btn">Add size reference</button><button type="button" class="btn quiet" data-act="form-reset">Cancel</button></div></form>
    <form class="form" id="styleForm">
      <label class="field"><span>Style description</span><textarea id="stylePrompt" maxlength="2000" style="height:140px">${esc(s.prompt)}</textarea></label>
      <p class="meta">Always added, and can't be changed here: “${esc(s.guard)}”</p>
      <div class="actions"><button class="btn">Save style</button><button type="button" class="btn quiet" data-act="form-reset">Cancel</button>
        <button type="button" class="btn quiet" data-act="style-reset">Reset to the default</button></div>
    </form></div></div>`;
}

let confirmTag = { id: null, at: 0 };
function renderTags() {
  $m().innerHTML = `<div class="pad"><div class="form">
    <h2>Tags</h2><p class="meta">Tags group foods in the Foods list. A food can have several. Favorites is separate: it holds pinned plates.</p>
    <table class="portions"><thead><tr><th>Tag</th><th>Foods</th><th></th></tr></thead><tbody>${S.tags.map(t => `<tr data-tid="${t.id}">
      <td><input class="tName" value="${esc(t.name)}" maxlength="30" aria-label="Tag name"></td><td class="meta">${t.foods}</td>
      <td><button class="btn small quiet" data-tact="del">${confirmTag.id === t.id ? "Tap again to remove" : "Remove"}</button></td></tr>`).join("")}</tbody></table>
    <form class="actions" id="tagAdd" style="align-items:end"><label class="field"><span>New tag</span><input id="tagNew" maxlength="30" required placeholder="Snacks"></label><button class="btn">Add tag</button><button type="button" class="btn quiet" data-act="form-reset">Cancel</button></form>
    <p class="err" id="tagErr"></p></div></div>`;
}

async function renderNightscout() {
  if (!$m()) return;
  let s; try { s = await api("/api/nightscout"); } catch (err) { if (stillOn("nightscout")) $m().innerHTML = `<div class="empty">${esc(err.message)}</div>`; return; }
  if (!stillOn("nightscout")) return;
  const ago = ms => ms ? `${Math.max(0, Math.round((Date.now() - ms) / 60000))} min ago` : "never";
  $m().innerHTML = `<div class="pad"><div class="form">
    <h2>Nightscout</h2>
    <p class="meta">Read-only. The app pulls glucose readings every 5 minutes and never writes anything to Nightscout. The token stays on the kitchen server.</p>
    ${s.configured ? `<div class="strip"><div class="tirl"><span>Connected to <b>${esc(s.url)}</b></span></div>
      <div class="tirl">${s.latest ? `<span>Latest <b>${s.latest.sgv}</b> mg/dL ${esc(s.latest.direction || "")} · ${ago(s.latest.date_ms)}</span>` : "<span>No readings yet</span>"}
      <span>${s.readings} readings stored</span><span>Last sync ${ago(s.last_sync_ms)}</span></div>
      ${s.last_error ? `<p class="err">${esc(s.last_error)}</p>` : ""}</div>
      <div class="actions"><button class="btn quiet" data-act="ns-off">Disconnect</button></div>` : ""}
    <form class="form" id="nsForm"><h3>${s.configured ? "Change connection" : "Connect"}</h3>
      <label class="field"><span>Nightscout address</span><input id="nsUrl" type="url" required placeholder="https://yoursite.example.com" value="${esc(s.url || "")}"></label>
      <label class="field"><span>Access token with the "readable" role (Admin tools → Subjects). Not the API secret.</span><input id="nsToken" type="password" required autocomplete="off"></label>
      <p class="err" id="nsErr"></p><div class="actions"><button class="btn primary">Test and save</button><button type="button" class="btn quiet" data-act="form-reset">Cancel</button></div></form>
    <form class="form" id="tgForm"><h3>Target range (mg/dL)</h3><p class="meta">Used for time in range. Default 70–180; set it from your care team's advice.</p>
      <div class="fieldrow"><label class="field"><span>Low</span><input id="tgLow" type="number" min="54" max="120" value="${s.low}"></label>
      <label class="field"><span>High</span><input id="tgHigh" type="number" min="120" max="300" value="${s.high}"></label></div>
      <div class="actions"><button class="btn">Save range</button><button type="button" class="btn quiet" data-act="form-reset">Cancel</button></div></form>
  </div></div>`;
}

/* Insulin settings by time of day (okf/domain/insulin-settings.md); used only by the meal summary */
const DOSE_KINDS = [["carb_ratio", "Carb ratio", "g of carbs per 1 u", 1, 150, "e.g. 15"], ["isf", "Correction factor", "mg/dL lowered by 1 u", 5, 500, "e.g. 50"],
  ["target", "Target BG", "mg/dL", 70, 200, "e.g. 120"]];
function doseForm() {
  const d = S.doseEdit; if (!d) return "";
  return `<form class="form" id="doseForm"><h2>Insulin settings</h2>
    <p class="meta">Used only by the meal summary when a meal is saved. Copy them from the pump or the care team's plan.
      Each starts at a time of day and runs until the next one.${S.doseUpdated ? ` Last changed ${esc(dayLabel(S.doseUpdated))}.` : ""}</p>
    ${DOSE_KINDS.map(([k, label, unit, lo, hi, ph]) => {
      const rows = d[k].length ? d[k] : [{ start: "00:00", value: "" }];
      return `<fieldset class="doseset" data-k="${k}"><legend>${label} <small>${unit}</small></legend>
        ${rows.map((b, i) => `<div class="doserow"><input type="time" class="dStart" value="${b.start}" ${i ? "" : "readonly"} aria-label="${label} from" required>
          <input type="number" class="dVal" inputmode="decimal" min="${lo}" max="${hi}" step="any" value="${b.value}" placeholder="${ph}" aria-label="${label}" required>
          ${i ? `<button type="button" class="rm" data-act="dose-rm" data-i="${i}" aria-label="Remove this time">×</button>` : `<span class="dfirst">from midnight</span>`}</div>`).join("")}
        <button type="button" class="linkbtn" data-act="dose-add">+ Add a time</button></fieldset>`; }).join("")}
    <div class="actions"><button class="btn">Save insulin settings</button></div></form>`;
}
function doseCollect() {
  const out = {};
  for (const fs of document.querySelectorAll("#doseForm .doseset")) out[fs.dataset.k] = [...fs.querySelectorAll(".doserow")].map(r => ({
    start: r.querySelector(".dStart").value, value: r.querySelector(".dVal").value === "" ? "" : +r.querySelector(".dVal").value }));
  return out;
}

async function renderSettings() {
  try { S.settings = await api("/api/settings", { parent: true }); } catch { S.settings = null; }
  try { const d = await api("/api/dose-settings"); S.doseEdit = d.settings || { carb_ratio: [], isf: [], target: [] }; S.doseUpdated = d.updated; } catch { S.doseEdit = null; }
  if (!stillOn("settings")) return;
  const st = S.settings;
  $m().innerHTML = `<div class="pad"><div class="form">
    ${st ? `<form class="form" id="offContact"><h2>Food lookup</h2>
      <label class="field"><span>Contact email sent to Open Food Facts with each lookup, so they can reach you if something goes wrong</span>
        <input id="offContactEmail" type="email" required maxlength="120" value="${esc(st.off_contact)}"></label>
      <label class="field"><span>Region for packaged food search (barcodes always work for any country)</span><select id="offCountry">${Object.entries(st.countries).map(([k, l]) =>
        `<option value="${k}" ${st.off_country === k ? "selected" : ""}>${esc(l)}</option>`).join("")}</select></label>
      <p class="meta">Default: ${esc(st.off_contact_default)}. FatSecret is ${esc(st.fatsecret)}${st.fatsecret === "set up" ? "" : ": add FAT_SECRET_CLIENT_ID and FAT_SECRET_CLIENT_SECRET to .env"}.</p>
      <div class="actions"><button class="btn">Save contact</button><button type="button" class="btn quiet" data-act="form-reset">Cancel</button></div></form>` : ""}
    ${st ? `<section class="form"><h2>Log</h2>
      <label class="check"><input type="checkbox" id="pastEdits" ${st.past_edits ? "checked" : ""}>Allow changes to earlier days</label>
      <p class="meta">On: meals and entries from earlier days can be changed, deleted or added, and each change is marked ✎ in the log and 'Changed later' in the export.
        Off: earlier days are read-only. Moving a meal or entry to another date and time works either way.</p></section>` : ""}
    <div id="doseBox">${doseForm()}</div>
    <div id="pushBox"></div>
    <div id="tidepoolBox"></div>
    <div id="accountsBox"></div>
    <section class="form"><h2>Kitchen scale</h2>
      ${Scale.supported ? `<p class="meta">Connect the scale from the plate. The app reads the standard Bluetooth weight scale and the Decent Scale.
        For another scale, the raw viewer shows what it sends: weigh a few known amounts and the format can be worked out and added.</p>
        <div class="actions"><button type="button" class="btn" data-act="scale-raw">Open raw viewer</button></div><pre class="rawlog" id="rawLog" hidden></pre>`
      : `<p class="meta">This browser can't talk to Bluetooth devices. Safari on iPad and iPhone doesn't support it; use Chrome or Edge on Android,
        ChromeOS, Windows or a Mac.${window.isSecureContext ? "" : " It also needs the secure address (the https name, or localhost)."}</p>`}</section>
    <form class="form" id="pinChange"><h2>Change parent PIN</h2>
      <div class="fieldrow"><label class="field"><span>Current PIN</span><input id="oldPin" type="password" inputmode="numeric" required></label>
      <label class="field"><span>New PIN (4 to 8 digits)</span><input id="newPin" type="password" inputmode="numeric" pattern="\\d{4,8}" required></label></div>
      <div class="actions"><button class="btn">Change PIN</button><button type="button" class="btn quiet" data-act="form-reset">Cancel</button></div></form>
    </div></div>`;
  S.accounts = null; renderAccounts(); renderPush(); renderTidepool();
}

/* ---------- Tidepool (okf/features/tidepool-sync.md) ---------- */
let confirmTpRemove = 0;
async function renderTidepool(msg = "") {
  const box = $("#tidepoolBox"); if (!box) return;
  let t; try { t = S.tp = await api("/api/tidepool", { parent: true }); } catch { return; }
  if (!t.available) { box.innerHTML = `<section class="form"><h2>Tidepool</h2><p class="meta">Tidepool is off in QA, so test meals never reach the real record.</p></section>`; return; }
  const k = t.kinds;
  box.innerHTML = `<form class="form" id="tpForm"><h2>Tidepool</h2>
    <p class="meta">Sends the log to the family's Tidepool account and keeps it in step: new, changed and deleted meals and entries follow within a minute.
      Kitchen Carbs' records sit in their own data set, so the pump's and CGM's data are never changed.</p>
    ${t.on ? `<p>Sending to <b>${esc(t.server_name)}</b> as ${esc(t.email)}. ${t.last_sync ? `Last sent ${esc(movedLabel(t.last_sync))}` : "Not sent yet"} · ${t.sent} record${t.sent === 1 ? "" : "s"} in Tidepool.</p>`
      : t.email ? `<p class="meta">Not sending. Save to start again.</p>` : ""}
    ${t.last_error ? `<p class="warn">Last try failed: ${esc(t.last_error)}</p>` : ""}
    <fieldset class="field tagpick"><legend>Server</legend><div class="seg neutral" role="radiogroup">
      ${[["test", "Test server"], ["tidepool", "Tidepool"]].map(([v, l]) => `<button type="button" data-tpserver="${v}" class="${t.server === v ? "on" : ""}" aria-pressed="${t.server === v}">${l}</button>`).join("")}</div></fieldset>
    <p class="meta">Try the test server first with a free account from external.integration.tidepool.org, then switch to Tidepool.</p>
    <div class="fieldrow"><label class="field"><span>Tidepool email</span><input id="tpEmail" type="email" autocomplete="off" maxlength="200" value="${esc(t.email)}" required></label>
      <label class="field"><span>Password</span><input id="tpPw" type="password" autocomplete="new-password" maxlength="200" placeholder="${t.password_saved ? "Saved. Type to change it" : ""}"></label></div>
    <label class="field"><span>Send to account ID (only when signing in as a caregiver; from the person's Tidepool profile link)</span><input id="tpTarget" maxlength="40" autocomplete="off" spellcheck="false" value="${esc(t.target)}"></label>
    <label class="field"><span>Send from</span><input id="tpFrom" type="date" max="${localDay()}" value="${esc(t.from)}" required></label>
    <fieldset class="field"><legend>What to send</legend>
      <label class="check"><input type="checkbox" id="tpCarbs" ${k.carbs ? "checked" : ""}><span>Carbs: each meal with its foods, and carbs typed in entries</span></label>
      <label class="check"><input type="checkbox" id="tpBg" ${k.bg ? "checked" : ""}><span>Meter BG typed on meals and entries (never CGM)</span></label>
      <label class="check"><input type="checkbox" id="tpIns" ${k.insulin ? "checked" : ""}><span>Insulin typed on meals and entries</span></label>
      <label class="field tphours"><span>Spread each basal or long-acting dose over</span><span class="unitin"><input id="tpHours" type="number" inputmode="numeric" min="1" max="168" step="1" value="${t.basal_hours}" required><span>hours</span></span></label>
      <p class="meta">Tidepool shows basal as a rate over time. 24 for a daily insulin, 42 for Tresiba, 168 for a weekly one. A dose ends early when the next long-acting dose is logged.</p>
      <p class="meta warn">Only send insulin if the pump's or pen's own data doesn't reach Tidepool, or Tidepool will count the same insulin twice.</p>
      <p class="meta">Switching a kind off removes what was sent of it.</p></fieldset>
    <p class="err" role="alert">${esc(msg)}</p>
    <div class="actions"><button class="btn primary">${t.on ? "Save" : "Connect and send"}</button>
      ${t.on ? `<button type="button" class="btn" data-act="tp-sync">Send now</button><button type="button" class="btn quiet" data-act="tp-off">Turn off</button>` : ""}
      ${t.sent || t.dataset ? `<button type="button" class="btn quiet" data-act="tp-remove">${Date.now() - confirmTpRemove < 4000 ? "Tap again to remove" : "Remove from Tidepool"}</button>` : ""}</div></form>`;
}

/* ---------- notifications (okf/features/notify-family.md, okf/architecture/web-push.md) ---------- */
const pushOk = () => window.isSecureContext && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
const deviceName = () => {
  const u = navigator.userAgent, ios = isIOS();
  const os = /Android/.test(u) ? "Android" : ios ? (/iPhone|iPod/.test(u) ? "iPhone" : "iPad") : /CrOS/.test(u) ? "Chromebook"
    : /Windows/.test(u) ? "Windows" : /Mac/.test(u) ? "Mac" : /Linux/.test(u) ? "Linux" : "";
  const br = /Edg\//.test(u) ? "Edge" : /SamsungBrowser/.test(u) ? "Samsung Internet" : /Firefox|FxiOS/.test(u) ? "Firefox"
    : /CriOS|Chrome/.test(u) ? "Chrome" : /Safari/.test(u) ? "Safari" : "";
  const app = matchMedia("(display-mode: standalone)").matches || navigator.standalone ? "installed app" : "";
  return [os, br, app].filter(Boolean).join(" · ") || "Browser";
};
async function pushReg() {   // the worker registers at load; don't wait for ever if it couldn't
  return Promise.race([navigator.serviceWorker.ready, new Promise(r => setTimeout(() => r(null), 4000))]);
}
const keyBytes = k => Uint8Array.from(atob(k.replace(/-/g, "+").replace(/_/g, "/")), c => c.charCodeAt(0));
async function renderPush(msg = "") {
  const box = $("#pushBox"); if (!box) return;
  let info, devs;
  try { [info, devs] = await Promise.all([api("/api/push"), api("/api/push/devices", { parent: true })]); } catch { return; }
  const reg = info.enabled && pushOk() ? await pushReg() : null;
  const sub = reg ? await reg.pushManager.getSubscription().catch(() => null) : null;
  const on = !!sub && devs.some(d => d.mine);
  if (!on && store.get("push", "")) store.set("push", "");
  const here = !info.enabled ? `<p class="meta">Notifications are off in QA, so test meals never reach the family's phones.</p>`
    : !pushOk() ? `<p class="meta">${isIOS() ? "On iPhone and iPad, notifications only work in the installed app: in Safari tap Share → <b>Add to Home Screen</b>, open Kitchen Carbs from the Home Screen, then turn them on here."
        : "This browser can't show notifications."}</p>`
    : Notification.permission === "denied" ? `<p class="meta warn">Notifications are blocked for Kitchen Carbs on this device. Allow them in the browser's site settings (on a phone, also Settings → Notifications), then come back here.</p>`
    : !reg ? `<p class="meta">The app's background worker isn't running on this device yet. Reload the page and try again.</p>`
    : on ? `<p>This device gets notifications.</p><div class="actions"><button type="button" class="btn" data-act="push-test">Send a test</button><button type="button" class="btn quiet" data-act="push-off">Turn off</button></div>`
    : `<div class="actions"><button type="button" class="btn primary" data-act="push-on">Notify this device</button></div>`;
  box.innerHTML = `<section class="form"><h2>Notifications</h2>
    <p class="meta">A device that turns this on gets a notification whenever a meal is saved or an entry (BG, insulin or carbs) is added on another device, with the numbers that were logged. The calculated dose is never sent.</p>
    ${here}<p class="err" role="alert">${esc(msg)}</p>
    ${devs.length ? `<span class="label">Getting notifications</span><ul class="pushlist">${devs.map(d => `<li><span><b>${esc(d.device || "Device")}</b>${d.mine ? " (this device)" : ""}<br>
        <span class="meta">${esc(d.email || "")}${d.last_error ? ` · <span class="warn">last try failed</span>` : ""}</span></span>
        <button type="button" class="btn quiet small" data-pushdel="${d.id}">Remove</button></li>`).join("")}</ul>` : ""}</section>`;
}
async function pushOn() {
  if (await Notification.requestPermission() !== "granted") return renderPush("Notifications weren't allowed on this device.");
  const [info, reg] = await Promise.all([api("/api/push"), pushReg()]);
  if (!reg) return renderPush("The app's background worker isn't running. Reload the page and try again.");
  const key = keyBytes(info.public_key);
  let sub = await reg.pushManager.getSubscription();
  try { sub = sub || await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key }); }
  catch { await sub?.unsubscribe(); sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key }); }
  const j = sub.toJSON();
  await api("/api/push/subscribe", { method: "POST", parent: true, body: { endpoint: j.endpoint, p256dh: j.keys.p256dh, auth: j.keys.auth, device: deviceName() } });
  store.set("push", j.endpoint); toast("Notifications on for this device");
}

/* ---------- Google sign-in (okf/features/sign-in.md, okf/architecture/auth.md) ---------- */
const FIREBASE_SDK = "https://www.gstatic.com/firebasejs/10.12.2";
let fb = null;
async function firebase() {   // loaded only when someone needs to sign in
  if (fb) return fb;
  const { initializeApp } = await import(`${FIREBASE_SDK}/firebase-app.js`);
  const a = await import(`${FIREBASE_SDK}/firebase-auth.js`);
  fb = { ...a, auth: a.getAuth(initializeApp(S.auth.firebase)) };
  return fb;
}
const signInError = e => ({
  "auth/unauthorized-domain": `This address (${location.hostname}) isn't in the Firebase project's Authorized domains yet.`,
  "auth/popup-closed-by-user": "The Google window was closed before signing in.",
  "auth/network-request-failed": "Couldn't reach Google. Check the internet connection.",
})[e?.code] || (e?.code?.startsWith("auth/api-key-not-valid") ? "The Firebase settings in .env don't match a Firebase project. Check FIREBASE_API_KEY."
  : e?.message || "Sign-in didn't work. Try again.");
function showSignIn(msg = "") {
  S.signedOut = true; stopScanner();
  VIEWS.forEach(x => ($("#v-" + x).hidden = true));
  $("#v-signin").hidden = false; $("#platebar").hidden = true; document.body.classList.add("signed-out");
  $("#signinView").innerHTML = `<div class="signinbox"><h1>Kitchen Carbs</h1>
    <p>Sign in once on this device with a family Google account. It stays signed in.</p>
    <button class="btn primary big" id="gSignIn">Sign in with Google</button>
    <p class="err" id="signinErr" role="alert">${esc(msg)}</p>
    <p><button class="linkbtn" id="codeSignIn">Sign in with a code instead</button><br><span class="meta">For kiosks and dashboards where Google won't open.</span></p>
    <p class="meta">Not on the family list? Ask a parent to add your Google account in Manage → Settings.</p></div>`;
  if (S.auth?.enabled && !msg) finishRedirect();
}
async function finishRedirect() {   // coming back from a full-page Google sign-in
  try { const f = await firebase(), r = await f.getRedirectResult(f.auth); if (r?.user) await finishSignIn(r.user); }
  catch (e) { const el = $("#signinErr"); if (el) el.textContent = signInError(e); }
}
async function finishSignIn(user) {
  const id_token = await user.getIdToken();
  try { await api("/api/auth/session", { method: "POST", body: { id_token } }); }
  finally { await fb.signOut(fb.auth).catch(() => { }); }   // from here on the server's cookie keeps the device signed in
  location.reload();
}
/* Sign in with a code: this device shows a code, a parent approves it on a signed-in device (okf/features/sign-in.md) */
let codeWait = null;
async function startCodeSignIn() {
  clearInterval(codeWait);
  const box = $("#signinView .signinbox");
  let d;
  try { d = await api("/api/auth/device", { method: "POST" }); }
  catch (err) { $("#signinErr").textContent = err.message; return; }
  const ends = Date.now() + d.expires_in * 1000;
  box.innerHTML = `<h1>Kitchen Carbs</h1>
    <p>On a phone or tablet that's already signed in, open <b>Manage → Settings → Sign in another device</b> and type:</p>
    <p class="devcode" aria-label="Code ${d.code.split("").join(" ")}">${esc(d.code)}</p>
    <p class="meta" id="codeLeft"></p><p class="err" id="signinErr" role="alert"></p>
    <p><button class="linkbtn" id="codeBack">Back to Google sign-in</button></p>`;
  const tick = async () => {
    const left = Math.max(0, Math.round((ends - Date.now()) / 1000));
    $("#codeLeft").textContent = `Waiting for approval · ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")} left`;
    let r; try { r = await api(`/api/auth/device/${encodeURIComponent(d.poll)}`); } catch { return; }   // try again next tick
    if (r.state === "approved") { clearInterval(codeWait); location.reload(); }
    else if (r.state === "expired" || !left) {
      clearInterval(codeWait);
      box.querySelector(".devcode").classList.add("used");
      $("#codeLeft").innerHTML = `The code ran out. <button class="linkbtn" id="codeSignIn">Show a new code</button>`;
    }
  };
  codeWait = setInterval(tick, 2000); tick();
}
document.addEventListener("click", e => {
  if (e.target.id === "codeSignIn") startCodeSignIn();
  else if (e.target.id === "codeBack") { clearInterval(codeWait); showSignIn(); }
});
document.addEventListener("click", async e => {
  if (e.target.id !== "gSignIn") return;
  const btn = e.target, err = $("#signinErr"); btn.disabled = true; err.textContent = "";
  try {
    const f = await firebase(), provider = new f.GoogleAuthProvider();
    provider.setCustomParameters({ prompt: "select_account" });
    try { await finishSignIn((await f.signInWithPopup(f.auth, provider)).user); }
    catch (e2) {
      if (["auth/popup-blocked", "auth/operation-not-supported-in-this-environment"].includes(e2.code)) return f.signInWithRedirect(f.auth, provider);
      throw e2;
    }
  } catch (e3) { err.textContent = e3 instanceof ApiError ? e3.message : signInError(e3); btn.disabled = false; }
});
async function renderAccounts() {
  const box = $("#accountsBox"); if (!box) return;
  try { S.accounts = S.accounts || await api("/api/accounts", { parent: true }); } catch { return; }
  const a = S.accounts;
  box.innerHTML = `<form class="form" id="accountsForm"><h2>Family accounts</h2>
    ${a.enabled ? `<p>Signed in on this device as <b>${esc(a.me || "?")}</b>. <button type="button" class="linkbtn" data-act="sign-out">Sign out this device</button></p>`
      : `<p class="meta">Google sign-in is off on this server: no Firebase project is set in .env. The list below is used once it is.</p>`}
    <label class="field"><span>Google accounts allowed to use the app, one per line</span>
      <textarea id="accEmails" rows="4" spellcheck="false" autocapitalize="off">${esc(a.emails.join("\n"))}</textarea></label>
    <p class="meta">Taking an account off the list signs out its devices straight away.${Object.keys(a.devices).length ? " Signed-in devices: " + Object.entries(a.devices).map(([e, n]) => `${esc(e)} ${n}`).join(", ") + "." : ""}</p>
    <div class="actions"><button class="btn">Save accounts</button><button type="button" class="btn quiet" data-act="form-reset">Cancel</button>
      ${a.enabled ? `<button type="button" class="btn quiet" data-act="sign-out-others">Sign out all other devices</button>` : ""}</div></form>
    ${a.enabled ? `<form class="form" id="approveDevice"><h2>Sign in another device</h2>
      <p class="meta">On the kiosk or dashboard, choose 'Sign in with a code', then type the code it shows. It will be signed in as ${esc(a.me || "you")}.</p>
      <div class="fieldrow"><label class="field"><span>Code</span><input id="devCode" required maxlength="12" autocomplete="off" autocapitalize="characters" spellcheck="false" placeholder="ABCD-EFGH"></label></div>
      <div class="actions"><button class="btn">Approve</button></div></form>` : ""}`;
}

/* ---------- install on a phone (okf/features/install-app.md) ---------- */
let installEvt = null;
addEventListener("beforeinstallprompt", e => { e.preventDefault(); installEvt = e; if ($("#installCard")) showInstall(); });
addEventListener("appinstalled", () => { store.set("installAsked", true); $("#installCard")?.remove(); });
if ("serviceWorker" in navigator && window.isSecureContext) navigator.serviceWorker.register("sw.js").catch(() => { });
const isIOS = () => /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
function offerInstall() {
  const phone = matchMedia("(pointer: coarse)").matches && Math.min(screen.width, screen.height) < 600;
  const installed = matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  if (!phone || installed || window.top !== window || store.get("installAsked", false)) return;
  setTimeout(showInstall, 1500);   // gives Chrome a moment to say it can install
}
function showInstall() {
  let card = $("#installCard");
  if (!card) { card = document.createElement("aside"); card.id = "installCard"; card.className = "installcard"; card.setAttribute("aria-label", "Install the app"); document.body.append(card); }
  const how = installEvt ? "" : isIOS()
    ? `<p class="meta">Tap <b>Share</b> <span aria-hidden="true">⎙</span> at the bottom of Safari, then <b>Add to Home Screen</b>.</p>`
    : `<p class="meta">Open the browser menu <span aria-hidden="true">⋮</span> and choose <b>Install app</b> or <b>Add to Home screen</b>.</p>`;
  card.innerHTML = `<img src="icon-192.png" alt=""><div><b>Install Kitchen Carbs on this phone?</b>
      <p>It opens from the home screen like an app, full screen.</p>${how}</div>
    <div class="ibtns">${installEvt ? `<button class="btn primary small" data-install="yes">Install</button>` : ""}
      <button class="btn quiet small" data-install="no">${installEvt ? "Not now" : "Got it"}</button></div>`;
}
document.addEventListener("click", async e => {
  const b = e.target.closest("[data-install]"); if (!b) return;
  store.set("installAsked", true);   // asked once, whatever the answer
  if (b.dataset.install === "yes" && installEvt) { installEvt.prompt(); await installEvt.userChoice.catch(() => { }); installEvt = null; }
  $("#installCard")?.remove();
});

/* ---------- start ---------- */
async function start() {
  try { S.auth = await api("/api/auth/config"); } catch { S.auth = null; }
  try { S.session = await api("/api/session"); document.title = S.session.env === "prod" ? "Kitchen Carbs" : `Kitchen Carbs (${S.session.env.toUpperCase()})`; }
  catch (err) { S.session = null; if (err.signin) return; }   // the sign-in screen is showing
  await loadFoods(); pickMealFilter();
  renderStatus(); route(); watchJobs(); offerInstall();
  syncQueue();
  setInterval(async () => {
    syncQueue();
    try { S.session = await api("/api/session"); } catch { }
  }, 30000);
}
start();
