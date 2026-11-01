// Records the Kitchen Carbs demo reels from the demo server (made-up data, no keys, sign-in off); run by record.sh.
//   node reels.js <outdir> [reel ...]   writes <reel>.webm and <reel>.json (when each caption appeared)
const { chromium, devices } = require("playwright");
const fs = require("fs");
const BASE = "http://127.0.0.1:8095";
const TABLET = { viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1 };
const PHONE = { ...devices["Pixel 7"], viewport: { width: 412, height: 860 }, deviceScaleFactor: 1 };

const OVERLAY = () => {
  const css = `#democursor{position:fixed;left:0;top:0;width:26px;height:26px;margin:-4px 0 0 -4px;z-index:2147483647;pointer-events:none;transition:transform .08s}
    #democursor svg{filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))}
    #democursor.down{transform:scale(.85)}
    .demoripple{position:fixed;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;border:3px solid rgba(31,58,95,.7);z-index:2147483646;pointer-events:none;animation:demorip .5s ease-out forwards}
    @keyframes demorip{from{transform:scale(.3);opacity:1}to{transform:scale(1.4);opacity:0}}
    #democap{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);max-width:min(860px,92vw);z-index:2147483645;pointer-events:none;
      background:rgba(28,32,38,.88);color:#fff;font:600 19px/1.35 "Kitchen Sans",sans-serif;padding:11px 20px;border-radius:12px;text-align:center;
      box-shadow:0 6px 24px rgba(0,0,0,.25);transition:opacity .35s}
    #democap.off{opacity:0}
    @media (max-width:500px){#democap{font-size:15px;bottom:auto;top:58px;padding:9px 14px;width:max-content}}`;
  const add = () => {
    if (document.getElementById("democursor")) return;
    const s = document.createElement("style"); s.textContent = css; document.head.appendChild(s);
    const c = document.createElement("div"); c.id = "democursor";
    c.innerHTML = `<svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 2l16 9.5-7 1.6-3.6 6.9z" fill="#1f2a37" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
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

function helpers(p, marks) {
  let x = 640, y = 400; const t0 = Date.now();
  const wait = ms => p.waitForTimeout(ms);
  const box = async target => {
    const l = typeof target === "string" ? p.locator(target).first() : target;
    await l.scrollIntoViewIfNeeded(); await wait(150);
    return l.boundingBox();
  };
  const move = async (tx, ty, ms = 600) => {
    const steps = Math.max(8, Math.round(ms / 16));
    for (let i = 1; i <= steps; i++) {
      const t = i / steps, e = t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      await p.mouse.move(x + (tx - x) * e, y + (ty - y) * e);
    }
    x = tx; y = ty;
  };
  const moveTo = async (target, ms) => { const b = await box(target); await move(b.x + b.width / 2, b.y + b.height / 2, ms); return b; };
  const click = async (target, after = 700) => { await moveTo(target); await wait(180); await p.mouse.down(); await wait(90); await p.mouse.up(); await wait(after); };
  const type = async (target, text, after = 500) => { await click(target, 200); await p.keyboard.press("Control+A"); await p.keyboard.type(text, { delay: 90 }); await wait(after); };
  const cap = async (text, hold = 0) => { marks.push({ t: (Date.now() - t0) / 1000, text }); await p.evaluate(t => { const c = document.getElementById("democap"); if (!c) return;
    if (!t) { c.classList.add("off"); return; } c.textContent = t; c.classList.remove("off"); }, text); if (hold) await wait(hold); };
  const drag = async (target, fromFrac, toFrac, ms = 1200) => {
    const b = await box(target); const yy = b.y + b.height / 2;
    await move(b.x + b.width * fromFrac, yy); await wait(200); await p.mouse.down();
    await move(b.x + b.width * toFrac, yy, ms); await wait(150); await p.mouse.up(); await wait(500);
  };
  const scroll = async (sel, dy, ms = 900) => { const steps = Math.round(ms / 30);
    for (let i = 0; i < steps; i++) { await p.evaluate(([s, d]) => { const el = s ? document.querySelector(s) : document.scrollingElement; if (el) el.scrollBy(0, d); }, [sel, dy / steps]); await wait(30); } };
  return { wait, move, moveTo, click, type, cap, drag, scroll };
}

const REELS = {
  async plate(p, h) {
    await p.goto(BASE + "/#foods"); await h.wait(1500);
    await h.cap("Foods are photo cards, sorted by tags like Breakfast, Lunch and Dinner", 1800);
    await h.click("[data-filter=all]", 900);
    await h.cap("Search finds a food, in this tag and beyond it");
    await h.type("#q", "cheer", 900);
    await h.click("[data-addcard=multi-grain-cheerios]", 1000);
    await h.click("#q", 100); await p.keyboard.press("Control+A"); await p.keyboard.press("Backspace"); await p.locator("#q").blur(); await h.wait(700);
    await h.cap("Tap a card to add it. Foods with several portions ask which one");
    await h.click("[data-addcard=honeycrisp-apple-slices]", 900);
    await h.click("#portionDialog [data-pick] >> nth=1", 1100);
    await h.cap("Set the real weight with the slider, or a Bluetooth kitchen scale");
    await h.drag("#platePane .pitem >> nth=0 >> .wRange", 0.3276, 0.42, 1400);
    await h.wait(600);
    await h.cap("The plate adds up the carbs as you go", 2000);
    await h.cap("");
  },
  async summary(p, h) {
    await p.goto(BASE + "/#foods"); await h.wait(1200);
    if (!(await p.locator("#platePane .pitem").count())) {
      await p.click("[data-filter=all]"); await p.click("[data-addcard=multi-grain-cheerios]"); await h.wait(400);
      await p.click("[data-addcard=honeycrisp-apple-slices]"); await p.click("#portionDialog [data-pick] >> nth=1"); await h.wait(600);
    }
    await h.cap("Save to log opens the meal summary");
    await h.click(p.getByText("Save to log").first(), 1400);
    await h.cap("Pick the meal's date and time if it wasn't just now");
    const tb = await h.moveTo("#sumAt", 600);
    await h.move(tb.x + 22, tb.y + tb.height / 2, 300); await p.mouse.down(); await p.mouse.up(); await h.wait(250);
    const at = new Date(Date.now() - 20 * 60000), hh = at.getHours(), pad = n => String(n).padStart(2, "0");
    await p.keyboard.type(`${pad((hh + 11) % 12 + 1)}${pad(at.getMinutes())}${hh < 12 ? "A" : "P"}`, { delay: 140 }); await h.wait(900);
    await h.cap("BG comes from the CGM for a meal right now. For an earlier one, type the meter reading");
    await h.type("#sumBg", "165", 1400);
    await h.moveTo("#sumCalc", 700);
    await h.cap("A dose is worked out from the parent's own ratios, shown here only, never stored", 2800);
    await h.cap("Record what was actually given, and when");
    await h.type("#doseDialog .dIns", "3.5", 700);
    await h.click("#doseDialog [data-dwhen=before]", 600);
    await h.click("#doseDialog [data-sum=save]", 1800);
    await h.cap("Saved to the log, and parents' phones get a notification", 2200);
    await h.cap("");
  },
  async log(p, h) {
    await p.goto(BASE + "/#log"); await h.wait(1600);
    await h.cap("The log shows each day: carbs, insulin and time in range from the CGM", 2400);
    await h.click("[data-period='7']", 1400);
    await h.click("[data-period=day]", 600);
    await h.cap("Go back a day and open a meal");
    await h.click("[data-day='-1']", 1200);
    await h.click("#logList .lrow[data-meal] >> nth=1", 1500);
    await h.cap("Each meal shows its glucose curve for the next three hours", 2400);
    await h.cap("Change what was eaten or add a comment. A Save bar appears");
    await h.click("#mealDetail .eatseg [data-eaten=most]", 900);
    await h.type("#cmtText", "Left some pasta, tired after practice", 900);
    await h.click(".savebar .btn.primary", 1500);
    await h.cap("Manual entries add juice, a meter BG or a long-acting dose", 1200);
    await h.click("[data-act=add-entry]", 1800);
    await h.cap("");
  },
  async manage(p, h) {
    await p.goto(BASE + "/#manage"); await h.wait(1600);
    await h.cap("Manage (behind a parent PIN) holds the foods and their photos", 2000);
    await h.click("[data-mfood='cinnamon-toast-crunch-general-mills']", 1400);
    await h.cap("Each food keeps its source, carbs per serving and checked portions", 2200);
    await h.scroll("#v-manage", 520, 1400); await h.wait(600);
    await h.cap("Portion photos are styled by Gemini to match the family's own plates, then checked by a parent", 2800);
    await h.scroll("#v-manage", 400, 900); await h.wait(900);
    await h.click("[data-mtab=style]", 1600);
    await h.cap("The photo style: the family's plate, bowl and counter, and the prompt", 2400);
    await h.click("[data-mtab=foods]", 1200);
    await h.cap("");
  },
  async settings(p, h) {
    await p.goto(BASE + "/#manage"); await h.wait(1200);
    await h.click("[data-mtab=settings]", 1400);
    await h.cap("Settings: food lookup, the log's rules, and the ratios the meal summary uses", 2400);
    await h.scroll("#v-manage", 900, 2000); await h.wait(500);
    await h.cap("Notifications to parents' phones, and Tidepool sync for the care team", 2200);
    await h.moveTo("#tidepoolBox", 800);
    await h.scroll("#v-manage", 500, 1200); await h.wait(1500);
    await h.cap("");
  },
  async phone(p, h) {
    await p.goto(BASE + "/#foods"); await h.wait(1500);
    await h.cap("On a phone too");
    await h.click("[data-filter=all]", 700);
    await h.click("[data-addcard=rice-chex-general-mills]", 900);
    await h.click("[data-addcard='d-anjou-pears']", 900);
    await h.cap("Open the plate, set the weights");
    await h.click("#platebar .btn", 1400);
    await h.drag("#plateView .pitem >> nth=0 >> .wRange", 0.33, 0.25, 1100);
    await h.cap("Then the log, wherever you are");
    await h.click("#tabs [data-v=log]", 1600);
    await h.click("#logList .lrow >> nth=0", 1600);
    await h.scroll(null, 500, 1200); await h.wait(800);
    await h.cap("");
  },
};

(async () => {
  const [out, ...want] = process.argv.slice(2);
  const names = want.length ? want : Object.keys(REELS);
  const b = await chromium.launch();
  for (const n of names) {
    const opt = n === "phone" ? PHONE : TABLET;
    const ctx = await b.newContext({ ...opt, permissions: ["notifications"], recordVideo: { dir: out + "/raw", size: opt.viewport } });
    const p = await ctx.newPage(); const errs = []; p.on("pageerror", e => errs.push(e.message));
    await p.addInitScript(OVERLAY);
    const marks = []; const h = helpers(p, marks);
    try { await REELS[n](p, h); } catch (e) { console.log(n, "FAILED", e.message.split("\n")[0]); await p.screenshot({ path: `${out}/${n}-fail.png` }); }
    const v = p.video(); await ctx.close();
    fs.renameSync(await v.path(), `${out}/${n}.webm`); fs.writeFileSync(`${out}/${n}.json`, JSON.stringify(marks, null, 1));
    console.log(n, "done", errs.length ? errs : "");
  }
  await b.close();
})();
