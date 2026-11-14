const { chromium } = require('playwright');
const fs = require('fs');
const body = fs.readFileSync(__dirname + '/../artifact.html', 'utf8').replace(/<link[^>]*fonts[^>]*>/, '');
const snapRow = { now: '2026-11-12T18:50:10Z',
  bed: { ts: '2026-11-12T18:50:00Z', temp_c: 19.1, humidity: 47, co2: 1040, battery: 100 },
  desk: { ts: '2026-11-12T18:50:00Z', temp_c: 19.4, humidity: 46, battery: 60 },
  bed_now: { temp_c: 19.1, co2: 1040, n: 6 }, bed_prev: { temp_c: 18.9, co2: 900, n: 8 },
  outdoor: { ts: '2026-11-12T18:50:00Z', temp_c: 7.1, wind_ms: 6.7, wind_dir_deg: 343, low_next10h_c: -1.5 },
  trend: { bed_c: 0.3, co2: -40, desk_c: 0.02, out_c: null }, pc: { ts: null, watts: null, n: 0 }, state: { ts: '2026-11-12T17:00:00Z', window_in: 0, fan: 'off', people: 1, mode: 'awake', pc: 'idle' } };
const payload = { result: 'Below is the result...\n\n<untrusted-data-06f27527-2814-4ed4-9635-61b1d6aead9e>\n' + JSON.stringify([{ snap: snapRow }]) + '\n</untrusted-data-06f27527-2814-4ed4-9635-61b1d6aead9e>\n\nUse this data' };
const html = '<!doctype html><html><head><script>window.claude={use:async()=>({callTool:async()=>({content:[],payload:'+JSON.stringify(payload)+'})})}</'+'script><meta charset=utf8><meta name=viewport content="width=device-width,initial-scale=1"><style>body{margin:0;font:14px system-ui}[hidden]{display:none!important}</style></head><body>' + body + '</body></html>';
(async () => {
  const b = await chromium.launch();
  for (const [name, scheme, mode] of [['dark', 'dark', 'sleep']]) {
    const p = await b.newPage({ viewport: { width: 393, height: 640 }, colorScheme: scheme });
    p.on('pageerror', e => console.log('PAGEERROR', e.message));
    await p.addInitScript(pl => { window.claude = { use: async () => ({ callTool: async () => ({ content: [], payload: pl }) }) }; }, payload);
    await p.setContent(html); await p.waitForTimeout(400);
    
    await p.screenshot({ path: __dirname + `/coach_${name}.png`, fullPage: false });
    const out = await p.evaluate(() => {
      const base = { watts: 100, ageMin: 1, slope: 0, deskF: 70, co2: 700, phase: null };
      const run = o => { const a = advise(Object.assign({}, base, o)); return a.error || [a.door, a.window, a.fan, a.conf, a.phase, a.why].join(' | '); };
      return {
        sleep_hot: run({ mode: 'sleep', bedF: 71, outF: 40, lowF: 36 }),
        sleep_precool_cont: run({ mode: 'sleep', bedF: 67.8, outF: 40, lowF: 36, phase: 'precool' }),
        sleep_hold: run({ mode: 'sleep', bedF: 66.6, outF: 40, lowF: 40 }),
        sleep_cold: run({ mode: 'sleep', bedF: 63.5, outF: 30, lowF: 28 }),
        awake_mid: run({ mode: 'awake', bedF: 69, outF: 45 }),
        awake_hot: run({ mode: 'awake', bedF: 74, deskF: 75, outF: 45, watts: 350 }),
        awake_cold: run({ mode: 'awake', bedF: 66, deskF: 66, outF: 45, co2: 900 }),
        awake_cold_co2: run({ mode: 'awake', bedF: 66, deskF: 66, outF: 45, co2: 1300 }),
        away: run({ mode: 'away', bedF: 69, outF: 45 }), stale: run({ mode: 'sleep', bedF: 69, outF: 45, ageMin: 25 }) };
    });
    console.log(JSON.stringify(out, null, 1));
    console.log('overflow', await p.evaluate(() => document.documentElement.scrollWidth > innerWidth));
    await p.close();
  }
  await b.close();
})();
