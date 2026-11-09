// Records the Kitchen Carbs demo reels from the demo server (made-up data, no keys, sign-in off); run by record.sh.
//   node reels.js <outdir> [reel ...]   writes <reel>.webm and <reel>.json: when each caption appeared, and the
//   named clips the sizzle reel is cut from (build.py). A clip starts once its caption has faded in and ends on a
//   still frame, so the sizzle never cuts mid-scroll, mid-fade or mid-click.
const { chromium, devices } = require("playwright");
const fs = require("fs");
const BASE = "http://127.0.0.1:8095";
// Playwright's video is always at CSS pixels (a larger size only pads it), so the page is recorded at 1x
const TABLET = { viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1 };
const PHONE = { ...devices["Pixel 7"], viewport: { width: 412, height: 860 }, deviceScaleFactor: 1 };

const OVERLAY = () => {
  const css = `#democursor{position:fixed;left:0;top:0;width:26px;height:26px;margin:-4px 0 0 -4px;z-index:2147483647;pointer-events:none;transition:transform .08s;will-change:left,top}
    #democursor svg{filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))}
    #democursor.down{transform:scale(.85)}
    .demoripple{position:fixed;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;border:3px solid rgba(31,58,95,.7);z-index:2147483646;pointer-events:none;animation:demorip .5s ease-out forwards}
    @keyframes demorip{from{transform:scale(.3);opacity:1}to{transform:scale(1.4);opacity:0}}
    #democap{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);max-width:min(860px,92vw);z-index:2147483645;pointer-events:none;
      background:rgba(28,32,38,.88);color:#fff;font:600 19px/1.35 "Kitchen Sans",sans-serif;padding:11px 20px;border-radius:12px;text-align:center;
      box-shadow:0 6px 24px rgba(0,0,0,.25);transition:opacity .35s}
    #democap.off{opacity:0}
    @media (max-width:500px){#democap{font-size:15px;bottom:auto;top:58px;padding:9px 14px;width:max-content}}
    html{scroll-behavior:auto!important}`;
  const add = () => {
    if (document.getElementById("democursor")) return;
    const s = document.createElement("style"); s.textContent = css; document.head.appendChild(s);
    const c = document.createElement("div"); c.id = "democursor";
    c.innerHTML = `<svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 2l16 9.5-7 1.6-3.6 6.9z" fill="#1f2a37" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
    c.style.left = (window.__demoX ?? 640) + "px"; c.style.top = (window.__demoY ?? 400) + "px";
    document.body.appendChild(c);
    const cap = document.createElement("div"); cap.id = "democap"; cap.className = "off"; document.body.appendChild(cap);
    addEventListener("mousemove", e => { c.style.left = e.clientX + "px"; c.style.top = e.clientY + "px"; }, true);
    addEventListener("mousedown", e => { c.classList.add("down"); const r = document.createElement("div"); r.className = "demoripple";
      r.style.left = e.clientX + "px"; r.style.top = e.clientY + "px"; document.body.appendChild(r); setTimeout(() => r.remove(), 600); }, true);
    addEventListener("mouseup", () => c.classList.remove("down"), true);
  };
  if (document.readyState === "loading") addEventListener("DOMContentLoaded", add); else add();
  try { localStorage.setItem("kc.installAsked", "true"); sessionStorage.setItem("kc.pin", "1234"); } catch {}
};

function helpers(p, log, t0) {
  let x = 640, y = 400;
  const now = () => (Date.now() - t0) / 1000;
  const wait = ms => p.waitForTimeout(ms);
  // Smoothly scroll whatever holds the element (the page or a scrolling pane) until it is in view, then settle.
  const reveal = async l => {
    const ms = await l.evaluate(el => {
      const r = el.getBoundingClientRect();
      let s = el.parentElement;
      while (s && !(/(auto|scroll)/.test(getComputedStyle(s).overflowY) && s.scrollHeight > s.clientHeight)) s = s.parentElement;
      const sc = s || document.scrollingElement, top = s ? s.getBoundingClientRect().top : 0, h = s ? s.clientHeight : innerHeight;
      const margin = 90;   // clear of the caption
      if (r.top >= top + 10 && r.bottom <= top + h - margin) return 0;
      const dy = Math.max(-sc.scrollTop, Math.min(sc.scrollHeight - sc.clientHeight - sc.scrollTop, r.top - top - (h - r.height) / 2.4));
      if (Math.abs(dy) < 2) return 0;
      const from = sc.scrollTop, d = Math.min(900, 350 + Math.abs(dy) * 0.6), t0 = performance.now();
      const step = t => { const k = Math.min(1, (t - t0) / d), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
        sc.scrollTop = from + dy * e; if (k < 1) requestAnimationFrame(step); };
      requestAnimationFrame(step); return d;
    });
    if (ms) await wait(ms + 200);
  };
  const box = async target => {
    const l = typeof target === "string" ? p.locator(target).first() : target;
    await l.waitFor({ state: "visible" }); await reveal(l);
    return l.boundingBox();
  };
  // Real-time cursor motion: one step a frame, eased, so it moves at the same speed however busy the machine is.
  const move = async (tx, ty, ms = 600) => {
    const start = Date.now(), fx = x, fy = y;
    for (;;) {
      const t = Math.min(1, (Date.now() - start) / ms), e = t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      await p.mouse.move(fx + (tx - fx) * e, fy + (ty - fy) * e);
      if (t >= 1) break;
      await wait(16);
    }
    x = tx; y = ty;
    await p.evaluate(([a, b]) => { window.__demoX = a; window.__demoY = b; }, [x, y]);
  };
  const moveTo = async (target, ms) => { const b = await box(target); const d = Math.hypot(b.x + b.width / 2 - x, b.y + b.height / 2 - y);
    await move(b.x + b.width / 2, b.y + b.height / 2, ms ?? Math.min(900, 300 + d * 0.8)); return b; };
  const click = async (target, after = 700) => { await moveTo(target); await wait(160); await p.mouse.down(); await wait(90); await p.mouse.up(); await wait(after); };
  const type = async (target, text, after = 500) => { await click(target, 200); await p.keyboard.press("Control+A"); await p.keyboard.type(text, { delay: 85 }); await wait(after); };
  const cap = async (text, hold = 0) => { log.caps.push({ t: now(), text }); await p.evaluate(t => { const c = document.getElementById("democap"); if (!c) return;
    if (!t) { c.classList.add("off"); return; } c.textContent = t; c.classList.remove("off"); }, text); if (hold) await wait(hold); };
  // A clip for the sizzle: its caption fades in first, and it ends after a still beat
  const clip = async (name, text) => { if (text != null) { await cap(text); await wait(450); } log.clips[name] = { start: now() }; };
  const end = async (name, hold = 900) => { await wait(hold); log.clips[name].end = now(); };
  const drag = async (target, fromFrac, toFrac, ms = 1200) => {
    const b = await box(target); const yy = b.y + b.height / 2;
    await move(b.x + b.width * fromFrac, yy); await wait(200); await p.mouse.down();
    await move(b.x + b.width * toFrac, yy, ms); await wait(150); await p.mouse.up(); await wait(500);
  };
  const scrollBy = async (target, dy) => { const l = p.locator(target).first(); await l.evaluate((el, d) => {
    let s = el; while (s && !(/(auto|scroll)/.test(getComputedStyle(s).overflowY) && s.scrollHeight > s.clientHeight)) s = s.parentElement;
    const sc = s || document.scrollingElement, from = sc.scrollTop, to = Math.max(0, Math.min(sc.scrollHeight - sc.clientHeight, from + d)), t0 = performance.now(), dur = 1100;
    const step = t => { const k = Math.min(1, (t - t0) / dur), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      sc.scrollTop = from + (to - from) * e; if (k < 1) requestAnimationFrame(step); }; requestAnimationFrame(step); }, dy); await wait(1300); };
  return { wait, move, moveTo, click, type, cap, clip, end, drag, scrollBy };
}

// Open a page and wait until its photos have loaded, so nothing pops in on camera.
async function open(p, hash, h) {
  await p.goto(BASE + "/" + hash); await p.waitForLoadState("networkidle");
  await p.evaluate(() => Promise.all([...document.images].filter(i => !i.complete).map(i => new Promise(r => { i.onload = i.onerror = r; }))));
  await h.wait(500);
}

const REELS = {
  async plate(p, h) {
    await open(p, "#foods", h);
    await h.cap("Foods are photo cards, sorted by tags like Breakfast, Lunch and Dinner", 1800);
    await h.click("[data-filter=all]", 900);
    await h.clip("search", "Search finds a food, in this tag and beyond it");
    await h.type("#q", "cheer", 900);
    await h.click("[data-addcard=multi-grain-cheerios]", 1000);
    await h.end("search", 300);
    await h.click("#q", 100); await p.keyboard.press("Control+A"); await p.keyboard.press("Backspace"); await p.locator("#q").blur(); await h.wait(900);
    await h.clip("portion", "Tap a card to add it. Foods with several portions ask which one");
    await h.click("[data-addcard=honeycrisp-apple-slices]", 900);
    await h.click("#portionDialog [data-pick] >> nth=1", 1100);
    await h.end("portion", 400);
    await h.clip("weigh", "Set the real weight with the slider, or a Bluetooth kitchen scale");
    await h.drag("#platePane .pitem >> nth=0 >> .wRange", 0.3276, 0.42, 1400);
    await h.wait(400);
    await h.cap("The plate adds up the carbs as you go", 1800);
    await h.end("weigh", 200);
    await h.cap("");
  },
  async summary(p, h) {
    await open(p, "#foods", h);
    if (!(await p.locator("#platePane .pitem").count())) {
      await p.click("[data-filter=all]"); await p.click("[data-addcard=multi-grain-cheerios]"); await h.wait(400);
      await p.click("[data-addcard=honeycrisp-apple-slices]"); await p.click("#portionDialog [data-pick] >> nth=1"); await h.wait(600);
    }
    await h.clip("open", "Save to log opens the meal summary");
    await h.click(p.getByText("Save to log").first(), 1400);
    await h.end("open", 300);
    await h.cap("Pick the meal's date and time if it wasn't just now");
    const tb = await h.moveTo("#sumAt", 600);
    await h.move(tb.x + 22, tb.y + tb.height / 2, 300); await p.mouse.down(); await p.mouse.up(); await h.wait(250);
    const at = new Date(Date.now() - 20 * 60000), hh = at.getHours(), pad = n => String(n).padStart(2, "0");
    await p.keyboard.type(`${pad((hh + 11) % 12 + 1)}${pad(at.getMinutes())}${hh < 12 ? "A" : "P"}`, { delay: 140 }); await h.wait(900);
    await h.clip("bg", "BG comes from the CGM for a meal right now. For an earlier one, type the meter reading");
    await h.type("#sumBg", "165", 1200);
    await h.moveTo("#sumCalc", 700);
    await h.cap("A dose is worked out from the parent's own ratios, shown here only, never stored", 2600);
    await h.end("bg", 200);
    await h.clip("given", "Record what was actually given, and when");
    await h.type("#doseDialog .dIns", "3.5", 700);
    await h.type("#doseDialog .dMin", "15", 600);
    await h.click("#doseDialog [data-sum=save]", 1500);
    await h.cap("Saved to the log, and parents' phones get a notification", 1500);
    await h.end("given", 200);
    await h.cap("");
  },
  async log(p, h) {
    await open(p, "#log", h);
    await h.clip("day", "The log shows each day: carbs, insulin and time in range from the CGM");
    await h.wait(900);
    await h.click("[data-act=stats]", 1000);
    await h.click("[data-period='7']", 1300);
    await h.click("[data-period=day]", 500);
    await h.end("day", 300);
    await h.clip("meal", "Go back a day and open a meal: its glucose for the next three hours");
    await h.click("[data-day='-1']", 1100);
    await h.click("#logList .lrow[data-meal] >> nth=1", 1300);
    await h.moveTo("#gBox", 700);
    await h.end("meal", 1400);
    await h.clip("edit", "Note how much was eaten or add a comment. A Save bar appears");
    await h.click("#mealDetail .eatseg [data-eaten=most]", 900);
    await h.type("#cmtText", "Left some pasta", 600);
    await h.click(".savebar .btn.primary", 1200);
    await h.end("edit", 300);
    await h.cap("Manual entries add juice, a meter BG or a long-acting dose", 1200);
    await h.click("[data-act=add-entry]", 1800);
    await h.cap("");
  },
  async after(p, h) {
    await open(p, "#log", h);
    await h.click(".aftlink", 1200);
    await h.clip("after", "After meals lines up every meal's glucose for three hours, to share with the care team");
    await h.wait(1600);
    await h.click("[data-afmeals=breakfast]", 1300);
    await h.cap("Look at just breakfasts, lunches or dinners");
    await h.click("[data-afmeals=dinner]", 1300);
    await h.click("[data-afmode=mgdl]", 1500);
    await h.end("after", 300);
    await h.cap("");
  },
  async manage(p, h) {
    await open(p, "#manage", h);
    await h.clip("food", "Manage (behind a parent PIN) holds the foods, with their checked carbs and portions");
    await h.wait(900);
    await h.click("[data-mfood='cinnamon-toast-crunch-general-mills']", 1500);
    await h.end("food", 300);
    await h.clip("photos", "Portion photos are styled by Gemini to match the family's own plates, then checked by a parent");
    await h.moveTo("table.portions img", 800);
    await h.end("photos", 1800);
    await h.click("[data-mtab=settings]", 1200);
    await h.cap("The photo style: the family's plate, bowl and counter, and the prompt");
    await h.moveTo("#set-photo-style", 800); await h.wait(2000);
    await h.cap("");
  },
  async settings(p, h) {
    await open(p, "#manage", h);
    await h.click("[data-mtab=settings]", 1400);
    await h.clip("settings", "Settings: food lookup, the log's rules, and the ratios the meal summary uses");
    await h.wait(1600);
    await h.cap("Notifications to parents' phones, and Tidepool sync for the care team");
    await h.moveTo("#tidepoolBox", 800);
    await h.end("settings", 1600);
    await h.cap("");
  },
  async phone(p, h) {
    await open(p, "#foods", h);
    await h.clip("phone", "On a phone too");
    await h.click("[data-filter=all]", 700);
    await h.click("[data-addcard=rice-chex-general-mills]", 600);
    await h.click("[data-addcard='d-anjou-pears']", 600);
    await h.cap("Open the plate, set the weights");
    await h.click("#platebar .btn", 1300);
    await h.drag("#plateView .pitem >> nth=0 >> .wRange", 0.33, 0.25, 1100);
    await h.cap("Then the log, wherever you are");
    await h.click("#tabs [data-v=log]", 1500);
    await h.click("#logList .lrow >> nth=0", 1500);
    await h.end("phone", 600);
    await h.cap("");
  },
};

(async () => {
  const [out, ...want] = process.argv.slice(2);
  const names = want.length ? want : Object.keys(REELS);
  const b = await chromium.launch();
  let failed = false;
  for (const n of names) {
    const opt = n === "phone" ? PHONE : TABLET;
    const ctx = await b.newContext({ ...opt, permissions: ["notifications"], recordVideo: { dir: out + "/raw", size: opt.viewport } });
    const t0 = Date.now();   // the video starts with the page
    const p = await ctx.newPage(); const errs = []; p.on("pageerror", e => errs.push(e.message));
    await p.addInitScript(OVERLAY);
    const log = { caps: [], clips: {} }; const h = helpers(p, log, t0);
    try { await REELS[n](p, h); } catch (e) { failed = true; console.log(n, "FAILED", e.message.split("\n")[0]); await p.screenshot({ path: `${out}/${n}-fail.png` }); }
    const v = p.video(); await ctx.close();
    fs.renameSync(await v.path(), `${out}/${n}.webm`); fs.writeFileSync(`${out}/${n}.json`, JSON.stringify(log, null, 1));
    console.log(n, "done", errs.length ? errs : "");
  }
  await b.close();
  process.exit(failed ? 1 : 0);
})();
