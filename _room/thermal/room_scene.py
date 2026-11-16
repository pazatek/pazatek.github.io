"""The bedroom as boxes, for working out which camera pixel looks at what.

Same layout as the room view (_room/core.js) and the thermal comparison page: metres, x along the door wall toward the bed,
y up, z along the desk wall toward the window. Every box has a label; label_map() ray-traces each camera pixel to the first
box it hits. fake_frame() paints the same scene with made-up temperatures so the agent can be tested without a camera.
"""
from __future__ import annotations

import math

import numpy as np

W, D, DM, NX, H = 3.33, 3.685, 2.865, 1.65, 2.4          # room width, depth, closet line, closet edge, ceiling
WX0, WX1, WY0, WY1 = 0.14, 1.46, 0.92, 2.0               # window glass
CAM_W, CAM_H, HFOV, VFOV = 80, 62, 90.0, 67.0            # Waveshare Thermal-90 USB Camera (B)

# Emissivity per label, used to turn the camera's blackbody reading into a surface temperature.
EMISSIVITY = {
    "window": 0.84,   # glass straight on is about 0.92; the camera sees it at 15-30°, and the blind may be down
    "unit": 0.93, "wall": 0.94, "wall_window": 0.94, "wall_bed": 0.94, "closet": 0.90, "ceiling": 0.94,
    "floor": 0.93, "bed": 0.95, "you": 0.98, "desk": 0.92, "pc": 0.90, "chair": 0.93, "drawer": 0.92, "lamp": 0.85,
    "card": 0.95,
}

BOXES: list[tuple[float, float, float, float, float, float, str]] = []


def box(x0, x1, y0, y1, z0, z1, label):
    BOXES.append((x0, x1, y0, y1, z0, z1, label))


# Shell
box(0, W, -0.1, 0, 0, D, "floor")
box(-0.1, W + 0.1, H, H + 0.1, -0.1, D + 0.1, "ceiling")
box(-0.1, 0, 0, H, -0.1, D + 0.1, "wall")                 # desk wall
box(-0.1, W + 0.1, 0, H, -0.1, 0, "wall")                 # door wall
box(0, NX, 0, H, D, D + 0.1, "wall_window")
box(W, W + 0.1, 0, H, 0, DM, "wall_bed")
box(NX, W, 0, H, DM, D + 0.1, "closet")                   # mirrored closet doors face the room at z = DM
# Window wall: glass, sill and the heat/AC unit under it
box(WX0, WX1, WY0, WY1, D - 0.004, D, "window")
box(WX0 - 0.06, WX1 + 0.06, WY0 - 0.05, WY0, D - 0.07, D, "wall_window")
box(0.35, 1.35, 0.28, 0.72, D - 0.24, D, "unit")
# Bed along the bed wall, head at the door end
box(1.80, 3.30, 0.12, 1.1, 0, 0.065, "bed")
box(1.80, 3.30, 0.12, 0.75, 0.065, 2.035, "bed")
box(1.90, 3.20, 0.75, 0.86, 0.12, 0.52, "bed")
# Drawer (the camera hangs in the corner on the other side of the door)
box(0.80, 1.77, 0, 0.95, 0, 0.435, "drawer")
# Desk, PC, chair, arm lamp
for lx, lz in [(0.02, 2.5), (0.48, 2.5), (0.02, 1.62), (0.48, 1.62)]:
    box(lx, lx + 0.05, 0, 0.68, lz, lz + 0.05, "desk")
box(0, 0.55, 0.68, 0.76, 1.605, 2.565, "desk")
box(0.10, 0.135, 0.9, 1.28, 1.74, 2.36, "desk")
box(0.05, 0.47, 0, 0.38, 2.585, 2.855, "pc")
box(0.68, 1.18, 0.44, 0.52, 1.84, 2.32, "chair")
box(1.12, 1.20, 0.52, 1.12, 1.86, 2.30, "chair")
box(0.15, 0.33, 0, 0.66, 2.97, 3.15, "lamp")
HEAD = ((2.55, 0.93, 0.36), 0.11)                         # where your head is when you sleep


def camera_rays(pose: dict, w=CAM_W, h=CAM_H, hfov=HFOV, vfov=VFOV):
    """Unit ray per pixel (h, w, 3). pose: pos [x,y,z] m, yaw / tilt / roll in degrees, flip_h / flip_v."""
    y, t, r = (math.radians(pose.get(k, 0.0)) for k in ("yaw", "tilt", "roll"))
    fwd = np.array([math.sin(y) * math.cos(t), math.sin(t), math.cos(y) * math.cos(t)])
    right = np.cross([0.0, 1.0, 0.0], fwd); right /= np.linalg.norm(right)
    up = np.cross(fwd, right)
    right, up = right * math.cos(r) + up * math.sin(r), up * math.cos(r) - right * math.sin(r)
    u = ((np.arange(w) + 0.5) / w) * 2 - 1
    v = 1 - ((np.arange(h) + 0.5) / h) * 2
    if pose.get("flip_h"): u = -u
    if pose.get("flip_v"): v = -v
    uu, vv = np.meshgrid(u * math.tan(math.radians(hfov) / 2), v * math.tan(math.radians(vfov) / 2))
    d = fwd + uu[..., None] * right + vv[..., None] * up
    return d / np.linalg.norm(d, axis=-1, keepdims=True)


def trace(origin, dirs):
    """First hit per ray: (t, label index, hit points). dirs is (..., 3)."""
    o = np.asarray(origin, float)
    shape = dirs.shape[:-1]
    d = dirs.reshape(-1, 3)
    best = np.full(len(d), np.inf)
    lab = np.full(len(d), -1)
    with np.errstate(divide="ignore", invalid="ignore"):
        inv = 1.0 / d
        for i, (x0, x1, y0, y1, z0, z1, _) in enumerate(BOXES):
            lo = (np.array([x0, y0, z0]) - o) * inv
            hi = (np.array([x1, y1, z1]) - o) * inv
            tn = np.nanmax(np.minimum(lo, hi), axis=1)
            tf = np.nanmin(np.maximum(lo, hi), axis=1)
            ok = (tn <= tf) & (tn > 1e-6) & (tn < best)
            best[ok] = tn[ok]; lab[ok] = i
        c, rad = HEAD
        oc = o - np.array(c)
        b = d @ oc
        disc = b * b - (oc @ oc - rad * rad)
        th = -b - np.sqrt(np.where(disc >= 0, disc, np.nan))
        ok = (disc >= 0) & (th > 1e-6) & (th < best)
        best[ok] = th[ok]; lab[ok] = len(BOXES)
    pts = o + d * best[:, None]
    return best.reshape(shape), lab.reshape(shape), pts.reshape(shape + (3,))


LABELS = [b[6] for b in BOXES] + ["you"]


def label_map(pose: dict, supersample=3):
    """Per pixel: the label it mostly sees and how much of the pixel that label fills (0..1)."""
    s = supersample
    rays = camera_rays(pose, CAM_W * s, CAM_H * s)
    _, lab, _ = trace(pose["pos"], rays)
    names = np.array(LABELS)[lab]
    names = names.reshape(CAM_H, s, CAM_W, s).transpose(0, 2, 1, 3).reshape(CAM_H, CAM_W, s * s)
    out = np.empty((CAM_H, CAM_W), dtype=object); purity = np.zeros((CAM_H, CAM_W))
    for j in range(CAM_H):
        for i in range(CAM_W):
            vals, counts = np.unique(names[j, i], return_counts=True)
            k = counts.argmax(); out[j, i] = vals[k]; purity[j, i] = counts[k] / (s * s)
    return out, purity


def project(pose: dict, point):
    """Pixel (col, row) a room point lands on, or None if it's behind the camera or out of frame."""
    y, t = math.radians(pose.get("yaw", 0)), math.radians(pose.get("tilt", 0))
    fwd = np.array([math.sin(y) * math.cos(t), math.sin(t), math.cos(y) * math.cos(t)])
    right = np.cross([0.0, 1.0, 0.0], fwd); right /= np.linalg.norm(right)
    up = np.cross(fwd, right)
    r = math.radians(pose.get("roll", 0))
    right, up = right * math.cos(r) + up * math.sin(r), up * math.cos(r) - right * math.sin(r)
    v = np.asarray(point, float) - np.asarray(pose["pos"], float)
    z = v @ fwd
    if z <= 0: return None
    u = (v @ right) / z / math.tan(math.radians(HFOV) / 2)
    w = (v @ up) / z / math.tan(math.radians(VFOV) / 2)
    if pose.get("flip_h"): u = -u
    if pose.get("flip_v"): w = -w
    if abs(u) > 1 or abs(w) > 1: return None
    return (u + 1) / 2 * CAM_W - 0.5, (1 - w) / 2 * CAM_H - 0.5


def fake_frame(pose: dict, rng: np.random.Generator, out_f=30.0, in_bed=True, unit_on=False):
    """A made-up frame in °C (what the camera would report with its emissivity at 100%)."""
    rays = camera_rays(pose)
    _, lab, pts = trace(pose["pos"], rays)
    names = np.array(LABELS)[lab]
    x, y, z = pts[..., 0], pts[..., 1], pts[..., 2]
    f = np.full(names.shape, 69.0) + 1.5 * y / H
    win = np.exp(-(D - z) / 0.9) * np.exp(-((x - 0.8) / 1.1) ** 2)
    f = np.where(names == "floor", 66.3 - 5 * win, f)
    f = np.where(names == "window", 50.5 + (out_f - 37) * 0.25 + 4 * (y - WY0) / (WY1 - WY0), f)
    f = np.where(names == "wall_window", 66.4 + 2 * y / H, f)
    f = np.where(names == "unit", 92.0 if unit_on else 63.0, f)          # off, a through-wall unit leaks cold
    f = np.where(names == "bed", 72.5 + (5 if in_bed else 0) * np.exp(-((x - 2.55) / 0.45) ** 2 - ((z - 1.2) / 0.8) ** 2), f)
    f = np.where(names == "you", 91.0 if in_bed else 72.0, f)
    f = np.where(names == "pc", 84.0, f)
    f = np.where(names == "ceiling", 71.5, f)
    c = (f - 32) / 1.8
    eps = np.vectorize(lambda n: EMISSIVITY.get(n, 0.94))(names)
    refl = (70 - 32) / 1.8
    k = 273.15
    apparent = (eps * (c + k) ** 4 + (1 - eps) * (refl + k) ** 4) ** 0.25 - k   # what a camera set to ε = 1 reads
    return (apparent + 0.4 + rng.normal(0, 0.15, apparent.shape)).astype(np.float32)  # plus a 0.4 °C offset to calibrate out
