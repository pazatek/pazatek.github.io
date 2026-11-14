const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 393, height: 760 }, deviceScaleFactor: 3 });
  p.on('pageerror', e => console.log('PAGEERROR', e.message));
  await p.goto('file://' + __dirname + '/../../room/index.html'); await p.waitForTimeout(300);
  await p.evaluate(() => viz.set(0, false, 'off', 0)); await p.waitForTimeout(1500);
  await p.screenshot({ path: __dirname + '/full.png', clip: { x: 0, y: 100, width: 393, height: 400 } }); await b.close(); })();
