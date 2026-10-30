/* Bluetooth kitchen scale (okf/features/kitchen-scale.md, okf/architecture/web-bluetooth.md).
   The reading lives only on this page; nothing here changes the plate (okf/rules/scale-reading-needs-tap.md). */
const Scale = (() => {
  const uuid = n => `0000${n.toString(16).padStart(4, "0")}-0000-1000-8000-00805f9b34fb`;
  const hex = dv => [...new Uint8Array(dv.buffer, dv.byteOffset, dv.byteLength)].map(b => b.toString(16).padStart(2, "0")).join(" ");
  const withXor = b => { b.push(b.reduce((a, x) => a ^ x, 0)); return new Uint8Array(b); };

  const DRIVERS = [
    { id: "sig", name: "Bluetooth weight scale", service: 0x181d,
      async start(svc, on) {
        const ch = await svc.getCharacteristic(0x2a9d);
        ch.addEventListener("characteristicvaluechanged", e => {
          const v = e.target.value, imperial = v.getUint8(0) & 1, raw = v.getUint16(1, true);
          if (raw === 0xffff) return;   // 'measurement unsuccessful'
          on(imperial ? raw * 0.01 * 453.59237 : raw * 5, null);   // kg at 0.005, lb at 0.01
        });
        await ch.startNotifications();
        return {};
      } },
    { id: "decent", name: "Decent Scale", service: 0xfff0,
      async start(svc, on) {
        const rx = await svc.getCharacteristic(0xfff4), tx = await svc.getCharacteristic(0x36f5);
        rx.addEventListener("characteristicvaluechanged", e => {
          const v = e.target.value;
          if (v.byteLength < 7 || v.getUint8(0) !== 0x03) return;
          const type = v.getUint8(1);
          if (type === 0xce || type === 0xca) on(v.getInt16(2, false) / 10, type === 0xce);
        });
        await rx.startNotifications();
        const tare = () => tx.writeValueWithoutResponse ? tx.writeValueWithoutResponse(withXor([0x03, 0x0f, 0, 0, 0, 1]))
                                                        : tx.writeValue(withXor([0x03, 0x0f, 0, 0, 0, 1]));
        await tare();   // the scale only starts sending weight after a command
        return { tare };
      } },
    { id: "esn00", name: "Etekcity Nutrition Scale", service: 0x1910,
      async start(svc, on) {
        const rx = await svc.getCharacteristic(0x2c12), tx = await svc.getCharacteristic(0x2c11);
        const send = (type, payload) => tx.writeValueWithoutResponse(esnPacket(type, payload));   // 2C11 takes no other kind of write
        let buf = [], askedGrams = 0;
        rx.addEventListener("characteristicvaluechanged", e => {
          const v = e.target.value;
          buf = buf.concat([...new Uint8Array(v.buffer, v.byteOffset, v.byteLength)]).slice(-256);
          for (const p of esnPackets(buf)) {
            buf = p.rest;
            if (p.type !== 0xd0 || p.payload.length < 5) continue;
            const [neg, hi, lo, unit, settled] = p.payload, tenths = (hi << 8) | lo;
            if (unit !== 0x00) {   // ounces or millilitres: never read as grams; put the scale back on grams
              if (Date.now() - askedGrams > 2000) { askedGrams = Date.now(); send(0xc0, [0x00]).catch(() => { }); }
              continue;
            }
            on((neg ? -1 : 1) * tenths / 10, settled === 0x01);
          }
        });
        await rx.startNotifications();
        await send(0xc0, [0x00]);   // grams
        return { tare: () => send(0xc1, [0x00]) };   // like the scale's own TARE button (00 seen working on the real scale, 01 ignored)
      } },
  ];
  /* Etekcity ESN00 framing: FE EF C0 A2, type, length, payload, checksum = (type + length + payload) & 0xff */
  const ESN_HEAD = [0xfe, 0xef, 0xc0, 0xa2];
  const esnPacket = (type, payload) => {
    const body = [type, payload.length, ...payload];
    return new Uint8Array([...ESN_HEAD, ...body, body.reduce((a, b) => (a + b) & 0xff, 0)]);
  };
  function* esnPackets(bytes) {   // whole, valid packets in order; 'rest' is what's left after each one
    let i = 0;
    while (true) {
      while (i + 4 <= bytes.length && !ESN_HEAD.every((b, k) => bytes[i + k] === b)) i++;
      if (i + 6 > bytes.length) return;
      const type = bytes[i + 4], len = bytes[i + 5], end = i + 6 + len;
      if (end >= bytes.length) return;   // the rest arrives in the next notification
      const body = bytes.slice(i + 4, end), sum = body.reduce((a, b) => (a + b) & 0xff, 0);
      i = sum === bytes[end] ? end + 1 : i + 1;
      if (sum === bytes[end]) yield { type, payload: body.slice(2), rest: bytes.slice(i) };
    }
  }
  // Services a raw viewer may look at: the known ones plus vendor ranges common on cheap kitchen scales.
  const RAW_SERVICES = [0x181d, 0x181b, 0xfff0, 0xffe0, 0xffb0, 0xfee7, 0xffd0, 0xffc0, 0x1910, 0xae00, 0xff00, 0xfe00];

  const s = { device: null, driver: null, ops: {}, grams: null, steady: false, offset: 0, status: "off", hist: [] };
  const listeners = new Set();
  const emit = () => listeners.forEach(f => f(state()));
  const state = () => ({ status: s.status, name: s.device?.name || s.driver?.name || "Scale",
    grams: s.grams == null ? null : Math.round((s.grams - s.offset) * 10) / 10, steady: s.steady });

  function reading(g, steady) {   // steady: from the scale, or null to work it out here
    const now = Date.now();
    s.hist = s.hist.filter(h => now - h.t < 1000).concat({ t: now, g });
    if (steady == null) {   // held within 1 g for about a second
      const gs = s.hist.map(h => h.g), first = s.hist[0];
      steady = now - first.t > 700 && Math.max(...gs) - Math.min(...gs) <= 1;
    }
    s.grams = g; s.steady = steady; emit();
  }

  async function attach(quiet = false) {   // quiet: auto-connect, so the bar doesn't flash 'Connecting…' every 15 s
    if (!quiet) { s.status = "connecting"; emit(); }
    const server = await s.device.gatt.connect();
    for (const d of DRIVERS) {
      let svc; try { svc = await server.getPrimaryService(d.service); } catch { continue; }
      s.driver = d; s.ops = await d.start(svc, reading); s.status = "on"; emit(); return;
    }
    s.device.gatt.disconnect();
    throw new Error("This scale isn't one the app can read yet. Manage → Settings → Scale shows its raw data so it can be added.");
  }
  async function reconnect() {   // a dropped link: a few tries, then say so
    for (let i = 0; i < 3 && s.device && s.status !== "off"; i++) {
      try { await attach(); return; } catch { await new Promise(r => setTimeout(r, 1500 * (i + 1))); }
    }
    if (s.device) { s.status = "lost"; s.grams = null; emit(); }
  }

  const LAST = "kc.scaleId";   // the scale used last on this device, for auto-connect
  const remember = id => { try { localStorage.setItem(LAST, id); } catch { } };
  const remembered = () => { try { return localStorage.getItem(LAST); } catch { return null; } };
  const KNOWN = /^(Etekcity|Decent)/i;
  let autoBusy = false, userOff = false;

  async function use(device, quiet = false) {
    const d = s.device; s.device = null; try { d && d !== device && d.gatt.disconnect(); } catch { }
    s.device = device; s.offset = 0; s.grams = null; s.hist = [];
    if (!device.kcWatched) {   // one listener per device, however often it reconnects
      device.kcWatched = true;
      device.addEventListener("gattserverdisconnected", () => { if (s.device === device && s.status === "on") reconnect(); });
    }
    try { await attach(quiet); remember(device.id); }
    catch (e) { s.device = null; s.status = "off"; emit(); throw e; }
  }

  return {
    supported: !!navigator.bluetooth,
    canAutoConnect: !!navigator.bluetooth?.getDevices,
    on(f) { listeners.add(f); return () => listeners.delete(f); },
    state,
    async connect() {
      const device = await navigator.bluetooth.requestDevice({
        filters: DRIVERS.map(d => ({ services: [d.service] })).concat({ namePrefix: "Decent" }, { namePrefix: "Etekcity" }),
        optionalServices: DRIVERS.map(d => d.service) });
      userOff = false;
      await use(device);
    },
    /* No tap needed for a scale this site was already allowed to use (okf/features/kitchen-scale.md).
       Quiet: one attempt at a time, 10 seconds at most, nothing shown if the scale is off or out of range. */
    async autoConnect() {
      if (!this.canAutoConnect || autoBusy || userOff || (s.device && s.status !== "lost")) return;
      autoBusy = true;
      try {
        const all = await navigator.bluetooth.getDevices(), want = remembered();
        const device = all.find(d => d.id === want) || all.find(d => KNOWN.test(d.name || ""));
        if (!device) return;
        await Promise.race([use(device, true), new Promise((_, no) => setTimeout(() => no(new Error("timeout")), 10000))]);
      } catch {
        if (s.status !== "on") { s.device = null; s.status = s.status === "lost" ? "lost" : "off"; emit(); }
      } finally { autoBusy = false; }
    },
    disconnect() {   // a tap on Disconnect also stops auto-connect until Connect is tapped again
      userOff = true;
      const d = s.device; s.device = null; s.driver = null; s.status = "off"; s.grams = null; emit();
      try { d?.gatt.disconnect(); } catch { }
    },
    async zero() {   // the scale's own tare when it has one, otherwise an offset kept here
      if (s.ops.tare) { s.offset = 0; s.hist = []; await s.ops.tare(); }
      else if (s.grams != null) { s.offset = s.grams; s.hist = []; s.steady = false; emit(); }
    },
    /* Raw viewer: any nearby device, every notifying characteristic in the services above, logged as hex. */
    async inspect(log) {
      const device = await navigator.bluetooth.requestDevice({ acceptAllDevices: true, optionalServices: RAW_SERVICES });
      log(`Device: ${device.name || "(no name)"}`);
      const server = await device.gatt.connect(), found = [];
      for (const svc of await server.getPrimaryServices().catch(() => [])) {
        log(`Service ${svc.uuid}`);
        for (const ch of await svc.getCharacteristics().catch(() => [])) {
          const p = ch.properties, props = ["read", "write", "writeWithoutResponse", "notify", "indicate"].filter(k => p[k]).join(", ");
          log(`  ${ch.uuid}  [${props}]`);
          if (p.notify || p.indicate) {
            ch.addEventListener("characteristicvaluechanged", e => log(`${ch.uuid.slice(4, 8)}: ${hex(e.target.value)}`));
            await ch.startNotifications().catch(err => log(`  could not listen: ${err.message}`));
            found.push(ch);
          }
        }
      }
      if (!found.length) log("No characteristic sends data. The scale may use a service not in this viewer's list.");
      return () => server.disconnect();
    },
  };
})();
