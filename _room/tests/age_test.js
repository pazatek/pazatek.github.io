const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 393, height: 852 }, deviceScaleFactor: 2 });
  p.on('pageerror', e => console.log('PAGEERROR', e.message));
  await p.goto('file://' + __dirname + '/../../room/index.html'); await p.waitForTimeout(300);
  await p.evaluate(() => { const n = Date.now(), iso = d => new Date(n - d * 1000).toISOString();
    snap = { now: iso(0), bed: { ts: iso(20), temp_c: 21.2, humidity: 52, co2: 2303, battery: 100 }, desk: { ts: iso(20), temp_c: 20.1, humidity: 60, battery: 60 },
      bed_now: { temp_c: 21.3, co2: 2400, n: 12 }, bed_prev: { temp_c: 22, co2: 3000, n: 16 }, outdoor: { ts: iso(100), temp_c: 2.2, wind_ms: 3.4, wind_dir_deg: 330, low_next10h_c: -2, sun_wm2: 0 },
      pc: { ts: iso(30), watts: 180, n: 5 }, state: { ts: iso(9000), window_in: 26, fan: "off", people: 1, mode: "awake", pc: "idle" }, trend: { bed_c: -0.4, co2: -550, desk_c: -1.1, out_c: null },
      since: { bed_c: iso(42), co2: iso(190), desk_c: iso(15), out_c: iso(4000) }, blind: { percent: 0, ts: iso(20), hold_until: null, auto: true, steering: true } };
    snapAt = performance.now(); render(); });
  await p.waitForTimeout(1500);
  console.log(await p.evaluate(() => ["t-desk","t-bed","co2","out"].map(i => document.getElementById("age-" + i).textContent).join(" | ")));
  console.log(await p.evaluate(() => document.documentElement.scrollHeight + ' ' + innerHeight));
  await p.screenshot({ path: __dirname + '/age.png', clip: { x: 0, y: 380, width: 393, height: 472 } }); await b.close(); })();
