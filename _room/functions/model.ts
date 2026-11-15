// A learned thermal model of the bedroom, used by the night blind controller in room.ts.
//
// Physics, with p = how far down the blind is (0 up .. 1 down):
//   dT/dt [°F per hour] = c − h·T − (gU·(1−p) + gD·p)·(T − out) + w·watts/100
// The room relaxes toward the warm building (c/h), leaks heat to outside through the window, and the blind scales that leak.
// The five numbers are fitted to logged nights (room_log) by ridge regression, pulled toward a prior so a few hours of data
// can't produce nonsense, with recent nights weighted most. On top of that a bias term, the model's recent miss (last two hours,
// mostly the last half hour), absorbs whatever tonight is doing differently (window opened wider, door, a guest).
//
// The controller then puts the blind where the model says the room will SETTLE at the target, and waits. A first-order room
// never overshoots its settling point, so there is nothing to chase: it may take longer, but it doesn't loop.

export type Theta = { c: number; h: number; gU: number; gD: number; w: number };
export const KEYS = ["c", "h", "gU", "gD", "w"] as const;
// Prior from the 2026-11-13 measurement (quarter-open window, 37°F out: fully up settles near 64°F, fully down near 68°F,
// most of the change within 45 minutes), with the building at 74°F.
export const PRIOR: Theta = { c: 162, h: 2.19, gU: 0.81, gD: 0.42, w: 0.3 };
// How far each number may wander from the prior once data backs it. h is pinned: most nights sit near steady state, where scaling
// every rate up or down together fits equally well, so one rate has to anchor the scale (it only sets how fast, not where it settles).
const TAU: Theta = { c: 60, h: 0.001, gU: 0.5, gD: 0.3, w: 0.5 };
const NOISE = 0.8; // °F/h: a 0.1°C sensor step over a 20 minute slope
const HALF_LIFE_DAYS = 7;
export const BIAS_MAX = 15;

export type Bucket = { t: number; p: number; T: number; out: number; watts: number }; // 10 minute means, t in ms
export type Sample = { x: number[]; y: number; t: number; p: number; step?: boolean };
const STEP_WEIGHT = 4;

export const feats = (T: number, p: number, out: number, watts: number) => [1, -T, -(1 - p) * (T - out), -p * (T - out), watts / 100];
const vec = (th: Theta) => KEYS.map((k) => th[k]);
const dot = (a: number[], b: number[]) => a.reduce((s, v, i) => s + v * b[i], 0);
export const rate = (th: Theta, T: number, p: number, out: number, watts: number) => dot(feats(T, p, out, watts), vec(th));

// Slopes from consecutive 10 minute buckets (central difference over 20 minutes).
export function samples(bs: Bucket[]): Sample[] {
  const out: Sample[] = [];
  for (let i = 1; i < bs.length - 1; i++) {
    const a = bs[i - 1], b = bs[i], z = bs[i + 1];
    if (b.t - a.t !== 600000 || z.t - b.t !== 600000) continue;
    if (Math.abs(a.p - b.p) > 0.02 || Math.abs(z.p - b.p) > 0.02) continue; // the blind moved inside this window: the slope mixes two settings
    out.push({ x: feats(b.T, b.p, b.out, b.watts), y: (z.T - a.T) * 3, t: b.t, p: b.p });
  }
  // Each blind move is a small experiment: the change in how fast the room warms or cools from just before to just after it
  // is caused by the move itself. Data where the controller holds the room on target says little about how strong the blind
  // is (the room looks the same at every height); these step rows are what pin that down.
  const steps: Sample[] = [];
  for (let i = 0; i < out.length - 1; i++) {
    const s1 = out[i], s2 = out[i + 1];
    if (s2.t - s1.t > 40 * 60000 || Math.abs(s2.p - s1.p) < 0.05) continue;
    steps.push({ x: s2.x.map((v, j) => v - s1.x[j]), y: s2.y - s1.y, t: s2.t, p: s2.p, step: true });
  }
  return out.concat(steps);
}

function solve(A: number[][], b: number[]) {
  const n = b.length, M = A.map((r, i) => [...r, b[i]]);
  for (let i = 0; i < n; i++) {
    let piv = i;
    for (let r = i + 1; r < n; r++) if (Math.abs(M[r][i]) > Math.abs(M[piv][i])) piv = r;
    [M[i], M[piv]] = [M[piv], M[i]];
    for (let r = 0; r < n; r++) {
      if (r === i) continue;
      const f = M[r][i] / M[i][i];
      for (let c = i; c <= n; c++) M[r][c] -= f * M[i][c];
    }
  }
  return M.map((r, i) => r[n] / r[i]);
}

export function fit(ss: Sample[], now: number) {
  const k = KEYS.length, A = Array.from({ length: k }, () => Array(k).fill(0)), b = Array(k).fill(0);
  KEYS.forEach((key, j) => { A[j][j] += 1 / TAU[key] ** 2; b[j] += PRIOR[key] / TAU[key] ** 2; });
  for (const s of ss) {
    const wt = Math.pow(0.5, (now - s.t) / (HALF_LIFE_DAYS * 864e5)) / NOISE ** 2 * (s.step ? STEP_WEIGHT : 1);
    for (let i = 0; i < k; i++) { b[i] += wt * s.x[i] * s.y; for (let j = 0; j < k; j++) A[i][j] += wt * s.x[i] * s.x[j]; }
  }
  const v = solve(A, b);
  let theta = Object.fromEntries(KEYS.map((key, i) => [key, v[i]])) as Theta;
  // Physically the room must cool faster with the blind up than down, and all rates are positive; otherwise keep the prior.
  if (!v.every(Number.isFinite) || theta.h <= 0 || theta.gD <= 0 || theta.gU <= theta.gD + 0.05) theta = { ...PRIOR };
  const lv = ss.filter((x) => !x.step), rmse = lv.length ? Math.sqrt(lv.reduce((s, x) => s + (x.y - dot(x.x, vec(theta))) ** 2, 0) / lv.length) : null;
  return { theta, n: lv.length, steps: ss.length - lv.length, rmse, usedPrior: theta === PRIOR || KEYS.every((k) => theta[k] === PRIOR[k]) };
}

// The model's recent miss in °F/h (positive: the room is warmer than the model expects), weighted toward the last half hour.
export function biasOf(th: Theta, ss: Sample[], now: number, windowMin = 120) {
  let s = 0, wsum = 0;
  for (const x of ss) {
    const age = (now - x.t) / 60000;
    if (x.step || age < 0 || age > windowMin) continue;
    const w = Math.pow(0.5, age / 30);
    s += w * (x.y - dot(x.x, vec(th))); wsum += w;
  }
  return wsum ? Math.max(-BIAS_MAX, Math.min(BIAS_MAX, s / wsum)) : 0;
}

// Where the room settles with the blind at p.
export function settle(th: Theta, p: number, out: number, watts: number, bias = 0) {
  const g = th.gU * (1 - p) + th.gD * p;
  return (th.c + bias + th.w * watts / 100 + g * out) / (th.h + g);
}

// The blind position (0 up .. 1 down) at which the room settles at aim; null when it's too mild out for the window to matter.
export function ideal(th: Theta, aim: number, out: number, watts: number, bias = 0) {
  if (aim - out < 3) return null;
  const g = (th.c + bias + th.w * watts / 100 - th.h * aim) / (aim - out);
  return Math.max(0, Math.min(1, (g - th.gU) / (th.gD - th.gU)));
}

// One controller decision. Leave the blind alone while the room is already heading to a settling point within DEAD_F of the aim
// (it may still be far off right now; that's fine, it's on its way). Otherwise move straight to the ideal height.
export const CTL = { SETTLE_MIN: 20, DEAD_F: 0.5, MIN_STEP: 10 };
export function decide(th: Theta, ss: Sample[], now: number, aim: number, curPct: number, out: number, watts: number) {
  const bias = biasOf(th, ss, now), cur = curPct / 100;
  const eqNow = settle(th, cur, out, watts, bias), p = ideal(th, aim, out, watts, bias);
  const pct = p == null ? null : Math.round(p * 20) * 5;
  const move = pct != null && Math.abs(eqNow - aim) >= CTL.DEAD_F && Math.abs(pct - curPct) >= CTL.MIN_STEP;
  return { bias, eqNow, pct, move };
}
