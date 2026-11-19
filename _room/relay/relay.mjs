// Room Coach lamp relay. Holds the bulbs as a Matter controller on the LAN and takes commands from the Room Coach app over
// the Supabase Realtime channel "room-lights". No cloud lighting API in the path:
//   phone --websocket--> Supabase Realtime --websocket--> this relay --Matter, local Wi-Fi--> bulb
//
// Command (broadcast event "cmd"):
//   { lamp: "pixar"|"little", on?: bool, brightness?: 1..100, k?: 2700..6500, hue?: 0..360, sat?: 0..100, t: epoch ms, sig: hex }
//   sig = HMAC-SHA256(key = the room app key, msg = "lamp|on|brightness|k|hue|sat|t"), a missing field as "".
//   Rejected when the signature is wrong or t is more than 10 s off this PC's clock.
// State (broadcast event "state", on every change and in reply to "hello"):
//   { lamp, on, brightness, k, hue, sat, mode: "ct"|"hs", online, t }
// Presence { relay: true } while connected, so the app knows the fast path is up.
//
// Keys: relay.env next to this file, ROOM_KEYS=<key>[,<key>...] (never committed or logged).
import { OnOff, LevelControl, ColorControl } from "@matter/main/clusters";
import { NodeId } from "@matter/main";
import { createClient } from "@supabase/supabase-js";
import { createHmac, timingSafeEqual, privateDecrypt, constants } from "node:crypto";
import { readFileSync, appendFileSync, statSync, renameSync, existsSync } from "node:fs";
import { join } from "node:path";
import { HERE, startController, lamps } from "./matter.mjs";

const URL = "https://hxaftcofwrffwjxtjeoj.supabase.co";
const PUBLISHABLE = "sb_publishable_4TJE66VMSen-hl22kWL-Rw_8RXH_UOH"; // public by design
const LOG = join(HERE, "relay.log");

function log(...a) {
  const line = `${new Date().toISOString()} ${a.join(" ")}\n`;
  process.stdout.write(line);
  try {
    if (existsSync(LOG) && statSync(LOG).size > 5e6) renameSync(LOG, LOG + ".1");
    appendFileSync(LOG, line);
  } catch {}
}

const env = Object.fromEntries(readFileSync(join(HERE, "relay.env"), "utf8").split(/\r?\n/).filter((l) => /^\w+=/.test(l)).map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1).trim()]));
const KEYS = (env.ROOM_KEYS || env.ROOM_KEY || "").split(",").map((k) => k.trim()).filter(Boolean);

// The app signs with a 12-hour key it gets from the `lamp` edge function: HMAC(secret, "lamp|" + exp). The secret comes from that
// function too, encrypted to this PC's RSA key (relay_key.pem), so it never sits in a file or crosses the channel in the clear.
let SECRET = null;
async function fetchSecret() {
  const r = await fetch(`${URL}/functions/v1/lamp?relay=1`);
  if (!r.ok) throw new Error(`lamp http ${r.status}`);
  const { s } = await r.json();
  SECRET = privateDecrypt({ key: readFileSync(join(HERE, "relay_key.pem")), padding: constants.RSA_PKCS1_OAEP_PADDING, oaepHash: "sha256" }, Buffer.from(s, "base64"));
}

const field = (v) => (v === undefined || v === null ? "" : String(v));
function verify(c) {
  if (typeof c?.sig !== "string" || !/^[0-9a-f]{64}$/.test(c.sig)) return "bad sig";
  if (typeof c.t !== "number" || Math.abs(Date.now() - c.t) > 10000) return "stale";
  const msg = [c.lamp, c.on, c.brightness, c.k, c.hue, c.sat, c.t].map(field).join("|");
  const got = Buffer.from(c.sig, "hex"), ok = (k) => timingSafeEqual(createHmac("sha256", k).update(msg).digest(), got);
  if (typeof c.exp === "number") {
    if (!SECRET) return "no secret yet";
    if (c.exp < Date.now() || c.exp > Date.now() + 13 * 3600000) return "expired key";
    return ok(createHmac("sha256", SECRET).update(`lamp|${c.exp}`).digest()) ? null : "bad sig";
  }
  return KEYS.some(ok) ? null : "bad sig";
}

// ---- Matter side ----
const NOOPTS = { optionsMask: { executeIfOff: false, coupleColorTempToLevel: false }, optionsOverride: { executeIfOff: false, coupleColorTempToLevel: false } };
const L = {}; // name -> { node, onOff, level, color, busy, pending }

async function attach(name, id, controller) {
  const node = await controller.getNode(NodeId(BigInt(id)));
  const lamp = (L[name] = { name, node, busy: false, pending: null });
  const bind = () => {
    const dev = node.getDevices().find((d) => d.getClusterClient(OnOff.Complete));
    if (!dev) return false;
    lamp.onOff = dev.getClusterClient(OnOff.Complete);
    lamp.level = dev.getClusterClient(LevelControl.Complete);
    lamp.color = dev.getClusterClient(ColorControl.Complete);
    return true;
  };
  node.events.attributeChanged.on((d) => { if ([6, 8, 0x300].includes(Number(d.path.clusterId))) stateSoon(name); });
  node.events.stateChanged.on((s) => { log(name, "node state", s); stateSoon(name); });
  const describe = () => {
    try {
      const b = node.basicInformation ?? {};
      const eps = node.getDevices().map((d) => `${d.number}:${[6, 8, 0x300].filter((c) => d.getClusterClientById?.(c) ?? null).join("/")}`);
      log(name, "is", JSON.stringify({ vendor: b.vendorName, product: b.productName, hw: b.hardwareVersionString, sw: b.softwareVersionString }), "endpoints", eps.join(" "));
    } catch (e) { log(name, "describe failed", e?.message ?? e); }
  };
  node.events.initializedFromRemote.on(() => { bind(); describe(); stateSoon(name); });
  node.connect();
  if (node.initialized) { bind(); describe(); }
  log(name, "attached as node", id);
}

async function readState(name) {
  const l = L[name];
  if (!l?.onOff) return { lamp: name, online: false, t: Date.now() };
  // From the subscription cache: reading the bulb over the network after every command kept it busy and slowed the next one.
  const g = async (c, a) => { try { const at = c?.attributes[a]; const v = at?.getLocal?.(); return v !== undefined ? v : await at?.get?.(); } catch { return null; } };
  const [on, level, mode, mireds, hue, sat] = await Promise.all([g(l.onOff, "onOff"), g(l.level, "currentLevel"), g(l.color, "colorMode"),
    g(l.color, "colorTemperatureMireds"), g(l.color, "currentHue"), g(l.color, "currentSaturation")]);
  return {
    lamp: name, online: !!l.node.isConnected, on: !!on,
    brightness: level == null ? null : Math.max(1, Math.round(level / 2.54)),
    // below the bulbs' warmest white (2700K) the colour is an xy point; report the Kelvin it was set to
    k: l.amber ? (l.lastK || 2000) : mireds ? Math.round(1e6 / mireds) : null,
    hue: hue == null ? null : Math.round(hue * 360 / 254), sat: sat == null ? null : Math.round(sat * 100 / 254),
    mode: l.amber || mode === 2 || mode === 1 ? "ct" : "hs", t: Date.now(),
  };
}

// One command per lamp in flight; while it runs, newer ones replace each other so a dragged slider never queues up.
function enqueue(c) {
  const l = L[c.lamp];
  if (!l) return log("unknown lamp", c.lamp);
  l.pending = { ...(l.pending || {}), ...c, rx: performance.now() };
  if (!l.busy) run(l);
}
async function run(l) {
  l.busy = true;
  while (l.pending) {
    const c = l.pending; l.pending = null;
    const t0 = performance.now(), did = [], jobs = [];
    // While a slider is being dragged (commands under 400 ms apart) each step fades over 0.3 s (about one bulb round trip) so the bulb glides instead of
    // stepping; a single tap changes at once.
    const tt = t0 - (l.lastCmd || 0) < 500 ? 3 : 0;
    l.lastCmd = t0;
    try {
      if (!l.onOff) throw new Error("not connected yet");
      if (c.on === false) { jobs.push(l.onOff.off()); did.push("off"); }
      else {
        // Colour and brightness go out together rather than one after the other.
        if (c.hue != null || c.k != null) l.amber = false;
        if (c.hue != null && c.sat != null) {
          jobs.push(l.color.moveToHueAndSaturation({ hue: Math.round((c.hue % 360) * 254 / 360), saturation: Math.round(c.sat * 2.54), transitionTime: tt, ...NOOPTS }));
          did.push(`hs ${c.hue}/${c.sat}`);
        } else if (c.k != null && c.k < 2700) {
          // Warmer than the white LEDs go. The exact xy point (planckXY) came out yellow-green on the Govee bulbs and differently
          // on each brand, so amber is a full-saturation hue, tuned per lamp by eye in AMBER_HUE.
          const am = AMBER[l.name] ?? AMBER.default;
          if (am.xy) jobs.push(l.color.moveToColor({ colorX: Math.round(am.xy[0] * 65536), colorY: Math.round(am.xy[1] * 65536), transitionTime: tt, ...NOOPTS }));
          else jobs.push(l.color.moveToHueAndSaturation({ hue: Math.round(am.hue * 254 / 360), saturation: 254, transitionTime: tt, ...NOOPTS }));
          l.lastK = c.k; l.amber = true;
          did.push(`amber (k ${c.k}, ${JSON.stringify(am)})`);
        } else if (c.k != null) {
          jobs.push(l.color.moveToColorTemperature({ colorTemperatureMireds: Math.round(1e6 / c.k), transitionTime: tt, ...NOOPTS }));
          did.push(`k ${c.k}`);
        }
        if (c.brightness != null) { jobs.push(l.level.moveToLevelWithOnOff({ level: Math.round(c.brightness * 2.54), transitionTime: tt, ...NOOPTS })); did.push(`b ${c.brightness}`); }
        else if (c.on === true) { jobs.push(l.onOff.on()); did.push("on"); }
      }
      // A bulb that drops off (power cut, Wi-Fi) leaves its command hanging, which used to block that lamp until a restart.
      await Promise.race([Promise.all(jobs), new Promise((_, no) => setTimeout(() => no(new Error("bulb didn't answer in 4 s")), 4000))]);
      // Lets the app time the whole trip on its own clock: its round trip minus `total` is the network both ways.
      const now = performance.now();
      channel?.send({ type: "broadcast", event: "done", payload: { lamp: l.name, t: c.t, total: Math.round(now - c.rx), bulb: Math.round(now - t0) } });
      log(l.name, did.join(", "), tt ? "(fade)" : "", `${(performance.now() - t0).toFixed(0)} ms`, `(sent ${Date.now() - c.t} ms ago)`);
    } catch (e) {
      log(l.name, "command failed:", e?.message ?? e);
    }
    stateSoon(l.name);
    liveCheck(l);
  }
  l.busy = false;
}

// Reads the bulb itself (not the subscription cache) 2 s after a command and logs it, so a bulb
// that says one thing and does another shows up in relay.log.
function liveCheck(l) {
  setTimeout(async () => {
    const get = async (c, a) => { try { return await c?.attributes[a]?.get?.(true); } catch (e) { return "err:" + (e?.message ?? e); } };
    const [on, level, min, max, mode, mireds] = await Promise.all([get(l.onOff, "onOff"), get(l.level, "currentLevel"), get(l.level, "minLevel"),
      get(l.level, "maxLevel"), get(l.color, "colorMode"), get(l.color, "colorTemperatureMireds")]);
    log(l.name, "live:", JSON.stringify({ on, level, min, max, mode, mireds }));
  }, 2000);
}

// ---- Realtime side ----
const supa = createClient(URL, PUBLISHABLE, { realtime: { params: { eventsPerSecond: 30 } }, auth: { persistSession: false } });
let channel = null;
const timers = {};
function stateSoon(name) {
  clearTimeout(timers[name]);
  timers[name] = setTimeout(async () => { if (channel) channel.send({ type: "broadcast", event: "state", payload: await readState(name) }); }, 80);
}
function join_() {
  channel = supa.channel("room-lights", { config: { broadcast: { self: false, ack: false }, presence: { key: "relay" } } });
  channel
    .on("broadcast", { event: "cmd" }, ({ payload: c }) => {
      const bad = verify(c);
      if (bad) { if (bad === "no secret yet") fetchSecret().catch(() => {}); return log("rejected cmd:", bad, c?.lamp ?? "", typeof c?.exp === "number" ? "(12 h key)" : "(no exp: old app version or test key)"); }
      enqueue({ lamp: c.lamp, on: c.on, brightness: num(c.brightness, 1, 100), k: num(c.k, 1700, 6500), hue: num(c.hue, 0, 360), sat: num(c.sat, 0, 100), t: c.t });
    })
    .on("broadcast", { event: "hello" }, () => { for (const n of Object.keys(L)) stateSoon(n); })
    .subscribe(async (status) => {
      log("channel", status);
      if (status === "SUBSCRIBED") { await channel.track({ relay: true, since: Date.now() }); for (const n of Object.keys(L)) stateSoon(n); }
      if (status === "CLOSED" || status === "CHANNEL_ERROR" || status === "TIMED_OUT") {
        const old = channel; channel = null;
        setTimeout(() => { supa.removeChannel(old).catch(() => {}); join_(); }, 3000);
      }
    });
}
// Amber (the app's 2000K button), as a hue in degrees per lamp: lower is redder. Tune by eye; 0 is pure red.
// Amber (the app's 2000K button), per lamp: a hue in degrees (lower is redder) or an xy point on the edge of the spectrum.
// The basket bulb is right at hue 14 (Piotr, 2026-11-17). The Govees looked washed out (pinkish/yellowish) on hue: testing
// pixar on a pure spectral orange (~605 nm) and little on hue 25.
const AMBER = { default: { hue: 22 }, pixar: { hue: 28 }, little: { hue: 28 }, basket: { hue: 14 } };  // matched by eye to the basket bulb, 2026-11-17

// CIE 1931 xy of a blackbody (Kim et al. cubic fit, valid 1667-4000K). 2000K -> (0.5269, 0.4133).
function planckXY(T) {
  const x = -0.2661239e9 / T ** 3 - 0.2343589e6 / T ** 2 + 0.8776956e3 / T + 0.17991;
  const y = T < 2222 ? -1.1063814 * x ** 3 - 1.3481102 * x ** 2 + 2.18555832 * x - 0.20219683
                     : -0.9549476 * x ** 3 - 1.37418593 * x ** 2 + 2.09137015 * x - 0.16748867;
  return [x, y];
}
const num = (v, lo, hi) => (typeof v === "number" && Number.isFinite(v) ? Math.min(hi, Math.max(lo, Math.round(v))) : undefined);

for (let i = 0; !SECRET; i++) {
  try { await fetchSecret(); log("signing secret loaded"); }
  catch (e) { log("couldn't load the signing secret:", e?.message ?? e); if (i >= 2) break; await new Promise((r) => setTimeout(r, 3000)); }
}
const controller = await startController();
for (const [name, id] of Object.entries(lamps())) await attach(name, id, controller).catch((e) => log(name, "attach failed:", e?.message ?? e));
join_();
log("relay up, lamps:", Object.keys(L).join(", ") || "none");

const stop = async () => { log("stopping"); try { await channel?.untrack(); await controller.close(); } catch {} process.exit(0); };
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
