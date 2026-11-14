import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import webpush from "npm:web-push@3.6.7";

// Backend for the Room Coach home screen app at piotrzatek.com/room.
//   GET                      -> latest sensor snapshot
//   POST {action:subscribe}  -> store this phone's Web Push subscription
//   POST {action:test}       -> send a test notification
//   POST {action:tick}       -> (pg_cron, every minute) work out the advice and push when it changes; after dark, steer the blind
// JWT verification is off because the app is a static page with no Supabase login; instead every
// request must carry a private key in the x-room-key header, checked against hashes in public.room_keys.

const VAPID_PUBLIC = "BO8s0WNjBYLWpIvpkIMxvAm4niN7hTg2DxQX5d_jbOBNM4QqMW-GCL961mCG4EC68jUebZ_3LvEzdfnSBfO4yt8";
const ORIGINS = new Set(["https://piotrzatek.com", "https://www.piotrzatek.com", "https://pazatek.github.io"]);
const BASE = Deno.env.get("SUPABASE_URL")!;
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const dbHeaders = { apikey: SERVICE, Authorization: `Bearer ${SERVICE}`, "Content-Type": "application/json" };

async function rpc(name: string, body: unknown = {}) {
  const res = await fetch(`${BASE}/rest/v1/rpc/${name}`, { method: "POST", headers: dbHeaders, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`${name} http ${res.status}`);
  return await res.json();
}
async function rest(path: string, method: string, body?: unknown, prefer = "return=minimal") {
  const res = await fetch(`${BASE}/rest/v1/${path}`, { method, headers: { ...dbHeaders, Prefer: prefer }, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!res.ok) throw new Error(`${method} ${path.split("?")[0]} http ${res.status} ${await res.text()}`);
}

// ---- the same model the app page uses; keep the two in step ----
const K = { TARGET: 66.5, LO: 65, HI: 68, B: 63, TBLDG: 74, PERSON: 90, KW: 0.488, FULL: 26, PC_IDLE: 100, AW_LO: 70, AW_HI: 73, AW_AIM: 71.5, CO2_HI: 1000 };
const cToF = (c: number | null | undefined) => (c == null ? null : Number(c) * 9 / 5 + 32);
const hold = (target: number, out: number, watts: number) => {
  const d = target - out;
  return d < 3 ? null : Math.max(0, (watts + K.PERSON + K.B * (K.TBLDG - target)) / (K.KW * Math.pow(d, 1.5)));
};
const co2Width = (inF: number, outF: number) => { const dK = (inF - outF) * 5 / 9; return dK < 1 ? null : 13.7 / (1.05 * Math.sqrt(dK)); };
const clampW = (w: number) => Math.max(0, Math.min(K.FULL, Math.round(w)));
const f1 = (x: number) => (Math.round(x * 10) / 10).toFixed(1);

type In = { mode: string; phase: string | null; bedF: number; deskF: number | null; co2: number | null; outF: number; lowF: number | null; watts: number; slope: number | null; blind?: { percent: number } | null };
type Advice = { door: string; window: number; fan: string; phase: string | null; what: string; holdW?: number };

function advise(s: In): Advice {
  if (s.mode === "away") return { door: "open", window: 0, fan: "off", phase: null, what: "Nobody is home" };
  if (s.blind) {
    // After dark the blind does the fine control, so the window stays at a quarter. It only changes when the blind has run out of travel.
    const sleep = s.mode === "sleep", t = sleep ? s.bedF : (s.deskF != null ? s.deskF : s.bedF), aim = sleep ? K.TARGET : K.AW_AIM;
    let phase = s.phase === "wide" || s.phase === "narrow" ? s.phase : null;
    if (s.blind.percent <= 3 && t > aim + 1) phase = "wide"; else if (phase === "wide" && s.blind.percent >= 60) phase = null;
    if (s.blind.percent >= 97 && t < aim - 1) phase = "narrow"; else if (phase === "narrow" && s.blind.percent <= 40) phase = null;
    return { door: "closed", window: phase === "wide" ? 13 : phase === "narrow" ? 3.25 : 6.5, fan: "off", phase,
      what: phase === "wide" ? `Blind is fully up and it is still ${f1(t)}°F` : phase === "narrow" ? `Blind is fully down and it is still ${f1(t)}°F` : `Blind is holding ${f1(aim)}°F` };
  }
  if (s.mode === "sleep") {
    const outEff = s.lowF == null ? s.outF : (s.outF + s.lowF) / 2, H = hold(K.TARGET, outEff, s.watts), wc = co2Width(s.bedF, s.outF);
    if (H == null) return { door: "closed", window: K.FULL, fan: "low", phase: null, what: "It is mild outside" };
    let phase = s.phase === "precool" || s.phase === "warm" ? s.phase : null;
    if (s.bedF > K.HI + 0.5) phase = "precool"; else if (phase === "precool" && s.bedF <= 67) phase = null;
    if (s.bedF < K.LO) phase = "warm"; else if (phase === "warm" && s.bedF >= 66) phase = null;
    if (phase === "precool") return { door: "closed", window: K.FULL, fan: "high", phase, what: `Bed is ${f1(s.bedF)}°F, too warm for sleep`, holdW: clampW(H) };
    if (phase === "warm") return { door: "closed", window: 0, fan: "off", phase, what: `Bed is ${f1(s.bedF)}°F, too cold for sleep` };
    let w = H;
    if (s.slope != null && s.bedF > 67.5 && s.slope >= 0) w += 2;
    if (s.slope != null && s.bedF < 65.8 && s.slope <= 0) w -= 2;
    let win = clampW(w);
    if (s.co2 != null && s.co2 >= K.CO2_HI && wc != null && win < Math.ceil(wc)) win = clampW(Math.ceil(wc));
    return { door: "closed", window: win, fan: "off", phase: null, what: `Bed is ${f1(s.bedF)}°F` };
  }
  const t = s.deskF != null ? s.deskF : s.bedF, wc = co2Width(t, s.outF);
  let phase = s.phase === "cold" ? "cold" : null;
  if (t < K.AW_LO) phase = "cold"; else if (t > 71) phase = null;
  if (t > K.AW_HI) {
    const W = hold(K.AW_AIM, s.outF, s.watts);
    return { door: "closed", window: W == null ? K.FULL : clampW(Math.max(W, wc || 0, 1)), fan: "low", phase: null, what: `Desk is ${f1(t)}°F, too warm` };
  }
  if (phase === "cold") {
    const high = s.co2 != null && s.co2 >= 1200;
    return { door: "open", window: high ? 2 : 0, fan: "off", phase, what: `Desk is ${f1(t)}°F, too cool` + (high ? ` and CO2 is ${Math.round(s.co2!)} ppm` : "") };
  }
  return { door: "closed", window: wc == null ? 2 : clampW(Math.ceil(wc)), fan: "off", phase: null,
    what: s.co2 != null && s.co2 >= K.CO2_HI ? `CO2 is ${Math.round(s.co2)} ppm` : `Desk is back to ${f1(t)}°F` };
}

// The window is only ever set to closed, an eighth, a quarter, half or full; inches are stored rounded (0, 3, 7, 13, 26).
const STEPS = [3.25, 6.5, 13, 26];
const snapInches = (inches: number) => (inches < 1.6 ? 0 : Math.round(STEPS.reduce((best, s) => (Math.abs(Math.log(inches / s)) < Math.abs(Math.log(inches / best)) ? s : best))));
const adviseSnapped = (s: In): Advice => { const a = advise(s); a.window = snapInches(a.window); if (a.holdW != null) a.holdW = snapInches(a.holdW); return a; };
const windowPhrase = (w: number) => (w <= 0 ? "close the window" : w >= 26 ? "open the window fully" : w >= 13 ? "open the window halfway" : w >= 6 ? "open the window a quarter" : "open the window an eighth");
function actions(a: Advice, last: Record<string, unknown> | null) {
  const all = !last || last.door == null || last.window_in == null || last.fan == null;
  const out: string[] = [];
  if (all || Math.abs(Number(last!.window_in) - a.window) >= 1) out.push(windowPhrase(a.window));
  if (all || last!.door !== a.door) out.push(a.door === "open" ? "open the door" : "close the door");
  if (all || last!.fan !== a.fan) out.push(`fan ${a.fan}`);
  const s = out.join(", ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

type Sub = { endpoint: string; p256dh: string; auth: string };
async function push(subs: Sub[], body: string, vapidPrivate: string) {
  let sent = 0; const errors: string[] = [];
  for (const s of subs) {
    try {
      await webpush.sendNotification({ endpoint: s.endpoint, keys: { p256dh: s.p256dh, auth: s.auth } }, JSON.stringify({ title: "Room", body }),
        { TTL: 1800, urgency: "high", vapidDetails: { subject: "https://piotrzatek.com/room/", publicKey: VAPID_PUBLIC, privateKey: vapidPrivate } });
      sent++;
    } catch (e) {
      const status = (e as { statusCode?: number }).statusCode;
      errors.push(String(status ?? (e as Error).message).slice(0, 120));
      if (status === 404 || status === 410) await rest(`room_push_subs?endpoint=eq.${encodeURIComponent(s.endpoint)}`, "DELETE").catch(() => {});
    }
  }
  return { sent, errors };
}

// The night controller: once a minute, nudge the blind a few percent toward the temperature target.
// Up lets more outside air in (cooler); down cuts it (warmer). Measured 2026-11-13 with the window at a quarter
// and 37°F outside: fully up settles near 64°F, fully down near 68°F, most of the change within 45 minutes.
async function steer(blind: { percent: number }, sleep: boolean, base: { bedF: number; deskF: number | null; co2: number | null; slope: number | null }, key: string) {
  const t = sleep ? base.bedF : (base.deskF ?? base.bedF), aim = sleep ? K.TARGET : K.AW_AIM;
  // Where the room is heading in 15 minutes, from the last half hour's drift, so it eases off before overshooting.
  const ahead = t + (base.slope ?? 0) * 0.5 - aim;
  let step = Math.abs(ahead) < 0.25 ? 0 : Math.max(-3, Math.min(3, Math.round(ahead * 1.5) || Math.sign(ahead)));
  if (base.co2 != null && base.co2 >= K.CO2_HI) step = Math.max(step, 3);
  return await moveBlind(Math.max(0, Math.min(100, blind.percent - step)), blind.percent, key);
}
async function moveBlind(to: number, from: number, key: string) {
  if (to === from) return null;
  const res = await fetch(`${BASE}/functions/v1/blind`, { method: "POST", headers: { "x-room-key": key, "Content-Type": "application/json" }, body: JSON.stringify({ percent: to }) });
  return { from, to, ok: res.ok };
}

async function tick(key: string) {
  const d = await rpc("room_tick_data");
  const snap = d.snap, last = d.last as Record<string, unknown> | null, subs = d.subs as Sub[];
  const now = Date.parse(snap.now);
  const mode = d.me === "asleep" ? "sleep" : d.me === "away" ? "away" : "awake";
  const log = async (row: Record<string, unknown>, text: string | null) => {
    let sent = 0, errors: string[] = [];
    if (text && subs.length && d.vapid_private) ({ sent, errors } = await push(subs, text, d.vapid_private));
    await rest("room_notify", "POST", { ...row, notified: sent > 0, message: text });
    return { ...row, message: text, sent, errors };
  };

  if (!snap.bed || now - Date.parse(snap.bed.ts) > 10 * 60000) {
    if (last && last.kind === "offline") return { skip: "still offline" };
    return await log({ kind: "offline", mode }, "Room sensors are offline. Check the SwitchBot hub.");
  }
  if (snap.outdoor?.temp_c == null) return { skip: "no outdoor reading" };

  const avg = snap.bed_now?.n > 0 ? snap.bed_now : null, prev = snap.bed_prev?.n > 0 ? snap.bed_prev : null;
  const bedF = cToF(avg ? avg.temp_c : snap.bed.temp_c)!;
  const base = {
    bedF, deskF: snap.desk && now - Date.parse(snap.desk.ts) < 15 * 60000 ? cToF(snap.desk.temp_c) : null,
    co2: snap.bed.co2 == null ? null : Number(snap.bed.co2), outF: cToF(snap.outdoor.temp_c)!, lowF: cToF(snap.outdoor.low_next10h_c),
    watts: snap.pc?.n > 0 && snap.pc.watts != null ? Number(snap.pc.watts) : K.PC_IDLE, slope: prev ? bedF - cToF(prev.temp_c)! : null,
  };
  const sinceSent = d.last_sent ? now - Date.parse(d.last_sent) : Infinity;
  const blind = snap.blind && snap.blind.percent != null ? { percent: Number(snap.blind.percent) } : null;
  const held = snap.blind?.hold_until && Date.parse(snap.blind.hold_until) > now, steering = !!(blind && snap.blind.steering && mode !== "away");
  let moved = null;
  if (steering) moved = await steer(blind!, mode === "sleep", base, key).catch(() => null);
  // At sunrise the controller stops; if he is still asleep the blind goes fully down, since the window faces the bed.
  else if (blind && snap.blind.auto && !held && mode === "sleep" && Number(snap.outdoor.sun_wm2) > 5 && blind.percent < 100) moved = await moveBlind(100, blind.percent, key).catch(() => null);
  const steered = steering ? blind : null;

  if (mode === "awake" && d.local_hour < 3 && (!d.last_bedtime || now - Date.parse(d.last_bedtime) > 12 * 3600000)) {
    const a = adviseSnapped({ ...base, mode: "sleep", phase: null, blind: steered });
    const text = `Bedtime setup. ${actions(a, null)}.` + (a.phase === "precool" ? ` When the bed reads 67°F, ${windowPhrase(a.holdW!)} and fan off.` : "");
    return await log({ kind: "bedtime", mode: "sleep", phase: a.phase, door: a.door, window_in: a.window, fan: a.fan }, text);
  }
  if (mode === "awake" && last && last.kind === "bedtime" && now - Date.parse(String(last.ts)) < 3 * 3600000) return { skip: "bedtime setup sent, waiting for sleep" };

  const a = adviseSnapped({ ...base, mode, phase: last && last.mode === mode ? (last.phase as string | null) : null, blind: steered });
  const changed = !last || last.kind === "offline" || last.mode !== mode || last.door !== a.door || last.fan !== a.fan || Math.abs(Number(last.window_in) - a.window) >= 1;
  if (!changed) return { skip: "no change", advice: a, blind: moved };
  const row = { kind: "advice", mode, phase: a.phase, door: a.door, window_in: a.window, fan: a.fan };
  if (mode === "sleep") return await log(row, null);
  if (sinceSent < 10 * 60000) return { skip: "sent one less than 10 minutes ago", advice: a };
  return await log(row, `${a.what}. ${actions(a, last && last.kind !== "offline" ? last : null)}.`);
}

function cors(req: Request) {
  const o = req.headers.get("origin") ?? "";
  return {
    "Access-Control-Allow-Origin": ORIGINS.has(o) ? o : "https://piotrzatek.com",
    "Access-Control-Allow-Headers": "x-room-key, content-type",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

Deno.serve(async (req: Request) => {
  const headers = { ...cors(req), "Content-Type": "application/json", "Cache-Control": "no-store" };
  const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers });
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers });
  const key = req.headers.get("x-room-key") ?? "";
  if (key.length < 16 || key.length > 128) return reply({ error: "key" }, 401);
  try {
    const label = await rpc("room_key_label", { p_key: key });
    if (!label) return reply({ error: "key" }, 401);
    if (req.method === "GET") return reply(await rpc("room_snapshot"));
    if (req.method !== "POST") return reply({ error: "method" }, 405);
    const body = await req.json().catch(() => ({}));
    if (body.action === "tick") return label === "cron tick" ? reply(await tick(key)) : reply({ error: "key" }, 401);
    if (body.action === "subscribe") {
      const s = body.sub ?? {};
      const ok = typeof s.endpoint === "string" && s.endpoint.startsWith("https://") && s.endpoint.length < 1000 && typeof s.keys?.p256dh === "string" && typeof s.keys?.auth === "string"
        && s.keys.p256dh.length < 200 && s.keys.auth.length < 100;
      if (!ok) return reply({ error: "bad subscription" }, 400);
      await rest("room_push_subs?on_conflict=endpoint", "POST", { endpoint: s.endpoint, p256dh: s.keys.p256dh, auth: s.keys.auth }, "resolution=merge-duplicates,return=minimal");
      return reply({ ok: true });
    }
    if (body.action === "test") {
      const d = await rpc("room_tick_data");
      return reply(await push(d.subs, "Alerts are on. You'll hear from me when something should change.", d.vapid_private));
    }
    return reply({ error: "action" }, 400);
  } catch (e) {
    return reply({ error: "server", detail: (e as Error).message.slice(0, 200) }, 502);
  }
});
