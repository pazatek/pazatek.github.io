// Simulates nights in a room whose physics differ from the prior, and compares the old jump controller with the learning one.
// Run: node model_sim.js   (bundles ../functions/model.ts with esbuild first)
const { execSync } = require("child_process"), path = require("path"), os = require("os");
const out = path.join(os.tmpdir(), "room_model_sim.cjs");
execSync(`npx.cmd --yes esbuild@0.24.0 "${path.join(__dirname, "../functions/model.ts")}" --format=cjs --outfile="${out}" --log-level=error`, { stdio: "inherit", shell: true });
const M = require(out);

let seed = 7; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
const TRUE = { c: 170, h: 2.3, gU: 0.7, gD: 0.25, w: 0.4 }; // warmer building, leakier blind than the prior thinks
const AIM = 66.5, q = (f) => Math.round((f - 32) * 5 / 9 * 10) / 10 * 9 / 5 + 32; // 0.1°C sensor

function night(n, ctl, log, t0) {
  const scale = 0.85 + 0.3 * rnd(), th = { ...TRUE, gU: TRUE.gU * scale, gD: TRUE.gD * scale }; // window a bit different each night
  const lowOut = 18 + 20 * rnd();
  let T = 70 + 4 * rnd(), p = 1, lastMove = -1e9, moves = 0, reversals = 0, lastDir = 0, err = 0, errN = 0, early = 0, earlyN = 0;
  const hist = [];
  for (let m = 0; m < 8 * 60; m++) {
    const t = t0 + m * 60000, outF = lowOut + 12 * (1 - m / 480) + (rnd() - 0.5), watts = 100 + (m % 97 < 30 ? 150 : 0);
    const Ts = q(T + (rnd() - 0.5) * 0.1);
    hist.push(Ts); log.push({ t, p, T: Ts, out: outF, watts });
    const target = ctl({ t, T: Ts, hist, p, outF, watts, log, lastMove });
    if (target != null && target !== p) { moves++; const dir = Math.sign(target - p); if (lastDir && dir !== lastDir) reversals++; lastDir = dir; p = target; lastMove = t; }
    T += M.rate(th, T, p, outF, watts) / 60;
    if (m >= 120) { err += Math.abs(T - AIM); errN++; } else if (m >= 60) { early += Math.abs(T - AIM); earlyN++; }
  }
  return { moves, reversals, err: err / errN, early: early / earlyN, end: T };
}

// Old: jump 25%/°F from the half-hour trend, 20 minute settle, 0.5°F deadband.
function oldCtl(s) {
  if (s.t - s.lastMove < 20 * 60000) return null;
  const slope = s.hist.length > 30 ? s.T - s.hist[s.hist.length - 31] : 0, ahead = s.T + slope * 0.5 - AIM;
  if (Math.abs(ahead) < 0.5) return null;
  const pct = Math.max(0, Math.min(100, s.p * 100 - Math.round(ahead * 25 / 5) * 5));
  return pct / 100;
}

// New: fit on everything logged (10 minute buckets), bias from the last hour, go to where the room settles at the aim.
function bucketsOf(log) {
  const by = new Map();
  for (const r of log) { const b = Math.floor(r.t / 600000) * 600000; const a = by.get(b) || { t: b, p: 0, T: 0, out: 0, watts: 0, n: 0 }; a.p += r.p; a.T += r.T; a.out += r.out; a.watts += r.watts; a.n++; by.set(b, a); }
  return [...by.values()].filter((a) => a.n >= 5).map((a) => ({ t: a.t, p: a.p / a.n, T: a.T / a.n, out: a.out / a.n, watts: a.watts / a.n }));
}
let lastFit = null, noLearn = false;
function newCtl(s) {
  if (s.t - s.lastMove < M.CTL.SETTLE_MIN * 60000) return null;
  if (s.t % (10 * 60000) !== 0 && lastFit) { /* refit every 10 min is plenty for the sim */ } else {
    const ss = M.samples(bucketsOf(s.log)); lastFit = { ...(noLearn ? { theta: M.PRIOR } : M.fit(ss, s.t)), ss };
  }
  const d = M.decide(lastFit.theta, lastFit.ss, s.t, AIM, Math.round(s.p * 100), s.outF, s.watts);
  return d.move ? d.pct / 100 : null;
}

for (const [name, ctl, nl] of [["old jump", oldCtl], ["prior + tonight's bias only", newCtl, true], ["learning", newCtl, false]]) {
  seed = 7; lastFit = null; noLearn = !!nl; const log = []; globalThis.__log = log;
  console.log(`\n== ${name}`);
  for (let n = 0; n < 7; n++) {
    const r = night(n, ctl, log, Date.UTC(2026, 10, 15 + n, 4));
    console.log(`night ${n + 1}: moves ${r.moves}, reversals ${r.reversals}, miss in hour 2 ${r.early.toFixed(2)}°F, after ${r.err.toFixed(2)}°F, end ${r.end.toFixed(1)}°F`);
  }
  if (lastFit) console.log("settles up/down at 25F, 200 W: true", [0, 1].map((p) => M.settle(TRUE, p, 25, 200).toFixed(1)).join("/"), "model", [0, 1].map((p) => M.settle(lastFit.theta, p, 25, 200).toFixed(1)).join("/"));
  if (lastFit) console.log("learned", Object.fromEntries(Object.entries(lastFit.theta).map(([k, v]) => [k, +v.toFixed(2)])), "true", TRUE);
}
