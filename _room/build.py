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
  <div class="sheet-back" id="lampback" hidden></div>
  <section class="sheet" id="lampsheet" role="dialog" aria-modal="true" aria-labelledby="lamp-name" hidden>
    <div class="grab"></div>
    <div class="row"><span class="sh-title" id="lamp-name">Lamp</span><span class="note" id="lamp-note"></span><button class="switch" id="lamp-on" type="button" role="switch" aria-checked="false" aria-label="Lamp on"></button></div>
    <label class="sl"><span>Brightness</span><span class="note" id="lamp-b-v"></span><input type="range" id="lamp-b" min="1" max="100" step="1"></label>
    <label class="sl"><span>Temperature</span><span class="note" id="lamp-k-v"></span><input type="range" id="lamp-k" min="2700" max="6500" step="50"></label>
    <div class="wheel" id="lamp-wheel" role="slider" aria-label="Color"><i id="lamp-dot" hidden></i></div>
  </section>'''
hooks='function onBlank(askKey) { $("keyform").hidden = !askKey; }\nfunction onGood() { $("keyform").hidden = true; $("why").hidden = true; }\nfunction onBlind(p, steering) { for (const b of document.querySelectorAll("#blind button")) b.setAttribute("aria-pressed", String(b.dataset.p === "auto" ? steering : !steering && p != null && Math.abs(p - Number(b.dataset.p)) <= 12)); }\n'
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
      } else lampState[s.lamp].online = s.online;
      if (sheetLamp === s.lamp) paintSheet();
    }
  };
  live.onclose = () => { clearInterval(liveBeat); relays.clear(); setTimeout(liveOpen, 2000); };
}
document.addEventListener("visibilitychange", liveOpen);
liveOpen();
// Tapping a lamp opens its sheet: power, brightness, colour temperature and a colour wheel. Every change is a signed command
// (HMAC with the app key over "lamp|on|brightness|k|hue|sat|t") that the relay on the PC checks before touching the bulb.
const lampNames = { pixar: "Pixar lamp", little: "Little lamp" }, lampState = { pixar: {}, little: {} }, pend = {}, lastSent = {}, pendTimer = {};
let sheetLamp = null;
const hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, "0")).join("");
async function lampFlush(id) {
  const f = pend[id]; pend[id] = null; pendTimer[id] = 0;
  if (!f) return;
  lastSent[id] = performance.now(); lampHold[id] = performance.now() + 1500;
  const t = Date.now(), c = { lamp: id, ...f, t }, val = v => (v == null ? "" : String(v));
  signer = signer || crypto.subtle.importKey("raw", utf8.encode(key), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", await signer, utf8.encode([id, c.on, c.brightness, c.k, c.hue, c.sat, t].map(val).join("|")));
  liveSend(TOPIC, "broadcast", { type: "broadcast", event: "cmd", payload: { ...c, sig: hex(mac) } });
}
// A dragged slider sends at most every 120 ms; the last position always goes out.
function lampSend(id, f) {
  if (!key) return;
  const p = pend[id] || {};
  if (f.k != null) { delete p.hue; delete p.sat; }
  if (f.hue != null) delete p.k;
  pend[id] = { ...p, ...f };
  const wait = 120 - (performance.now() - (lastSent[id] || 0));
  if (wait <= 0) lampFlush(id); else if (!pendTimer[id]) pendTimer[id] = setTimeout(() => lampFlush(id), wait);
}
const sheet = $("lampsheet"), lampB = $("lamp-b"), lampK = $("lamp-k"), wheel = $("lamp-wheel"), dot = $("lamp-dot");
function paintSheet() {
  const id = sheetLamp, s = lampState[id], on = !!lamps[id];
  $("lamp-name").textContent = lampNames[id];
  $("lamp-on").setAttribute("aria-checked", String(on));
  sheet.classList.toggle("off", !on);
  $("lamp-note").textContent = !relays.size ? "Relay offline" : s.online === false ? "Bulb offline" : "";
  if (document.activeElement !== lampB) lampB.value = s.brightness || 100;
  if (document.activeElement !== lampK) lampK.value = s.k || 2700;
  $("lamp-b-v").textContent = lampB.value + "%";
  $("lamp-k-v").textContent = s.mode === "hs" ? "Color" : Math.round(lampK.value / 50) * 50 + " K";
  dot.hidden = s.mode !== "hs" || s.hue == null;
  if (!dot.hidden) {
    const a = s.hue * Math.PI / 180, r = Math.min(1, (s.sat || 0) / 100) * 50;
    dot.style.left = 50 + r * Math.cos(a) + "%"; dot.style.top = 50 + r * Math.sin(a) + "%";
    dot.style.background = "hsl(" + s.hue + " " + (s.sat || 0) + "% " + (100 - (s.sat || 0) / 2) + "%)";
  }
}
function onLamp(id) {
  if (!key) return;
  sheetLamp = id; liveOpen();
  sheet.hidden = false; $("lampback").hidden = false;
  paintSheet();
}
function closeSheet() { sheetLamp = null; sheet.hidden = true; $("lampback").hidden = true; }
$("lampback").addEventListener("click", closeSheet);
document.addEventListener("keydown", e => { if (e.key === "Escape" && sheetLamp) closeSheet(); });
$("lamp-on").addEventListener("click", () => {
  const id = sheetLamp, on = !lamps[id];
  lamps[id] = on; lampState[id].on = on; viz.lamps(lamps); paintSheet();
  lampSend(id, { on });
});
const lit = id => { if (!lamps[id]) { lamps[id] = true; lampState[id].on = true; viz.lamps(lamps); } };
lampB.addEventListener("input", () => { const id = sheetLamp, b = Number(lampB.value); lampState[id].brightness = b; lit(id); paintSheet(); lampSend(id, { brightness: b }); });
lampK.addEventListener("input", () => { const id = sheetLamp, k = Number(lampK.value); Object.assign(lampState[id], { k, mode: "ct" }); lit(id); paintSheet(); lampSend(id, { k }); });
function wheelAt(e) {
  const r = wheel.getBoundingClientRect(), dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height / 2);
  const hue = Math.round((Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360), sat = Math.round(Math.min(1, Math.hypot(dx, dy) / (r.width / 2)) * 100);
  const id = sheetLamp; Object.assign(lampState[id], { hue, sat, mode: "hs" }); lit(id); paintSheet(); lampSend(id, { hue, sat });
}
wheel.addEventListener("pointerdown", e => { wheel.setPointerCapture(e.pointerId); wheelAt(e); });
wheel.addEventListener("pointermove", e => { if (wheel.hasPointerCapture(e.pointerId)) wheelAt(e); });
'''
pad='padding-top: calc(env(safe-area-inset-top, 0px) + clamp(8px, 1.8vh, 18px)); padding-bottom: calc(env(safe-area-inset-bottom, 0px) + clamp(8px, 1.8vh, 18px));'
sheetcss='''.sheet-back { position: fixed; inset: 0; z-index: 9; background: rgba(0, 0, 0, 0.4) }
.sheet { position: fixed; left: 0; right: 0; bottom: 0; z-index: 10; max-width: 440px; margin: 0 auto; background: var(--card); border-radius: 22px 22px 0 0;
  padding: 8px 20px calc(env(safe-area-inset-bottom, 0px) + 18px); display: flex; flex-direction: column; gap: 16px; animation: sheet-up 0.22s ease-out }
@keyframes sheet-up { from { transform: translateY(100%) } }
.grab { width: 36px; height: 5px; border-radius: 3px; background: var(--raised); margin: 0 auto }
.sheet .row { min-height: 36px }
.sh-title { font: 600 20px/1.2 var(--display); letter-spacing: -0.01em }
.sl { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 8px 12px; font-size: 15px; font-weight: 500 }
.sl .note { font-variant-numeric: tabular-nums }
.sl input { grid-column: 1 / -1; width: 100%; margin: 0; height: 34px; border-radius: 17px; -webkit-appearance: none; appearance: none; touch-action: none;
  background: linear-gradient(90deg, #3a3a3c, #fff6e6) }
#lamp-k { background: linear-gradient(90deg, #ffa84f, #fff1dc 45%, #d6e4ff) }
.sl input::-webkit-slider-thumb { -webkit-appearance: none; width: 30px; height: 30px; border-radius: 50%; background: #fff; border: 0; box-shadow: 0 1px 5px rgba(0, 0, 0, 0.5) }
.sl input::-moz-range-thumb { width: 30px; height: 30px; border-radius: 50%; background: #fff; border: 0; box-shadow: 0 1px 5px rgba(0, 0, 0, 0.5) }
.wheel { position: relative; width: min(60vw, 28vh, 230px); aspect-ratio: 1; margin: 0 auto; border-radius: 50%; touch-action: none;
  background: radial-gradient(circle closest-side, #fff, rgba(255, 255, 255, 0)), conic-gradient(from 90deg, #f00, #ff0, #0f0, #0ff, #00f, #f0f, #f00) }
.wheel i { position: absolute; width: 30px; height: 30px; margin: -15px 0 0 -15px; border-radius: 50%; border: 3px solid #fff; box-shadow: 0 1px 5px rgba(0, 0, 0, 0.5); pointer-events: none }
.sheet.off .sl, .sheet.off .wheel { opacity: 0.45 }
'''
out=head+'<style>\n'+css.replace('PADBLOCK',pad)+sheetcss+'</style>\n</head>\n<body>\n'+html.replace('EXTRA',extra)+'<script>\n'+pre+hooks+core+tail+alerts+'</script>\n</body>\n</html>\n'
open(p,'w').write(out)
print('built', len(out))
