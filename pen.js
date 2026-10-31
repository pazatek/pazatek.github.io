import { getStroke } from './vendor/perfect-freehand.js';

const STEP = 1.5;
const DOWNSTROKE_CONTRAST = 0.2;
const THINNING = 0.35;
const START_TAPER = 0.8;
const END_TAPER = 2;

const FOLD_REACH = 30;
const FOLD_DEPTH = 0.75;
const CAP_STEPS = 4;
const TIP_WIDTH = 0.25;

const dist = (a, b) => Math.hypot(b[0] - a[0], b[1] - a[1]);

// Pencils without a pressure sensor report one constant value; derive it instead from speed,
// like ink that pools when the pen slows, and from direction, like a brush pen pressed into
// downstrokes and lifted on the way up.
function inkPressure(points) {
  const p = points.map((pt, i) => {
    const a = points[Math.max(0, i - 1)];
    const b = points[Math.min(points.length - 1, i + 1)];
    const speed = b[3] > a[3] ? dist(a, b) / (b[3] - a[3]) : 0;
    const flow = Math.min(0.7, Math.max(0.45, 0.75 - 0.25 * speed));
    const down = (b[1] - a[1]) / (dist(a, b) || 1);
    return Math.min(1, flow * (1 + DOWNSTROKE_CONTRAST * down));
  });
  for (let pass = 0; pass < 2; pass++) {
    for (let i = 1; i < p.length; i++) p[i] = p[i - 1] * 0.6 + p[i] * 0.4;
    for (let i = p.length - 2; i >= 0; i--) p[i] = p[i + 1] * 0.6 + p[i] * 0.4;
  }
  return p;
}

// Safari only delivers ~60 samples a second (no getCoalescedEvents), so fast strokes
// arrive as visible straight segments. A centripetal Catmull-Rom spline fills them back in.
function resample(points) {
  if (points.length < 3) return points;
  const out = [points[0]];
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(0, i - 1)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(points.length - 1, i + 2)];
    const steps = Math.max(1, Math.ceil(dist(p1, p2) / STEP));

    const knot = (a, b) => Math.max(Math.sqrt(dist(a, b)), 1e-4);
    const t1 = knot(p0, p1);
    const t2 = t1 + knot(p1, p2);
    const t3 = t2 + knot(p2, p3);

    for (let s = 1; s <= steps; s++) {
      const u = s / steps;
      const t = t1 + (t2 - t1) * u;
      const lerp = (a, b, ta, tb) => a.map((v, k) => k > 1 ? v : ((tb - t) * v + (t - ta) * b[k]) / (tb - ta));
      const a1 = lerp(p0, p1, 0, t1);
      const a2 = lerp(p1, p2, t1, t2);
      const a3 = lerp(p2, p3, t2, t3);
      const b1 = lerp(a1, a2, 0, t2);
      const b2 = lerp(a2, a3, t1, t3);
      const c = lerp(b1, b2, t1, t2);
      out.push([c[0], c[1], p1[2] + (p2[2] - p1[2]) * u, p1[3] + (p2[3] - p1[3]) * u]);
    }
  }
  return out;
}

// Evens out small tremors in the hand without moving where strokes start and end.
function steady(points) {
  return points.map((pt, i) => {
    if (i === 0 || i === points.length - 1) return pt;
    const a = points[i - 1];
    const b = points[i + 1];
    return [(a[0] + 2 * pt[0] + b[0]) / 4, (a[1] + 2 * pt[1] + b[1]) / 4, pt[2], pt[3]];
  });
}

// points are [x, y, pressure, ms]; returns the same shape, smoothed and densified.
export function prepareStroke(points) {
  points = steady(points);
  const flat = points.every(p => Math.abs(p[2] - points[0][2]) < 0.01);
  if (flat && points.length > 1) {
    const p = inkPressure(points);
    points = points.map((pt, i) => [pt[0], pt[1], p[i], pt[3]]);
  }
  return resample(points);
}

function outlineOf(points, size, complete) {
  let length = 0;
  for (let i = 1; i < points.length; i++) length += dist(points[i - 1], points[i]);

  // A quick tap barely registers pressure, but a pen dot should be as heavy as the line around it.
  if (length < size) points = points.map(([x, y, p]) => [x, y, Math.max(p, 0.5)]);

  return getStroke(points, {
    size,
    thinning: THINNING,
    smoothing: 0.5,
    streamline: 0.25,
    simulatePressure: false,
    last: complete,
    // Tapers stay proportional on short strokes so every mark ends the same way; perfect-freehand
    // turns a taper longer than the stroke itself into a sliver.
    start: { taper: length > size * 1.5 ? Math.min(size * START_TAPER, length * 0.2) : 0, cap: true },
    end: { taper: length > size * 1.5 ? Math.min(size * END_TAPER, length * 0.35) : 0, cap: true },
  });
}

function pathThrough(outline) {
  const path = new Path2D();
  if (!outline.length) return path;
  path.moveTo(outline[0][0], outline[0][1]);
  for (let i = 0; i < outline.length; i++) {
    const [x0, y0] = outline[i];
    const [x1, y1] = outline[(i + 1) % outline.length];
    path.quadraticCurveTo(x0, y0, (x0 + x1) / 2, (y0 + y1) / 2);
  }
  path.closePath();
  return path;
}

// pass complete = false while a stroke is still being drawn.
export function strokePath(points, size, complete = true) {
  return pathThrough(outlineOf(points, size, complete));
}

// How thick the ink is at each point, for inkPath. The stroke's ink, measured once.
export function inkWidths(points, size) {
  const outline = outlineOf(points, size, true);
  let widths = points.map(([x, y]) => Math.min(...outline.map(o => Math.hypot(o[0] - x, o[1] - y))));
  // The outline's points are coarse, so distances to them come out lumpy. The two ends stay narrow,
  // or the taper smooths away and the line ends blunt.
  for (let pass = 0; pass < 4; pass++) {
    widths = widths.map((w, i) => {
      if (i === 0 || i === widths.length - 1) return Math.max(w, size * TIP_WIDTH);
      const near = widths.slice(Math.max(0, i - 3), i + 4);
      return near.reduce((sum, v) => sum + v, 0) / near.length;
    });
  }
  return widths;
}

// For a line that's moving. perfect-freehand drops outline points that land too close together or
// too near the ends of a stroke, and which ones change as the line moves, so bits of it pop from
// frame to frame. Here every point keeps its place in the outline and its width, except where the
// line folds back on itself, like the foot of the nose mid-turn: the edge there lands inside the
// ink further along, and an outline that went through it would cross itself and fill as a hole.
// A round dab, wound the same way as the outline, stands in for each edge point left out. Only
// there: where dabs overlap each other the ink shows faint seams, so they can't make up a whole line.
export function inkPath(points, widths) {
  const last = points.length - 1;
  const left = [];
  const right = [];
  const folded = [];
  const onEdge = (x, y, i) => {
    for (let j = Math.max(0, i - FOLD_REACH); j <= Math.min(last, i + FOLD_REACH); j++) {
      if (j !== i && Math.hypot(points[j][0] - x, points[j][1] - y) < widths[j] * FOLD_DEPTH) return false;
    }
    return true;
  };
  const normal = i => {
    const a = points[Math.max(0, i - 3)];
    const b = points[Math.min(last, i + 3)];
    const run = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    return [-(b[1] - a[1]) / run * widths[i], (b[0] - a[0]) / run * widths[i]];
  };
  // Round from the left edge to the right, going out past the end of the line.
  const cap = (i, outward) => {
    const [nx, ny] = normal(i);
    const arc = [];
    for (let step = 1; step < CAP_STEPS; step++) {
      const [cos, sin] = [Math.cos(Math.PI * step / CAP_STEPS), Math.sin(Math.PI * step / CAP_STEPS) * outward];
      const [x, y] = [points[i][0] + nx * cos + ny * sin, points[i][1] + ny * cos - nx * sin];
      if (onEdge(x, y, i)) arc.push([x, y]);
    }
    return arc;
  };
  points.forEach(([x, y], i) => {
    const [nx, ny] = normal(i);
    const [leftEdge, rightEdge] = [onEdge(x + nx, y + ny, i), onEdge(x - nx, y - ny, i)];
    if (leftEdge) left.push([x + nx, y + ny]);
    if (rightEdge) right.push([x - nx, y - ny]);
    if (!leftEdge || !rightEdge) folded.push(i);
  });
  const path = pathThrough([...left, ...cap(last, 1), ...right.reverse(), ...cap(0, -1).reverse()]);
  for (const i of folded) {
    path.moveTo(points[i][0] + widths[i], points[i][1]);
    path.arc(points[i][0], points[i][1], widths[i], 0, Math.PI * 2, true);
  }
  return path;
}
