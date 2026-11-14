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
  <form class="foot key" id="keyform" hidden><input id="key" type="password" autocomplete="off" aria-label="App key" placeholder="App key"><button class="link" type="submit">Save</button></form>'''
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
    liveSend(TOPIC, "phx_join", { config: { broadcast: { self: false, ack: false }, presence: { key: "" }, private: false } });
    liveSend(TOPIC, "broadcast", { type: "broadcast", event: "hello", payload: {} });
    clearInterval(liveBeat); liveBeat = setInterval(() => liveSend("phoenix", "heartbeat", {}), 25000);
  };
  live.onmessage = e => {
    let m; try { m = JSON.parse(e.data); } catch (err) { return; }
    if (m.event === "presence_state") { relays.clear(); noteRelays(m.payload, true); }
    else if (m.event === "presence_diff") { noteRelays(m.payload.leaves, false); noteRelays(m.payload.joins, true); }
    else if (m.event === "broadcast" && m.payload && m.payload.event === "state") {
      const s = m.payload.payload;
      // Right after a tap the relay may still report the old state; the tap wins until the bulb has had time to answer.
      if (s && s.lamp in lamps && performance.now() >= (lampHold[s.lamp] || 0) && lamps[s.lamp] !== !!s.on) { lamps[s.lamp] = !!s.on; viz.lamps(lamps); }
    }
  };
  live.onclose = () => { clearInterval(liveBeat); relays.clear(); setTimeout(liveOpen, 2000); };
}
document.addEventListener("visibilitychange", liveOpen);
liveOpen();
async function onLamp(id) {
  if (!key) return;
  if (!relays.size) { stale("The lamp relay on the PC isn't connected."); return; }
  const on = !lamps[id], t = Date.now();
  lamps[id] = on; lampHold[id] = performance.now() + 1500; viz.lamps(lamps);
  signer = signer || crypto.subtle.importKey("raw", utf8.encode(key), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", await signer, utf8.encode([id, on, "", "", t].join("|")));
  liveSend(TOPIC, "broadcast", { type: "broadcast", event: "cmd", payload: { lamp: id, on, t, sig: [...new Uint8Array(mac)].map(b => b.toString(16).padStart(2, "0")).join("") } });
}
'''
pad='padding-top: calc(env(safe-area-inset-top, 0px) + clamp(8px, 1.8vh, 18px)); padding-bottom: calc(env(safe-area-inset-bottom, 0px) + clamp(8px, 1.8vh, 18px));'
out=head+'<style>\n'+css.replace('PADBLOCK',pad)+'</style>\n</head>\n<body>\n'+html.replace('EXTRA',extra)+'<script>\n'+pre+hooks+core+tail+alerts+'</script>\n</body>\n</html>\n'
open(p,'w').write(out)
print('built', len(out))
