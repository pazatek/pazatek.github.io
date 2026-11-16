"""Room Coach thermal agent: reads the Waveshare Thermal-90 USB Camera (B) on Piotr's PC and sends a summary to Supabase every minute.

Each minute it averages every frame it got (about 2 a second), corrects each pixel for what the surface is made of,
calibrates against the desk thermometer through a reference card, and posts:
  window, heat/AC unit, walls, floor, bed and head temperatures, whether you're in bed, and how many warm-body pixels it sees.
Every 15 minutes it also sends the whole 80×62 frame.

Usage (from the install folder, see README.md):
  python thermal_agent.py                 run forever (what the scheduled task does)
  python thermal_agent.py --once --dry-run --snapshot snap.png    one minute, print it, save a picture, send nothing
  python thermal_agent.py --fake ...      same, with a made-up camera (for testing without hardware)
  python thermal_agent.py --find-card     hold a warm hand behind the reference card for 20 s; saves where it is
Settings live next to it: thermal.env (ROOM_URL, ROOM_KEY; never commit it), config.json (pose, card), calib.json (written by the agent).
"""
from __future__ import annotations

import argparse
import base64
import calendar
import json
import math
import os
import pathlib
import struct
import sys
import time
import urllib.request
import zlib
from collections import deque

import numpy as np

import room_scene as rs

HERE = pathlib.Path(__file__).resolve().parent
K = 273.15
DEFAULT_CONFIG = {
    # On the desk wall 45 cm from the window corner, near the ceiling, turned on its side (roll 90: its wide 90° axis runs up
    # and down), aimed toward the bed side and 40° down (the mount holds this). Only 8% of the picture is wasted wall; it sees
    # the PC, desk, floor, bed, you and the heat/AC unit. The glass it sees at a steep angle, so window_c is skipped.
    "pose": {"pos": [0.046, 2.2, 3.235], "yaw": 115.0, "tilt": -40.0, "roll": 90.0, "flip_h": False, "flip_v": False},
    "skip": ["window"],
    # Reference card: black electrical tape on a piece of card, hung in free air next to the desk thermometer.
    "card": {"pixel": None, "thermometer": "desk"},
    "frame_every_min": 15,
}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def load_json(path: pathlib.Path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def load_env(path: pathlib.Path) -> dict:
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


# ---------- camera sources ----------

class Camera:
    """The real camera through Meridian's pysenxor-lite (pip install pysenxor-lite)."""

    def __init__(self):
        from senxor import connect, list_senxor
        devices = list_senxor("serial")
        if not devices:
            raise RuntimeError("no SenXor camera found on any serial port")
        self.dev = connect(devices[0])
        log("connected to", self.dev.name, "shape", self.dev.get_shape())
        self.emissivity = self._emissivity_to_one()
        self.dev.start_stream()

    def _emissivity_to_one(self) -> float:
        # The docs disagree on units (0.98 vs 98), so set it, read it back and report what stuck.
        for setter in (lambda: self.dev.fields.EMISSIVITY.set(100), lambda: self.dev.set_emissivity(100), lambda: self.dev.set_emissivity(1.0)):
            try:
                setter()
                e = float(self.dev.get_emissivity())
                e = e / 100 if e > 1.5 else e
                if abs(e - 1.0) < 0.02:
                    log("camera emissivity set to 1.0")
                    return 1.0
            except Exception:  # noqa: BLE001 - any failure just moves on to the next way of setting it
                pass
        try:
            e = float(self.dev.get_emissivity()); e = e / 100 if e > 1.5 else e
        except Exception:  # noqa: BLE001
            e = 0.95
        log(f"could not set the camera's emissivity to 1.0; it is {e:.2f}, corrections assume that")
        return e

    def read(self):
        header, frame = self.dev.read(block=False)
        return None if frame is None else np.asarray(frame, np.float32)

    def close(self):
        try:
            self.dev.close()
        except Exception:  # noqa: BLE001
            pass


class FakeCamera:
    """The room model with made-up temperatures, a 0.4 °C error to calibrate out, and a reference card at the desk."""

    def __init__(self, pose, card_pixel):
        self.pose, self.card = pose, card_pixel
        self.rng = np.random.default_rng(7)
        self.emissivity = 1.0
        self.t0 = time.time()

    def air_c(self):
        return 22.0 + 1.5 * math.sin((time.time() - self.t0) / 900)

    def read(self):
        f = rs.fake_frame(self.pose, self.rng)
        if self.card:
            c, r = self.card
            e, a, refl = rs.EMISSIVITY["card"], self.air_c() + K, 21.0 + K
            f[r, c] = (e * a ** 4 + (1 - e) * refl ** 4) ** 0.25 - K + 0.4 + self.rng.normal(0, 0.15)
        time.sleep(0.5)
        return f

    def close(self):
        pass


# ---------- per-surface correction and calibration ----------

def surface_temps(apparent_c: np.ndarray, labels: np.ndarray, cam_emissivity: float, reflected_c: float) -> np.ndarray:
    """Turn the camera's reading into each surface's own temperature using that surface's emissivity.
    The camera sees ε·σT⁴ + (1-ε)·σT_reflected⁴; walls reflect the room, so T_reflected is roughly the median wall."""
    eps = np.vectorize(lambda n: rs.EMISSIVITY.get(n, 0.94))(labels)
    rad = cam_emissivity * (apparent_c + K) ** 4 + (1 - cam_emissivity) * (reflected_c + K) ** 4   # undo the camera's own setting
    t4 = (rad - (1 - eps) * (reflected_c + K) ** 4) / eps
    return np.power(np.maximum(t4, 1.0), 0.25) - K


class Calibration:
    """T_true = a·T + b, fitted from the reference card against a thermometer over the last week."""

    def __init__(self, path: pathlib.Path):
        self.path = path
        d = load_json(path, {})
        self.a, self.b = d.get("a", 1.0), d.get("b", 0.0)
        self.samples = d.get("samples", [])
        self.recent = deque(maxlen=12)

    def apply(self, t):
        return self.a * t + self.b

    def add(self, now, card_c, card_sd, ref_c, ref_age_s):
        self.recent.append(card_c)
        steady = card_sd < 0.3 and len(self.recent) >= 10 and abs(self.recent[-1] - self.recent[0]) < 0.3 and ref_age_s < 600
        if steady:
            self.samples.append([round(now), round(card_c, 3), round(ref_c, 3)])
        self.samples = [s for s in self.samples if s[0] > now - 7 * 86400]
        n = len(self.samples)
        if n >= 10:
            x = np.array([s[1] for s in self.samples]); y = np.array([s[2] for s in self.samples])
            w = np.power(0.5, (now - np.array([s[0] for s in self.samples])) / 86400.0 / 2)   # two-day half-life
            if y.max() - y.min() >= 2.0:
                # Weighted least squares, nudged toward a = 1, b = 0 so a few odd minutes can't bend it.
                A = np.array([[np.sum(w * x * x) + 50, np.sum(w * x)], [np.sum(w * x), np.sum(w) + 0.5]])
                rhs = np.array([np.sum(w * x * y) + 50, np.sum(w * y)])
                a, b = np.linalg.solve(A, rhs)
            else:
                a, b = 1.0, float(np.sum(w * (y - x)) / np.sum(w))
            self.a, self.b = float(np.clip(a, 0.85, 1.15)), float(np.clip(b, -5, 5))
        self.path.write_text(json.dumps({"a": self.a, "b": self.b, "samples": self.samples}))
        return steady


# ---------- one minute's summary ----------

def summarize(t: np.ndarray, labels: np.ndarray, purity: np.ndarray, skip=()) -> dict:
    def pick(*names, pure=0.75):
        m = np.isin(labels, names) & (purity >= pure)
        return t[m]

    def med(v):
        return round(float(np.median(v)), 2) if v.size else None

    walls = pick("wall", "wall_bed", "wall_window", "closet", "ceiling")
    wall_c = med(walls)
    unit = pick("unit", pure=0.6)
    unit_c = med(unit)
    unit_state = None
    if unit_c is not None and wall_c is not None:
        dt = unit_c - wall_c
        unit_state = "heating" if dt > 6 else "cooling" if dt < -6 else "off"
    bed = pick("bed", "you", pure=0.5)
    head = float(np.max(bed)) if bed.size else None
    warm = (t >= 30.0) & ~np.isin(labels, ["pc", "unit", "lamp"])
    floor = pick("floor")
    return {
        "window_c": None if "window" in skip else med(pick("window", pure=0.6)),
        "pc_c": med(pick("pc", pure=0.6)),     # the PC case (its power draw is logged separately in pc_power)
        "unit_c": unit_c, "unit_state": unit_state,
        "unit_leak": bool(unit_state == "off" and unit_c is not None and med(pick("wall_window")) is not None and unit_c < med(pick("wall_window")) - 1.5),
        "walls_c": wall_c,
        "floor_c": med(floor), "floor_min_c": round(float(np.percentile(floor, 5)), 2) if floor.size else None,
        "bed_c": med(pick("bed")), "head_c": round(head, 2) if head is not None else None,
        "in_bed": bool(head is not None and head >= 30.0),
        "people_px": int(warm.sum()),
        "max_c": round(float(t.max()), 2), "min_c": round(float(t.min()), 2),
    }


# ---------- pictures ----------

def ironbow(x):
    stops = [(0, (0, 0, 20)), (.18, (40, 0, 110)), (.38, (150, 0, 140)), (.58, (225, 60, 40)), (.78, (250, 160, 0)), (1, (255, 250, 210))]
    x = min(1.0, max(0.0, x))
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if x <= b:
            f = (x - a) / (b - a)
            return tuple(int(ca[k] + (cb[k] - ca[k]) * f) for k in range(3))
    return stops[-1][1]


def write_png(path, t, labels, lo=10.0, hi=33.0, scale=8, card=None):
    h, w = t.shape
    rows = []
    for j in range(h * scale):
        jj = j // scale
        row = bytearray([0])
        for i in range(w * scale):
            ii = i // scale
            edge = (i % scale == 0 and ii > 0 and labels[jj, ii] != labels[jj, ii - 1]) or (j % scale == 0 and jj > 0 and labels[jj, ii] != labels[jj - 1, ii])
            on_card = card is not None and (ii, jj) == tuple(card)
            row += bytes((255, 255, 255) if edge or (on_card and (i % scale in (0, scale - 1) or j % scale in (0, scale - 1))) else ironbow((t[jj, ii] - lo) / (hi - lo)))
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    pathlib.Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w * scale, h * scale, 8, 2, 0, 0, 0)) + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


# ---------- talking to Supabase (through the room edge function) ----------

def room_request(env, body=None):
    req = urllib.request.Request(env["ROOM_URL"], method="POST" if body is not None else "GET",
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"x-room-key": env["ROOM_KEY"], "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read() or b"{}")


def thermometer(env, which):
    snap = room_request(env)
    d = snap.get(which) or {}
    if d.get("temp_c") is None:
        return None, 1e9
    ts = d.get("ts")
    age = time.time() - calendar.timegm(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")) if ts else 1e9
    return float(d["temp_c"]), age


# ---------- main loop ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fake", action="store_true", help="use a made-up camera")
    ap.add_argument("--once", action="store_true", help="do one minute and stop")
    ap.add_argument("--dry-run", action="store_true", help="print instead of sending")
    ap.add_argument("--snapshot", help="save a PNG of the minute with the surfaces outlined")
    ap.add_argument("--find-card", action="store_true", help="find the reference card by warming it with a hand")
    ap.add_argument("--seconds", type=float, default=60.0, help="length of one summary (default 60)")
    args = ap.parse_args()
    if sys.executable.lower().endswith("pythonw.exe") or sys.stdout is None:   # the scheduled task has no console
        logf = HERE / "agent.log"
        if logf.exists() and logf.stat().st_size > 5_000_000:
            logf.replace(HERE / "agent.old.log")
        sys.stdout = sys.stderr = open(logf, "a", buffering=1, encoding="utf-8")

    cfg = {**DEFAULT_CONFIG, **load_json(HERE / "config.json", {})}
    pose = cfg["pose"]
    env = load_env(HERE / "thermal.env") or load_env(pathlib.Path.home() / "room-thermal" / "thermal.env")
    if not args.dry_run and not args.fake and not {"ROOM_URL", "ROOM_KEY"} <= env.keys():
        sys.exit("thermal.env needs ROOM_URL and ROOM_KEY")
    labels, purity = rs.label_map(pose)
    card = cfg["card"].get("pixel") or ([22, 40] if args.fake else None)
    cam = FakeCamera(pose, card) if args.fake else Camera()
    cal = Calibration(HERE / ("calib.fake.json" if args.fake else "calib.json"))
    minute = 0
    try:
        if args.find_card:
            return find_card(cam, cfg)
        while True:
            frames, end = [], time.time() + args.seconds
            while time.time() < end:
                f = cam.read()
                if f is None:
                    time.sleep(0.05); continue
                if f.shape != (rs.CAM_H, rs.CAM_W):
                    f = f.reshape(rs.CAM_H, rs.CAM_W)
                frames.append(f)
                time.sleep(0.4)
            if not frames:
                log("no frames this minute"); continue
            stack = np.stack(frames)
            apparent = stack.mean(axis=0)
            walls = apparent[np.isin(labels, ["wall", "wall_bed", "wall_window", "closet"]) & (purity >= 0.75)]
            reflected = float(np.median(walls)) if walls.size else 21.0
            surf = surface_temps(apparent, labels, cam.emissivity, reflected)
            now = time.time()
            calib = {"a": round(cal.a, 4), "b": round(cal.b, 3), "n": len(cal.samples)}
            if card:
                c, r = card
                card_lab = np.array([["card"]], dtype=object)
                card_c = float(surface_temps(apparent[r:r + 1, c:c + 1], card_lab, cam.emissivity, reflected)[0, 0])
                card_sd = float(stack[:, r, c].std())
                try:
                    ref_c, age = (cam.air_c(), 0) if args.fake else thermometer(env, cfg["card"].get("thermometer", "desk"))
                    if ref_c is not None:
                        calib["steady"] = cal.add(now, card_c, card_sd, ref_c, age)
                        calib.update(card_c=round(card_c, 2), ref_c=round(ref_c, 2))
                except Exception as e:  # noqa: BLE001 - calibration can wait a minute
                    log("thermometer read failed:", e)
            t = cal.apply(surf)
            stats = {**summarize(t, labels, purity, cfg.get("skip", [])), "frames": len(frames), "cal": calib, **({"fake": True} if args.fake else {})}
            body = {"action": "thermal", "stats": stats}
            if minute % cfg.get("frame_every_min", 15) == 0:
                q = np.clip(np.round(t * 10), -32768, 32767).astype("<i2")   # deci-°C
                body["frame"] = {"w": rs.CAM_W, "h": rs.CAM_H, "dc_i16_b64": base64.b64encode(q.tobytes()).decode()}
            if args.snapshot:
                write_png(args.snapshot, t, labels, card=card)
            if args.dry_run:
                log(json.dumps(stats))
            else:
                try:
                    room_request(env, body)
                except Exception as e:  # noqa: BLE001 - try again next minute
                    log("send failed:", e)
            minute += 1
            if args.once:
                return 0
    finally:
        cam.close()


def find_card(cam, cfg):
    log("watching for 30 s: hold a warm hand right behind the card now")
    base = None; best = None
    end = time.time() + 30
    while time.time() < end:
        f = cam.read()
        if f is None:
            time.sleep(0.05); continue
        base = f if base is None else base
        d = f - base
        j, i = np.unravel_index(np.argmax(d), d.shape)
        if best is None or d[j, i] > best[0]:
            best = (float(d[j, i]), int(i), int(j))
    if not best or best[0] < 1.5:
        sys.exit("didn't see anything warm up; try again closer to the card")
    cfg["card"]["pixel"] = [best[1], best[2]]
    (HERE / "config.json").write_text(json.dumps(cfg, indent=2))
    log(f"card is at pixel column {best[1]}, row {best[2]} (warmed {best[0]:.1f} °C); saved to config.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
