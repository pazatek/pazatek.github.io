import re
css=open('core.css').read()+".foot:has(> [hidden]:only-child) { display: none }\n"
html=open('core.html').read(); core=open('core.js').read()
core=core.replace('$("tag").textContent = msg;','$("tag").textContent = "Paused"; $("why").hidden = false; $("why").textContent = msg;')
assert '"Paused"' in core
def cut(s,a,b): i=s.index(a); return s[i:s.index(b,i)]

# ---- Claude artifact ----
art=open('artifact.html').read()
pre=cut(art,'const K = ','function onBlank(')
if 'const STEPS' in pre: pre=pre[:pre.index('const STEPS')]
pre=re.sub(r'/\* -{5,}.*?-{5,} \*/\n','',pre)
tail=art[art.index('function extract(res)'):art.index('</script>')]
tail=re.sub(r'/\* -{5,}.*?-{5,} \*/\n','',tail)
extra='''  <p class="foot" id="why" hidden></p>
  <p class="foot"><button class="link" id="allow" type="button" hidden>Allow Supabase</button></p>'''
hooks='function onBlank(allow) { $("allow").hidden = !allow; }\nfunction onGood() { $("allow").hidden = true; $("why").hidden = true; }\nfunction onBlind() {}\nfunction onLamp() {}\n'
for old in (hooks, hooks.replace('function onLamp() {}\n',''), hooks.replace('function onBlind() {}\nfunction onLamp() {}\n','')): pre=pre.replace(old,'')
out='<title>Room Coach</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n<style>\n'+css.replace('PADBLOCK','padding-block: clamp(8px, 1.8vh, 18px);')+'</style>\n\n'+html.replace('EXTRA',extra)+'\n<script>\n'+pre+hooks+core+tail+'</script>\n'
open('artifact.html','w').write(out)

# ---- home screen app ----
p='../room/index.html'; site=open('site_old.html').read()
head=site[:site.index('<style>')]
pre=cut(site,'const K = ','function show(')
tail=site[site.index('function stale(msg)'):site.index('const alertsBtn')]
extra='''  <div class="list"><div class="row"><span>Blind</span><div class="pick" id="blind"><button type="button" data-p="0" aria-pressed="false">Up</button><button type="button" data-p="50" aria-pressed="false">Half</button><button type="button" data-p="100" aria-pressed="false">Down</button><button type="button" data-p="auto" aria-pressed="false">Auto</button></div></div>
  <div class="row"><span>Alerts</span><span class="note" id="alerts-note"></span><button class="switch" id="alerts" type="button" role="switch" aria-checked="false" aria-label="Alerts"></button></div></div>
  <p class="foot" id="why" hidden></p>
  <form class="foot key" id="keyform" hidden><input id="key" type="password" autocomplete="off" aria-label="App key" placeholder="App key"><button class="link" type="submit">Save</button></form>
  <section class="lampcard" id="lampcard" role="dialog" aria-labelledby="lamp-name" hidden>
    <div class="lc-head"><span id="lamp-name">Lamp</span><span class="lc-note" id="lamp-note"></span><button class="lc-pow" id="lamp-on" type="button" role="switch" aria-checked="false" aria-label="Lamp on"></button></div>
    <div class="lc-sl" id="lamp-b" role="slider" aria-label="Brightness" aria-valuemin="1" aria-valuemax="100" tabindex="0"><i class="lc-ic sun"></i><span class="lc-track"><span class="lc-fill"></span><span class="lc-thumb"></span></span><span class="lc-v" id="lamp-b-v"></span></div>
    <div class="lc-sl kel" id="lamp-k" role="slider" aria-label="Color temperature" aria-valuemin="2700" aria-valuemax="6500" tabindex="0"><i class="lc-ic therm"></i><span class="lc-track"><span class="lc-thumb"></span></span><span class="lc-v" id="lamp-k-v"></span></div>
    <div class="lc-wheel" id="lamp-wheel" role="slider" aria-label="Color"><i id="lamp-dot" hidden></i></div>
    <div class="lc-ms" id="lamp-ms"></div>
  </section>'''
hooks='const PHOTO_BASE = "photo/";\nfunction onBlank(askKey) { $("keyform").hidden = !askKey; }\nfunction onGood() { $("keyform").hidden = true; $("why").hidden = true; }\nfunction onBlind(p, steering) { for (const b of document.querySelectorAll("#blind button")) b.setAttribute("aria-pressed", String(b.dataset.p === "auto" ? steering : !steering && p != null && Math.abs(p - Number(b.dataset.p)) <= 12)); }\n'
alerts='''const alertsBtn = $("alerts"), alertsNote = $("alerts-note");
const pushOk = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
function alertsShow(on, note) { alertsBtn.setAttribute("aria-checked", String(on)); alertsNote.textContent = note || ""; }
function keyBytes(s) {
  const p = s.replace(/-/g, "+").replace(/_/g, "/"), raw = atob(p + "=".repeat((4 - p.length % 4) % 4));
  return Uint8Array.from(raw, c => c.charCodeAt(0));
}
async function post(body) {
  const r = await fetch(ENDPOINT, { method: "POST", headers: { "x-room-key": key, "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error("http " + r.status);
  return r.json();
}
async function alertsState() {
  if (!pushOk) { alertsBtn.disabled = true; alertsShow(false, "Add to Home Screen first"); return; }
  const reg = await navigator.serviceWorker.register("sw.js"), sub = await reg.pushManager.getSubscription();
  alertsShow(!!sub && Notification.permission === "granted", Notification.permission === "denied" ? "Blocked in Settings" : "");
}
alertsBtn.addEventListener("click", async () => {
  if (!pushOk || !key) return;
  try {
    if (alertsBtn.getAttribute("aria-checked") === "true") {
      const sub = await (await navigator.serviceWorker.ready).pushManager.getSubscription();
      if (sub) await sub.unsubscribe();
      alertsShow(false);
      return;
    }
    // iOS only shows the permission prompt if this is the first thing awaited after the tap.
    if (await Notification.requestPermission() !== "granted") { alertsShow(false, "Blocked in Settings"); return; }
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription() || await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(VAPID) });
    await post({ action: "subscribe", sub: sub.toJSON() });
    const sent = await post({ action: "test" });
    alertsShow(sent.sent > 0, sent.sent > 0 ? "" : "Couldn't turn on");
  } catch (e) { alertsShow(false, "Couldn't turn on"); }
});
alertsState().catch(() => {});

const BLIND = ENDPOINT.replace(/room$/, "blind");
for (const b of document.querySelectorAll("#blind button")) b.addEventListener("click", () => {
  if (!key) return;
  // The motor takes up to half a minute to travel; until then the stored position is the old one, so show the target.
  const auto = b.dataset.p === "auto";
  if (!auto) { blindPct = Number(b.dataset.p); blindHold = performance.now() + 40000; render(); }
  fetch(BLIND, { method: "POST", headers: { "x-room-key": key, "Content-Type": "application/json" }, body: JSON.stringify(auto ? { auto: true } : { percent: blindPct }) })
    .then(r => { if (!r.ok) throw new Error("http " + r.status); })
    .catch(() => { blindHold = 0; stale("Couldn't reach the blind."); });
});
// Reading the blind is what records its position for the snapshot, so manual moves show up too.
const blindPoll = () => { if (key && !document.hidden) fetch(BLIND, { headers: { "x-room-key": key }, cache: "no-store" }).catch(() => {}); };
setInterval(blindPoll, 15000); blindPoll();

// Lamps go through a relay on the PC at home, reached over a live channel: no request per tap, so a tap costs one websocket frame.
const LIVE = "wss://hxaftcofwrffwjxtjeoj.supabase.co/realtime/v1/websocket?apikey=sb_publishable_4TJE66VMSen-hl22kWL-Rw_8RXH_UOH&vsn=1.0.0", TOPIC = "realtime:room-lights";
const lamps = { pixar: true, little: true }, lampHold = {}, relays = new Set(), utf8 = new TextEncoder();
let live = null, liveRef = 0, liveBeat = 0, signer = null;
const liveSend = (topic, event, payload) => { if (live && live.readyState === 1) live.send(JSON.stringify({ topic, event, payload, ref: String(++liveRef) })); };
const noteRelays = (map, add) => { for (const [id, v] of Object.entries(map || {})) if ((v.metas || []).some(m => m.relay)) add ? relays.add(id) : relays.delete(id); };
function liveOpen() {
  if (!key || document.hidden || (live && live.readyState < 2)) return;
  live = new WebSocket(LIVE);
  live.onopen = () => {
    liveSend(TOPIC, "phx_join", { config: { broadcast: { self: false, ack: false }, presence: { key: "", enabled: true }, private: false } });
    liveSend(TOPIC, "broadcast", { type: "broadcast", event: "hello", payload: {} });
    clearInterval(liveBeat); liveBeat = setInterval(() => liveSend("phoenix", "heartbeat", {}), 25000);
  };
  live.onmessage = e => {
    let m; try { m = JSON.parse(e.data); } catch (err) { return; }
    if (m.event === "presence_state") { relays.clear(); noteRelays(m.payload, true); if (sheetLamp) paintSheet(); }
    else if (m.event === "presence_diff") { noteRelays(m.payload.leaves, false); noteRelays(m.payload.joins, true); if (sheetLamp) paintSheet(); }
    else if (m.event === "broadcast" && m.payload && m.payload.event === "state") {
      const s = m.payload.payload;
      // Right after a tap the relay may still report the old state; the tap wins until the bulb has had time to answer.
      if (!s || !(s.lamp in lamps)) return;
      if (performance.now() >= (lampHold[s.lamp] || 0)) {
        Object.assign(lampState[s.lamp], s);
        if (lamps[s.lamp] !== !!s.on) { lamps[s.lamp] = !!s.on; viz.lamps(lamps); }
        viz.light(s.lamp, { ...lampState[s.lamp], on: lamps[s.lamp] });
      } else lampState[s.lamp].online = s.online;
      if (sheetLamp === s.lamp) paintSheet();
    }
    else if (m.event === "broadcast" && m.payload && m.payload.event === "done") {
      // Tap to bulb: half the round trip minus the relay's own time is the network one way, then the bulb's acknowledgement.
      const d = m.payload.payload, at = d && sentAt.get(d.t);
      if (!at) return;
      sentAt.delete(d.t);
      recentMs.push(Math.max(0, (performance.now() - at - d.total) / 2) + d.bulb);
      if (recentMs.length > 9) recentMs.shift();
      const med = [...recentMs].sort((a, b) => a - b)[recentMs.length >> 1];
      $("lamp-ms").textContent = "tap to lamp " + Math.round(med) + " ms";
    }
  };
  live.onclose = () => { clearInterval(liveBeat); relays.clear(); setTimeout(liveOpen, 2000); };
}
document.addEventListener("visibilitychange", liveOpen);
liveOpen();
// Tapping a lamp opens a small card beside it: power, brightness, colour temperature and a colour wheel. Every change is a signed command
// (HMAC over "lamp|on|brightness|k|hue|sat|t", with a key from the lamp function) that the relay on the PC checks before touching the bulb.
const lampNames = { pixar: "Pixar lamp", little: "Little lamp" }, lampState = { pixar: {}, little: {} }, pend = {}, lastSent = {}, pendTimer = {};
let sheetLamp = null;
const sentAt = new Map(), recentMs = [];
const hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, "0")).join("");
async function lampFlush(id) {
  const f = pend[id]; pend[id] = null; pendTimer[id] = 0;
  if (!f) return;
  lastSent[id] = performance.now(); lampHold[id] = performance.now() + 1500;
  const t = Date.now(), c = { lamp: id, ...f, t }, val = v => (v == null ? "" : String(v));
  const tk = await lampToken();
  if (!tk) { stale("Couldn't get a lamp key. Check the connection."); return; }
  const mac = await crypto.subtle.sign("HMAC", tk.signer, utf8.encode([id, c.on, c.brightness, c.k, c.hue, c.sat, t].map(val).join("|")));
  sentAt.set(t, performance.now()); if (sentAt.size > 50) sentAt.delete(sentAt.keys().next().value);
  liveSend(TOPIC, "broadcast", { type: "broadcast", event: "cmd", payload: { ...c, exp: tk.exp, sig: hex(mac) } });
}
// Commands are signed with a 12-hour key from the lamp function (it checks the app key); the relay derives the same key itself.
const LAMP = ENDPOINT.replace(/room$/, "lamp");
let lampTok = null, lampTokP = null;
function lampToken() {
  if (lampTok && lampTok.exp - Date.now() > 3600000) return Promise.resolve(lampTok);
  return lampTokP = lampTokP || fetch(LAMP, { method: "POST", headers: { "x-room-key": key, "Content-Type": "application/json" }, body: JSON.stringify({ action: "token" }) })
    .then(r => { if (!r.ok) throw new Error("http " + r.status); return r.json(); })
    .then(async j => {
      const raw = Uint8Array.from(j.key.match(/../g).map(x => parseInt(x, 16)));
      return lampTok = { exp: j.exp, signer: await crypto.subtle.importKey("raw", raw, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]) };
    })
    .catch(() => (lampTok = null))
    .finally(() => { lampTokP = null; });
}
// A dragged control sends at most every 80 ms; the last position always goes out. The relay fades each step over 0.2 s while
// commands keep coming, so the bulb glides instead of stepping.
function lampSend(id, f) {
  if (!key) return;
  const p = pend[id] || {};
  if (f.k != null) { delete p.hue; delete p.sat; }
  if (f.hue != null) delete p.k;
  pend[id] = { ...p, ...f };
  const wait = 80 - (performance.now() - (lastSent[id] || 0));
  if (wait <= 0) lampFlush(id); else if (!pendTimer[id]) pendTimer[id] = setTimeout(() => lampFlush(id), wait);
}
const card = $("lampcard"), lampB = $("lamp-b"), lampK = $("lamp-k"), wheel = $("lamp-wheel"), dot = $("lamp-dot");
const K_LO = 2700, K_HI = 6500;
// Thin sliders: grab anywhere on the row and drag; the thumb follows the finger every frame.
function slider(el, lo, hi, onMove) {
  const set = v => el.style.setProperty("--v", Math.max(0, Math.min(1, (v - lo) / (hi - lo))));
  const at = e => { const r = el.querySelector(".lc-track").getBoundingClientRect(); return lo + Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * (hi - lo); };
  el.addEventListener("pointerdown", e => { el.setPointerCapture(e.pointerId); el.classList.add("drag"); const v = at(e); set(v); onMove(v); });
  el.addEventListener("pointermove", e => { if (!el.hasPointerCapture(e.pointerId)) return; const v = at(e); set(v); onMove(v); });
  const end = () => el.classList.remove("drag");
  el.addEventListener("pointerup", end); el.addEventListener("pointercancel", end);
  el.addEventListener("keydown", e => { const step = (hi - lo) / 20, cur = lo + Number(el.style.getPropertyValue("--v") || 0) * (hi - lo);
    if (e.key === "ArrowRight" || e.key === "ArrowUp") { e.preventDefault(); set(cur + step); onMove(Math.min(hi, cur + step)); }
    if (e.key === "ArrowLeft" || e.key === "ArrowDown") { e.preventDefault(); set(cur - step); onMove(Math.max(lo, cur - step)); } });
  return set;
}
const lit = id => { if (!lamps[id]) { lamps[id] = true; lampState[id].on = true; viz.lamps(lamps); } };
const setB = slider(lampB, 1, 100, v => { const id = sheetLamp, b = Math.round(v); lampState[id].brightness = b; lit(id); paintSheet(); lampSend(id, { brightness: b }); });
const setK = slider(lampK, K_LO, K_HI, v => { const id = sheetLamp, k = Math.round(v / 10) * 10; Object.assign(lampState[id], { k, mode: "ct" }); lit(id); paintSheet(); lampSend(id, { k }); });
function paintSheet() {
  const id = sheetLamp, s = lampState[id], on = !!lamps[id];
  viz.light(id, { ...s, on });
  $("lamp-name").textContent = lampNames[id];
  $("lamp-on").setAttribute("aria-checked", String(on));
  card.classList.toggle("off", !on);
  $("lamp-note").textContent = !relays.size ? "Relay offline" : s.online === false ? "Bulb offline" : "";
  const b = s.brightness || 100, k = s.k || K_LO;
  if (!lampB.classList.contains("drag")) setB(b);
  if (!lampK.classList.contains("drag")) setK(k);
  lampB.setAttribute("aria-valuenow", b); lampK.setAttribute("aria-valuenow", k);
  $("lamp-b-v").textContent = b + "%";
  $("lamp-k-v").textContent = s.mode === "hs" ? "color" : Math.round(k / 50) * 50 + "K";
  dot.hidden = s.mode !== "hs" || s.hue == null;
  if (!dot.hidden) {
    const a = s.hue * Math.PI / 180, r = Math.min(1, (s.sat || 0) / 100) * 50;
    dot.style.left = 50 + r * Math.cos(a) + "%"; dot.style.top = 50 + r * Math.sin(a) + "%";
    dot.style.background = "hsl(" + s.hue + " " + (s.sat || 0) + "% " + (100 - (s.sat || 0) / 2) + "%)";
  }
}
// The card sits beside the lamp in the picture, on whichever side has room, kept inside the room view.
function placeCard() {
  if (!sheetLamp) return;
  const [x, y] = viz.spot(sheetLamp), hero = $("room").getBoundingClientRect(), w = card.offsetWidth, h = card.offsetHeight, gap = 26, m = 8;
  const right = x + gap + w <= hero.right - m || x - gap - w < hero.left + m;
  const left = right ? Math.min(x + gap, hero.right - m - w) : x - gap - w;
  const top = Math.max(hero.top + m, Math.min(y - h / 2, hero.bottom - m - h));
  card.style.left = Math.max(m, left) + "px"; card.style.top = top + "px";
  card.style.setProperty("--ox", right ? "0" : "100%");
}
function onLamp(id) {
  if (!key) return;
  sheetLamp = id; liveOpen(); lampToken();
  card.hidden = false; $("lamp-ms").textContent = recentMs.length ? $("lamp-ms").textContent : "";
  paintSheet(); placeCard();
}
function closeSheet() { sheetLamp = null; card.hidden = true; }
// Any touch outside the card closes it; a touch on the other lamp then opens that one.
document.addEventListener("pointerdown", e => { if (sheetLamp && !card.contains(e.target)) closeSheet(); }, true);
document.addEventListener("keydown", e => { if (e.key === "Escape" && sheetLamp) closeSheet(); });
addEventListener("resize", placeCard);
$("lamp-on").addEventListener("click", () => {
  const id = sheetLamp, on = !lamps[id];
  lamps[id] = on; lampState[id].on = on; viz.lamps(lamps); paintSheet();
  lampSend(id, { on });
});
function wheelAt(e) {
  const r = wheel.getBoundingClientRect(), dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height / 2);
  const hue = Math.round((Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360), sat = Math.round(Math.min(1, Math.hypot(dx, dy) / (r.width / 2)) * 100);
  const id = sheetLamp; Object.assign(lampState[id], { hue, sat, mode: "hs" }); lit(id); paintSheet(); lampSend(id, { hue, sat });
}
wheel.addEventListener("pointerdown", e => { wheel.setPointerCapture(e.pointerId); wheelAt(e); });
wheel.addEventListener("pointermove", e => { if (wheel.hasPointerCapture(e.pointerId)) wheelAt(e); });
'''
pad='padding-top: calc(env(safe-area-inset-top, 0px) + clamp(8px, 1.8vh, 18px)); padding-bottom: calc(env(safe-area-inset-bottom, 0px) + clamp(8px, 1.8vh, 18px));'
sheetcss='''.lampcard { position: fixed; z-index: 10; width: 196px; padding: 10px 12px 8px; border-radius: 18px; display: flex; flex-direction: column; gap: 9px;
  background: rgba(28, 28, 30, 0.72); -webkit-backdrop-filter: blur(18px) saturate(1.5); backdrop-filter: blur(18px) saturate(1.5);
  border: 0.5px solid rgba(255, 255, 255, 0.14); box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45); animation: lc-in 0.16s ease-out; transform-origin: var(--ox, 0) 50% }
@keyframes lc-in { from { opacity: 0; transform: scale(0.9) } }
.lc-head { display: flex; align-items: center; gap: 6px; font: 600 14px/1.2 var(--display) }
.lc-note { flex: 1; font: 500 11px/1.2 var(--body); color: var(--dim); text-align: right }
.lc-pow { flex: none; width: 30px; height: 30px; margin-left: auto; border: 0; border-radius: 50%; background: rgba(255, 255, 255, 0.14); position: relative }
.lc-pow::after { content: ""; position: absolute; inset: 7px; background: currentColor; -webkit-mask: var(--pow) center / contain no-repeat; mask: var(--pow) center / contain no-repeat }
.lc-pow[aria-checked="true"] { background: #ffd57a; color: #1c1c1e }
.lampcard { --pow: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2.4' stroke-linecap='round'%3E%3Cpath d='M12 3v8M6.3 6.8a8 8 0 1 0 11.4 0'/%3E%3C/svg%3E") }
.lc-sl { display: flex; align-items: center; gap: 7px; height: 26px; touch-action: none; cursor: pointer; outline: none }
.lc-ic { flex: none; width: 13px; height: 13px; background: var(--dim) }
.lc-ic.sun { -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2.4' stroke-linecap='round'%3E%3Ccircle cx='12' cy='12' r='4'/%3E%3Cpath d='M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4'/%3E%3C/svg%3E") center / contain no-repeat;
  mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2.4' stroke-linecap='round'%3E%3Ccircle cx='12' cy='12' r='4'/%3E%3Cpath d='M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4'/%3E%3C/svg%3E") center / contain no-repeat }
.lc-ic.therm { -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2.4' stroke-linecap='round'%3E%3Cpath d='M14 14.8V4a2 2 0 0 0-4 0v10.8a4 4 0 1 0 4 0z'/%3E%3C/svg%3E") center / contain no-repeat;
  mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2.4' stroke-linecap='round'%3E%3Cpath d='M14 14.8V4a2 2 0 0 0-4 0v10.8a4 4 0 1 0 4 0z'/%3E%3C/svg%3E") center / contain no-repeat }
.lc-track { position: relative; flex: 1; height: 6px; border-radius: 3px; background: rgba(255, 255, 255, 0.16) }
.lc-fill { position: absolute; left: 0; top: 0; bottom: 0; width: calc(var(--v, 0) * 100%); border-radius: 3px; background: #fff6e6 }
.kel .lc-track { background: linear-gradient(90deg, #ffa84f, #fff1dc 45%, #cfe0ff) }
.lc-thumb { position: absolute; top: 50%; left: calc(var(--v, 0) * 100%); width: 18px; height: 18px; margin: -9px 0 0 -9px; border-radius: 50%; background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.5); transition: transform 0.12s }
.lc-sl.drag .lc-thumb { transform: scale(1.25) }
.lc-v { flex: none; width: 42px; text-align: right; font: 500 11px/1 var(--body); color: var(--dim); font-variant-numeric: tabular-nums }
.lc-wheel { position: relative; width: 104px; aspect-ratio: 1; margin: 2px auto 0; border-radius: 50%; touch-action: none; cursor: crosshair;
  background: radial-gradient(circle closest-side, #fff, rgba(255, 255, 255, 0)), conic-gradient(from 90deg, #f00, #ff0, #0f0, #0ff, #00f, #f0f, #f00) }
.lc-wheel i { position: absolute; width: 20px; height: 20px; margin: -10px 0 0 -10px; border-radius: 50%; border: 2.5px solid #fff; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.5); pointer-events: none }
.lc-ms { min-height: 12px; font: 500 10px/1.2 var(--body); color: var(--dim); text-align: center; font-variant-numeric: tabular-nums }
.lampcard.off .lc-sl, .lampcard.off .lc-wheel { opacity: 0.4 }
'''
out=head+'<style>\n'+css.replace('PADBLOCK',pad)+sheetcss+'</style>\n</head>\n<body>\n'+html.replace('EXTRA',extra)+'<script>\n'+pre+hooks+core+tail+alerts+'</script>\n</body>\n</html>\n'
open(p,'w').write(out)
print('built', len(out))
