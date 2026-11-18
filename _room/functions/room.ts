import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import webpush from "npm:web-push@3.6.7";
import { CTL, decide, fit, samples, type Bucket } from "./model.ts";

// Backend for the Room Coach home screen app at piotrzatek.com/room.
//   GET                      -> latest sensor snapshot
//   POST {action:subscribe}  -> store this phone's Web Push subscription
//   POST {action:test}       -> send a test notification
//   POST {action:mode, mode: awake|sleep|away} -> set his presence (lights_presence 'me'), which picks the blind's target
//   POST {action:tick}       -> (pg_cron, every minute) work out the advice and push when it changes; after dark, steer the blind
//   POST {action:thermal, stats, frame?} -> (thermal camera key only) one minute's summary from the PC's thermal camera, into room_thermal
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
const K = { TARGET: 64, LO: 60, HI: 67, B: 63, TBLDG: 74, PERSON: 90, KW: 0.488, FULL: 26, PC_IDLE: 100, AW_LO: 73, AW_HI: 74, AW_AIM: 73.5, CO2_HI: 1000 };
const cToF = (c: number | null | undefined) => (c == null ? null : Number(c) * 9 / 5 + 32);
const hold = (target: number, out: number, watts: number) => {
  const d = target - out;
  return d < 3 ? null : Math.max(0, (watts + K.PERSON + K.B * (K.TBLDG - target)) / (K.KW * Math.pow(d, 1.5)));
};
const co2Width = (inF: number, outF: number) => { const dK = (inF - outF) * 5 / 9; return dK < 1 ? null : 13.7 / (1.05 * Math.sqrt(dK)); };
const clampW = (w: number) => Math.max(0, Math.min(K.FULL, Math.round(w)));
const f1 = (x: number) => (Math.round(x * 10) / 10).toFixed(1);
const ALERT_GAP_MIN = 15;

type In = { mode: string; phase: string | null; bedF: number; deskF: number | null; co2: number | null; outF: number; lowF: number | null; watts: number; slope: number | null; blind?: { percent: number } | null };
type Advice = { door: string; window: number; fan: string; phase: string | null; what: string; holdW?: number };

function advise(s: In): Advice {
  if (s.mode === "away") return { door: "open", window: 0, fan: "off", phase: null, what: "Nobody is home" };
  if (s.blind && s.mode !== "sleep") return awakeWindow(s);
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
    if (s.bedF > K.HI + 0.5) phase = "precool"; else if (phase === "precool" && s.bedF <= K.HI - 1) phase = null;
    if (s.bedF < K.LO) phase = "warm"; else if (phase === "warm" && s.bedF >= K.LO + 1) phase = null;
    if (phase === "precool") return { door: "closed", window: K.FULL, fan: "high", phase, what: `Bed is ${f1(s.bedF)}°F, too warm for sleep`, holdW: clampW(H) };
    if (phase === "warm") return { door: "closed", window: 0, fan: "off", phase, what: `Bed is ${f1(s.bedF)}°F, too cold for sleep` };
    let w = H;
    if (s.slope != null && s.bedF > K.HI - 0.5 && s.slope >= 0) w += 2;
    if (s.slope != null && s.bedF < K.LO + 0.8 && s.slope <= 0) w -= 2;
    let win = clampW(w);
    if (s.co2 != null && s.co2 >= K.CO2_HI && wc != null && win < Math.ceil(wc)) win = clampW(Math.ceil(wc));
    return { door: "closed", window: win, fan: "off", phase: null, what: `Bed is ${f1(s.bedF)}°F` };
  }
  const t = s.deskF != null ? s.deskF : s.bedF, wc = co2Width(t, s.outF);
  let phase = s.phase === "cold" ? "cold" : null;
  if (t < K.AW_LO) phase = "cold"; else if (t > K.AW_LO + 0.5) phase = null;
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

// Awake in cold weather an open window can't hold 73-74°F even with the blind fully down (the model: a quarter-open window at
// 30°F out settles 62-67°F), so the window stays shut and only opens when the room gets too warm, or an eighth for stale air.
function awakeWindow(s: In): Advice {
  const t = s.deskF != null ? s.deskF : s.bedF;
  let phase = s.phase === "vent" || s.phase === "air" ? s.phase : null;
  if (t > K.AW_HI + 0.3) phase = "vent"; else if (phase === "vent" && t <= K.AW_AIM) phase = null;
  if (phase !== "vent") {
    if (s.co2 != null && s.co2 >= 1200) phase = "air"; else if (phase === "air" && s.co2 != null && s.co2 < 900) phase = null;
  }
  if (phase === "vent") return { door: "closed", window: 6.5, fan: "off", phase, what: `Desk is ${f1(t)}°F, too warm` };
  if (phase === "air") return { door: "closed", window: 3.25, fan: "off", phase, what: `CO2 is ${Math.round(s.co2!)} ppm` };
  return { door: "closed", window: 0, fan: "off", phase: null, what: `Desk is ${f1(t)}°F` };
}

// The window is only ever set to closed, an eighth, a quarter, half or full; inches are stored rounded (0, 3, 7, 13, 26).
const STEPS = [3.25, 6.5, 13, 26];
const snapInches = (inches: number) => (inches < 1.6 ? 0 : Math.round(STEPS.reduce((best, s) => (Math.abs(Math.log(inches / s)) < Math.abs(Math.log(inches / best)) ? s : best))));
const adviseSnapped = (s: In): Advice => { const a = advise(s); a.window = snapInches(a.window); if (a.holdW != null) a.holdW = snapInches(a.holdW); return a; };
const windowPhrase = (w: number) => (w <= 0 ? "close the window" : w >= 26 ? "open the window fully" : w >= 13 ? "open the window halfway" : w >= 6 ? "open the window a quarter" : "open the window an eighth");
// The opening line of a phone alert: no numbers, just which way the room is about to go (Piotr, 2026-11-17).
function heads(a: Advice, last: Record<string, unknown> | null, mode: string) {
  if (mode === "away") return "Nobody's home.";
  if (a.phase === "air") return "Hey, the air's getting stuffy.";
  const when = mode === "sleep" ? "tonight" : "soon", w0 = last && last.window_in != null ? Number(last.window_in) : null;
  const warmer = ["cold", "warm", "narrow"].includes(a.phase ?? "") || (w0 != null && a.window < w0 - 0.5) || (a.door === "open" && (!last || last.door !== "open"));
  const cooler = ["precool", "wide", "vent"].includes(a.phase ?? "") || (w0 != null && a.window > w0 + 0.5) || (a.fan !== "off" && (!last || last.fan === "off"));
  if (warmer && !cooler) return `Hey, it might get too cold ${when}.`;
  if (cooler && !warmer) return `Hey, it might get too warm ${when}.`;
  return "Heads up.";
}
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

// The night controller: puts the blind where the learned model (model.ts) says the room will settle at the target, then waits
// for the room to get there instead of chasing every reading. It moves at most once per CTL.SETTLE_MIN minutes, and only when the
// room's settling point at the current height is more than CTL.DEAD_F off the target.
async function steer(blind: { percent: number; steeredAt: number | null }, sleep: boolean, base: { bedF: number; deskF: number | null; co2: number | null; outF: number; watts: number }, key: string, now: number) {
  if (blind.steeredAt && now - blind.steeredAt < CTL.SETTLE_MIN * 60000) return null;
  const sensor = sleep || base.deskF == null ? "bed" : "desk", aim = sleep ? K.TARGET : K.AW_AIM;
  const rows = (await rpc("room_fit_rows")) as Record<string, string | number | null>[];
  const bs: Bucket[] = rows.filter((r) => r[`${sensor}_f`] != null && r.percent != null && r.out_f != null)
    .map((r) => ({ t: Date.parse(String(r.b)), p: Number(r.percent) / 100, T: Number(r[`${sensor}_f`]), out: Number(r.out_f), watts: Number(r.watts ?? K.PC_IDLE) }));
  const ss = samples(bs), m = fit(ss, now);
  const d = decide(m.theta, ss, now, aim, blind.percent, base.outF, base.watts);
  let to = d.move ? d.pct! : blind.percent;
  if (base.co2 != null && base.co2 >= K.CO2_HI) to = Math.min(to, blind.percent - 10); // stale air: let more in regardless
  to = Math.max(0, Math.min(100, to));
  await rest("room_model?on_conflict=sensor", "POST", { sensor, theta: m.theta, n: m.n, steps: m.steps, rmse: m.rmse, bias: d.bias, settle_now: d.eqNow, ideal_pct: d.pct, fitted_at: new Date(now).toISOString() },
    "resolution=merge-duplicates,return=minimal").catch(() => {});
  const moved = await moveBlind(to, blind.percent, key);
  if (moved?.ok) await rest("room_blind?id=eq.1", "PATCH", { steered_at: new Date(now).toISOString() });
  return moved;
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
  // At most one phone alert every 15 minutes, of any kind (Piotr, 2026-11-17). A held-back alert isn't logged, so the next
  // tick tries again and the latest advice goes out once the 15 minutes are up.
  const sinceSent = d.last_sent ? now - Date.parse(d.last_sent) : Infinity;
  const log = async (row: Record<string, unknown>, text: string | null) => {
    if (text && sinceSent < ALERT_GAP_MIN * 60000) return { skip: `sent one less than ${ALERT_GAP_MIN} minutes ago`, held: text };
    // Saved before sending: if the save fails, nothing goes out, so a failing save can't repeat an alert every minute.
    const willSend = !!(text && subs.length && d.vapid_private);
    await rest("room_notify", "POST", { ...row, notified: willSend, message: text });
    let sent = 0, errors: string[] = [];
    if (willSend) ({ sent, errors } = await push(subs, text!, d.vapid_private));
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
  const blind = snap.blind && snap.blind.percent != null ? { percent: Number(snap.blind.percent) } : null;
  const held = snap.blind?.hold_until && Date.parse(snap.blind.hold_until) > now, steering = !!(blind && snap.blind.steering && mode !== "away");
  await rest("room_log", "POST", { percent: blind?.percent ?? null, mode, steering, bed_f: bedF, desk_f: base.deskF, out_f: base.outF, watts: base.watts }).catch(() => {});
  let moved = null;
  if (steering) {
    const at = await (await fetch(`${BASE}/rest/v1/room_blind?id=eq.1&select=steered_at`, { headers: dbHeaders })).json().catch(() => null);
    const steeredAt = at?.[0]?.steered_at ? Date.parse(at[0].steered_at) : null;
    moved = await steer({ ...blind!, steeredAt }, mode === "sleep", base, key, now).catch(() => null);
  }
  // At sunrise the controller stops; if he is still asleep the blind goes fully down, since the window faces the bed.
  else if (blind && snap.blind.auto && !held && mode === "sleep" && Number(snap.outdoor.sun_wm2) > 5 && blind.percent < 100) moved = await moveBlind(100, blind.percent, key).catch(() => null);
  const steered = steering ? blind : null;

  if (mode === "awake" && d.local_hour < 3 && (!d.last_bedtime || now - Date.parse(d.last_bedtime) > 12 * 3600000)) {
    const a = adviseSnapped({ ...base, mode: "sleep", phase: null, blind: steered });
    const text = `Bedtime. ${actions(a, null)}.` + (a.phase === "precool" ? ` Once it's cooled down, ${windowPhrase(a.holdW!)} and fan off.` : "");
    return await log({ kind: "bedtime", mode: "sleep", phase: a.phase, door: a.door, window_in: a.window, fan: a.fan }, text);
  }
  if (mode === "awake" && last && last.kind === "bedtime" && now - Date.parse(String(last.ts)) < 3 * 3600000) return { skip: "bedtime setup sent, waiting for sleep" };

  const a = adviseSnapped({ ...base, mode, phase: last && last.mode === mode ? (last.phase as string | null) : null, blind: steered });
  const changed = !last || last.kind === "offline" || last.mode !== mode || last.door !== a.door || last.fan !== a.fan || Math.abs(Number(last.window_in) - a.window) >= 1;
  if (!changed) return { skip: "no change", advice: a, blind: moved };
  const row = { kind: "advice", mode, phase: a.phase, door: a.door, window_in: a.window, fan: a.fan };
  if (mode === "sleep") return await log(row, null);
  const prior = last && last.kind !== "offline" ? last : null, act = actions(a, prior);
  return await log(row, act ? `${heads(a, prior, mode)} ${act}.` : heads(a, prior, mode));
}

// ---- Live Activity on the iPhone (the Room app in _room/ios): readings on the lock screen and in the Dynamic Island ----
// While he is home and awake (lights_presence 'me' = home) the activity is started by push-to-start and updated every
// minute the readings change; when he goes to sleep or leaves it is ended. iOS stops an activity after 8 hours, so one
// that old is ended and a fresh one started. Tokens come from the app (action live_token) and live in room_live.
// Secrets: APNS_KEY_P8 (the .p8 file's text), APNS_KEY_ID, APNS_TEAM_ID. Without them this does nothing.
const BUNDLE = "com.piotrzatek.roomcoach";
type LiveRow = { id: string; kind: string; token: string; env: string; started_at: string; ended_at: string | null; last_state: Record<string, unknown> | null; last_push: string | null; last_hi: string | null };
const WIN_SHORT: Record<number, string> = { 0: "closed", 3: "⅛", 7: "¼", 13: "½", 26: "full" };

// What the lock screen shows; RoomAttributes.ContentState in the app must have the same keys.
// deno-lint-ignore no-explicit-any
function liveState(snap: any, me: string | null, last: Record<string, unknown> | null) {
  const now = Date.parse(snap.now);
  // deno-lint-ignore no-explicit-any
  const fresh = (r: any) => r && r.temp_c != null && now - Date.parse(r.ts) < 15 * 60000;
  const r1 = (x: number | null) => (x == null ? null : Math.round(x * 10) / 10);
  const bedF = fresh(snap.bed) ? cToF(snap.bed.temp_c) : null, deskF = fresh(snap.desk) ? cToF(snap.desk.temp_c) : null;
  const sleep = me === "asleep", useDesk = !sleep && deskF != null;
  const src = useDesk ? snap.desk : snap.bed;
  let what = "Sensors offline";
  if (bedF != null || deskF != null) {
    what = "";
    if (last && last.kind !== "offline" && last.window_in != null) {
      const w = Number(last.window_in);
      what = `Window ${WIN_SHORT[w] ?? `${w} in`} · door ${last.door} · fan ${last.fan}`;
    }
    if (snap.blind?.percent != null) what += `${what ? " · " : ""}blind ${Math.round(Number(snap.blind.percent))}%`;
  }
  return {
    label: useDesk ? "Desk" : "Bed", temp: r1(useDesk ? deskF : bedF) ?? 0, lo: sleep ? K.LO : K.AW_LO, hi: sleep ? K.HI : K.AW_HI,
    bed: useDesk ? r1(bedF) : null, out: r1(cToF(snap.outdoor?.temp_c)),
    co2: snap.bed?.co2 == null ? null : Math.round(Number(snap.bed.co2)),
    hum: src?.humidity == null ? null : Math.round(Number(src.humidity)),
    what, ts: Math.floor(Date.parse(src?.ts ?? snap.now) / 1000),
  };
}
const canon = (o: Record<string, unknown> | null) => (o ? JSON.stringify(Object.keys(o).filter((k) => k !== "ts").sort().map((k) => [k, o[k]])) : "");

// Apple refuses a new provider token more than once every 20 minutes, so one is kept in room_live for 50.
async function apnsJwt() {
  const rows = await (await fetch(`${BASE}/rest/v1/room_live?id=eq.apns_jwt&select=token,updated_at`, { headers: dbHeaders })).json();
  if (rows?.[0] && Date.now() - Date.parse(rows[0].updated_at) < 50 * 60000) return rows[0].token as string;
  const pem = Deno.env.get("APNS_KEY_P8")!, kid = Deno.env.get("APNS_KEY_ID")!, team = Deno.env.get("APNS_TEAM_ID")!;
  const der = Uint8Array.from(atob(pem.replace(/-----[^-]+-----|\s/g, "")), (c) => c.charCodeAt(0));
  const key = await crypto.subtle.importKey("pkcs8", der, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const b64u = (b: Uint8Array) => btoa(String.fromCharCode(...b)).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
  const enc = (o: unknown) => b64u(new TextEncoder().encode(JSON.stringify(o)));
  const now = new Date(), head = `${enc({ alg: "ES256", kid })}.${enc({ iss: team, iat: Math.floor(now.getTime() / 1000) })}`;
  const sig = new Uint8Array(await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key, new TextEncoder().encode(head)));
  const jwt = `${head}.${b64u(sig)}`;
  await rest("room_live?on_conflict=id", "POST", { id: "apns_jwt", kind: "jwt", token: jwt, updated_at: now.toISOString() }, "resolution=merge-duplicates,return=minimal");
  return jwt;
}
async function apns(row: LiveRow, aps: Record<string, unknown>, priority: 5 | 10, jwt: string) {
  const host = row.env === "production" ? "api.push.apple.com" : "api.sandbox.push.apple.com";
  const res = await fetch(`https://${host}/3/device/${row.token}`, {
    method: "POST", body: JSON.stringify({ aps }),
    headers: { authorization: `bearer ${jwt}`, "apns-push-type": "liveactivity", "apns-topic": `${BUNDLE}.push-type.liveactivity`, "apns-priority": String(priority) },
  });
  const reason = res.ok ? null : ((await res.json().catch(() => ({}))) as { reason?: string }).reason ?? null;
  return { status: res.status, reason };
}
const deadToken = (r: { status: number; reason: string | null }) => r.status === 410 || ["BadDeviceToken", "ExpiredToken", "Unregistered", "DeviceTokenNotForTopic"].includes(r.reason ?? "");

// deno-lint-ignore no-explicit-any
async function live(d: any) {
  if (!Deno.env.get("APNS_KEY_P8")) return { skip: "no APNs key" };
  const rows = (await (await fetch(`${BASE}/rest/v1/room_live?kind=in.(start,update)&select=*`, { headers: dbHeaders })).json()) as LiveRow[];
  const now = Date.now(), ts = Math.floor(now / 1000), iso = new Date(now).toISOString(), home = d.me === "home";
  const st = liveState(d.snap, d.me, d.last), out: unknown[] = [];
  const active = rows.filter((r) => r.kind === "update" && !r.ended_at), start = rows.find((r) => r.id === "start");
  if (!active.length && !(home && start)) return { skip: home ? "no start token yet" : "not home" };
  const jwt = await apnsJwt();
  // One started by hand from the app while asleep or away stays up until the presence next changes.
  const me = await (await fetch(`${BASE}/rest/v1/lights_presence?person=eq.me&select=since`, { headers: dbHeaders })).json().catch(() => null);
  const meSince = me?.[0]?.since ? Date.parse(me[0].since) : 0;
  let running = 0;
  for (const r of active) {
    const id = encodeURIComponent(r.id);
    if ((!home && meSince > Date.parse(r.started_at)) || now - Date.parse(r.started_at) > 465 * 60000) {
      const res = await apns(r, { timestamp: ts, event: "end", "content-state": st, "dismissal-date": ts }, 10, jwt);
      await rest(`room_live?id=eq.${id}`, "PATCH", { ended_at: iso });
      out.push({ end: r.id, ...res });
      continue;
    }
    const since = r.last_push ? now - Date.parse(r.last_push) : Infinity;
    if (canon(r.last_state) === canon(st) && since < 5 * 60000) { running++; continue; }
    // High priority wakes the phone right away but iOS rations it; the rest go at low priority, which iOS may hold a little.
    const hi = !r.last_hi || now - Date.parse(r.last_hi) >= 2 * 60000 || r.last_state?.what !== st.what;
    const res = await apns(r, { timestamp: ts, event: "update", "content-state": st, "stale-date": ts + 600 }, hi ? 10 : 5, jwt);
    if (deadToken(res)) await rest(`room_live?id=eq.${id}`, "PATCH", { ended_at: iso });
    else {
      running++;
      if (res.status === 200) await rest(`room_live?id=eq.${id}`, "PATCH", { last_state: st, last_push: iso, ...(hi ? { last_hi: iso } : {}) });
    }
    out.push({ update: r.id, hi, ...res });
  }
  if (home && !running && start && (!start.last_push || now - Date.parse(start.last_push) > 15 * 60000)) {
    const res = await apns(start, {
      timestamp: ts, event: "start", "content-state": st, "stale-date": ts + 600, "attributes-type": "RoomAttributes", attributes: {},
      alert: { title: "Room", body: "Live readings are on" },
    }, 10, jwt);
    if (deadToken(res)) await rest("room_live?id=eq.start", "DELETE");
    else await rest("room_live?id=eq.start", "PATCH", { last_push: iso });
    out.push({ start: true, ...res });
  }
  return out;
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
    if (req.method === "GET") {
      // The Awake / Sleeping / Away switch lives on the server (lights_presence), so the app shows what the controller is using.
      const [snap, me] = await Promise.all([rpc("room_snapshot"), fetch(`${BASE}/rest/v1/lights_presence?person=eq.me&select=state`, { headers: dbHeaders }).then((r) => r.json()).catch(() => null)]);
      return reply({ ...snap, me: me?.[0]?.state ?? null });
    }
    if (req.method !== "POST") return reply({ error: "method" }, 405);
    const body = await req.json().catch(() => ({}));
    if (body.action === "tick") {
      if (label !== "cron tick") return reply({ error: "key" }, 401);
      const r = await tick(key);
      const lv = await rpc("room_tick_data").then(live).catch((e) => ({ error: (e as Error).message.slice(0, 200) }));
      return reply({ ...r, live: lv });
    }
    if (body.action === "live_token") {
      const env = body.env === "production" ? "production" : "sandbox";
      const tok = typeof body.token === "string" && /^[0-9a-f]{32,400}$/.test(body.token) ? body.token : null;
      const id = typeof body.id === "string" && /^[A-Za-z0-9-]{1,64}$/.test(body.id) && body.id !== "start" && body.id !== "apns_jwt" ? body.id : null;
      const up = (row: Record<string, unknown>) => rest("room_live?on_conflict=id", "POST", row, "resolution=merge-duplicates,return=minimal");
      if (body.kind === "start" && tok) await up({ id: "start", kind: "start", token: tok, env });
      else if (body.kind === "update" && tok && id) await up({ id, kind: "update", token: tok, env, ended_at: null });
      else if (body.kind === "ended" && id) await rest(`room_live?id=eq.${encodeURIComponent(id)}`, "PATCH", { ended_at: new Date().toISOString() });
      else return reply({ error: "bad token" }, 400);
      return reply({ ok: true });
    }
    if (body.action === "live_state") {
      const d = await rpc("room_tick_data");
      return reply(liveState(d.snap, d.me, d.last));
    }
    if (body.action === "subscribe") {
      const s = body.sub ?? {};
      const ok = typeof s.endpoint === "string" && s.endpoint.startsWith("https://") && s.endpoint.length < 1000 && typeof s.keys?.p256dh === "string" && typeof s.keys?.auth === "string"
        && s.keys.p256dh.length < 200 && s.keys.auth.length < 100;
      if (!ok) return reply({ error: "bad subscription" }, 400);
      await rest("room_push_subs?on_conflict=endpoint", "POST", { endpoint: s.endpoint, p256dh: s.keys.p256dh, auth: s.keys.auth }, "resolution=merge-duplicates,return=minimal");
      return reply({ ok: true });
    }
    if (body.action === "mode") {
      const state = ({ awake: "home", sleep: "asleep", away: "away" } as Record<string, string>)[body.mode];
      if (!state) return reply({ error: "bad mode" }, 400);
      await rest(`room_blind?id=eq.1`, "PATCH", { steered_at: null }); // a new mode means a new target: steer right away
      await rest(`lights_presence?person=eq.me&state=neq.${state}`, "PATCH", { state, since: new Date().toISOString() });
      return reply({ ok: true, state });
    }
    if (body.action === "test") {
      const d = await rpc("room_tick_data");
      return reply(await push(d.subs, "Alerts are on. You'll hear from me when something should change.", d.vapid_private));
    }
    if (body.action === "thermal") {
      if (label !== "thermal camera") return reply({ error: "key" }, 401);
      const s = body.stats ?? {};
      const num = (v: unknown, lo = -40, hi = 150) => (typeof v === "number" && Number.isFinite(v) && v >= lo && v <= hi ? Math.round(v * 100) / 100 : null);
      const f = body.frame;
      const frame = f && f.w === 80 && f.h === 62 && typeof f.dc_i16_b64 === "string" && f.dc_i16_b64.length <= 14000 ? f : null;
      const stats = JSON.stringify(s).length <= 4000 ? s : {};
      await rest("room_thermal", "POST", {
        window_c: num(s.window_c), unit_c: num(s.unit_c), unit_state: ["heating", "cooling", "off"].includes(s.unit_state) ? s.unit_state : null,
        unit_leak: typeof s.unit_leak === "boolean" ? s.unit_leak : null, walls_c: num(s.walls_c), floor_c: num(s.floor_c), floor_min_c: num(s.floor_min_c),
        bed_c: num(s.bed_c), head_c: num(s.head_c), in_bed: typeof s.in_bed === "boolean" ? s.in_bed : null,
        people_px: num(s.people_px, 0, 5000), stats, frame,
      });
      // Whole frames are kept for 30 days; the minute summaries stay.
      if (new Date().getMinutes() === 0) await rest(`room_thermal?ts=lt.${new Date(Date.now() - 30 * 864e5).toISOString()}&frame=not.is.null`, "PATCH", { frame: null }).catch(() => {});
      return reply({ ok: true });
    }
    return reply({ error: "action" }, 400);
  } catch (e) {
    return reply({ error: "server", detail: (e as Error).message.slice(0, 200) }, 502);
  }
});
