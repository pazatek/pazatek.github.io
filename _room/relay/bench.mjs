// Times the app's path on one clock: send signed commands like the app (12 h key), wait for the relay's "done" for each.
//   node bench.mjs [count]   taps one at a time on pixar's brightness, then puts brightness back where it was.
import { createClient } from "@supabase/supabase-js";
import { createHmac, privateDecrypt, constants } from "node:crypto";
import { readFileSync } from "node:fs";
const URL = "https://hxaftcofwrffwjxtjeoj.supabase.co", N = Number(process.argv[2] || 8);
const { s: enc } = await (await fetch(`${URL}/functions/v1/lamp?relay=1`)).json();
const secret = privateDecrypt({ key: readFileSync(new globalThis.URL("./relay_key.pem", import.meta.url)), padding: constants.RSA_PKCS1_OAEP_PADDING, oaepHash: "sha256" }, Buffer.from(enc, "base64"));
const exp = Date.now() + 12 * 3600000, k = createHmac("sha256", secret).update(`lamp|${exp}`).digest();
const f = (v) => (v === undefined || v === null ? "" : String(v));
const sb = createClient(URL, "sb_publishable_4TJE66VMSen-hl22kWL-Rw_8RXH_UOH");
const ch = sb.channel("room-lights", { config: { broadcast: { self: false } } });
let start = null; const waits = new Map(), rows = [];
ch.on("broadcast", { event: "state" }, ({ payload: p }) => { if (p.lamp === "pixar" && start == null) start = p; });
ch.on("broadcast", { event: "done" }, ({ payload: p }) => { const w = waits.get(p.t); if (w) { waits.delete(p.t); w(p); } });
const send = (c) => new Promise(async (res) => {
  c.lamp = "pixar"; c.t = Date.now(); c.exp = exp;
  c.sig = createHmac("sha256", k).update([c.lamp, c.on, c.brightness, c.k, c.hue, c.sat, c.t].map(f).join("|")).digest("hex");
  const t0 = performance.now(); waits.set(c.t, (p) => res({ rtt: performance.now() - t0, ...p }));
  await ch.send({ type: "broadcast", event: "cmd", payload: c });
  setTimeout(() => res(null), 4000);
});
ch.subscribe(async (st) => {
  if (st !== "SUBSCRIBED") return;
  await ch.send({ type: "broadcast", event: "hello", payload: {} });
  await new Promise((r) => setTimeout(r, 800));
  const was = start?.brightness ?? 100;
  for (let i = 0; i < N; i++) {
    const r = await send({ brightness: i % 2 ? was : Math.max(1, was - 20) });
    if (r) rows.push(r);
    await new Promise((x) => setTimeout(x, 700)); // spaced like separate taps, so no fade
  }
  await send({ brightness: was });
  const net = rows.map((r) => (r.rtt - r.total) / 2), tap = rows.map((r, i) => net[i] + r.bulb);
  const med = (a) => [...a].sort((x, y) => x - y)[Math.floor(a.length / 2)].toFixed(0);
  console.log(`n=${rows.length}  network one way ~${med(net)} ms  bulb ack ${med(rows.map((r) => r.bulb))} ms  tap to bulb ack ~${med(tap)} ms  (min ${Math.min(...tap).toFixed(0)}, max ${Math.max(...tap).toFixed(0)})`);
  process.exit(0);
});
