"""Corner mount for the Waveshare Thermal-90 USB Camera (B).

Two plates stick to the two walls of a corner on the desk wall (Command strips or VHB), and a cradle holds the camera
aimed the way the room model found best for that corner. SPOT picks the corner:
  "window": top left of the window as you walk in (the pick: sees the PC, desk, bed, you, floor and the heat/AC unit)
  "door":   top left of the door (sees the window glass head-on, but not the PC)

Mount frame, millimetres, origin at the corner where the plates meet, top of the mount at y = 0:
  z runs along the desk wall into the room, x runs along the other wall (window or door wall) toward the bed side, y is up.
The walls are the planes x = 0 and z = 0; everything printed sits at x >= 0, z >= 0.

Camera: an aluminium block with the lens on its big face and the USB-C plug sticking out of one end. Measure the real
one when it arrives and fix CAM_* below, then run:  py -3.12 mount.py   (needs: pip install manifold3d trimesh)
"""
import math
import pathlib

import numpy as np
import trimesh
from manifold3d import Manifold, Mesh

# Camera body (Waveshare lists 32.0 × 18.5 mm; the thickness is a guess until it is measured).
CAM_L, CAM_W, CAM_T = 32.0, 18.5, 10.0
FIT = 0.3            # clearance per side for a snug push fit
WALL = 2.4           # cradle wall
LIP = 1.2            # lip over the lens face's long edges that holds the camera in

# Per spot: aim in the mount frame (degrees from the desk wall toward the bed side, and down), roll (90 = camera turned on
# its side, so its wide 90° axis runs up and down), which end of the cradle is open (+1 / -1 along the camera's long axis,
# None = whichever end points down), and whether it's a two-wall corner mount or a single plate on the desk wall.
# They match thermal_agent.py's pose in room terms:
#   "above_pc":    on the desk wall 85 cm from the window corner, room yaw 100°, tilt -55°, upright (the pick: almost no
#                  ceiling, and it sees the PC, the heat/AC unit, the floor, the desk, the bed and you)
#   "window_side": 45 cm from the window corner, room yaw 115°, tilt -40°, on its side (less wasted side wall, but the
#                  top of the picture is all far wall)
#   "window":      in the window corner, room yaw 105°, tilt -50° (42% of the picture is the window wall, edge-on)
#   "door":        in the door corner, room yaw 40°, tilt -33° (sees the glass head-on, not the PC)
# The camera slides in from the open end with its USB-C plug sticking out of it; that end must not face a wall.
SPOTS = {"above_pc": (80.0, -55.0, 0.0, None, False), "window_side": (65.0, -40.0, 90.0, None, False), "window": (75.0, -50.0, 0.0, -1, True), "door": (40.0, -33.0, 0.0, +1, True)}
SPOT = "above_pc"
YAW, TILT, ROLL, PLUG_END, CORNER = SPOTS[SPOT]
# Where the lens sits (mm): out from the wall(s), and down from the top of the mount. On a single plate it sits mid-plate.

PLATE, PLATE_H, PLATE_T = 72.0, 48.0, 4.0
OUT, DOWN = 46.0, 28.0
ALONG = OUT if CORNER else PLATE / 2


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def frame():
    y, t = math.radians(YAW), math.radians(TILT)
    fwd = unit([math.sin(y) * math.cos(t), math.sin(t), math.cos(y) * math.cos(t)])
    right = unit(np.cross([0, 1, 0], fwd))
    up = np.cross(fwd, right)
    r = math.radians(ROLL)
    right, up = right * math.cos(r) + up * math.sin(r), up * math.cos(r) - right * math.sin(r)
    return right, up, fwd


def placed(m: Manifold, origin):
    """Move a part modelled in camera coordinates (x = long axis, y = short axis, z = optical axis) into the room."""
    r, u, f = frame()
    mat = np.column_stack([r, u, f, origin])  # 3×4
    return m.transform(mat)


def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def build():
    lens = np.array([OUT, -DOWN, ALONG])
    plug_end = PLUG_END if PLUG_END is not None else (-1 if frame()[0][1] > 0 else 1)   # open end pointing down
    L, W, T = CAM_L + 2 * FIT, CAM_W + 2 * FIT, CAM_T + FIT
    # Camera coordinates: lens face at z = 0, body behind it (z < 0).
    outer = box(-L / 2 - WALL, L / 2 + WALL, -W / 2 - WALL, W / 2 + WALL, -T - WALL, 0)
    pocket = box(-L / 2, L / 2, -W / 2, W / 2, -T, 5)
    window = box(-L / 2 + 1.5, L / 2 - 1.5, -W / 2 + LIP, W / 2 - LIP, -1, 5)       # opening in front of the lens face
    lips = box(-L / 2 - WALL, L / 2 + WALL, -W / 2 - WALL, W / 2 + WALL, 0, 1.2) - window
    # The plug end is left open: the camera slides in from there under the lips, and the plug and cable come out of it.
    slide = box(-L / 2, L / 2, -W / 2 - 0.05, W / 2 + 0.05, -T - 0.05, 0).translate([plug_end * L, 0, 0])  # a hair wider than the pocket so no edges just touch
    stop = box(-0.6, 0.6, -W / 2, W / 2, -T, -T + 0.5).translate([plug_end * (L / 2 - 1.5), 0, 0])  # small bump that clicks it in place
    cradle = placed(((outer + lips) - pocket - slide) + stop, lens)
    back = placed(box(-L / 2 - WALL + 0.4, L / 2 + WALL - 0.4, -W / 2 - WALL + 0.4, W / 2 + WALL - 0.4, -T - WALL + 0.3, -T - WALL + 1.5), lens)  # inside the back wall, so the stem never just touches the pocket
    plug = slide

    plate_desk = box(0, PLATE_T, -PLATE_H, 0, 0, PLATE)        # on the desk wall (x = 0)
    if CORNER:
        plate_other = box(0, PLATE, -PLATE_H, 0, 0, PLATE_T)   # on the window or door wall (z = 0)
        knuckle = box(0, 14, -PLATE_H, 0, 0, 14)               # solid corner where the plates meet
    else:
        plate_other = Manifold()                                # single plate: nothing on another wall
        knuckle = box(0, 12, -PLATE_H, 0, ALONG - 14, ALONG + 14)
    stem = Manifold.batch_hull([back, knuckle])
    part = plate_other + plate_desk + knuckle + stem + cradle
    part = part - placed(pocket, lens) - placed(slide, lens) - placed(plug, lens)
    keep = box(0, 400, -400, 400, 0, 400)                      # nothing may poke into the walls
    return part ^ keep


# ---- the sleek single-plate version (used when the spot isn't a corner) ----
SEG = 72                                    # facets per full circle: smooth on any printer
# 3M Command Medium picture-hanging strips: 3/4" x 2-3/4" (19.05 x 69.85 mm). About the last 15 mm is the pull tab, which
# must stay free, so the plate covers only the sticky part and the tabs hang out of the bottom.
STRIP_W, STRIP_L, STRIP_TAB = 19.05, 69.85, 15.0
STRIPS, STRIP_GAP, MARGIN = 2, 5.0, 2.5     # two side by side: the camera sticks out, and two strips resist peeling far better
SLEEK_W = STRIPS * STRIP_W + (STRIPS - 1) * STRIP_GAP + 2 * MARGIN    # 48.1 mm along the wall
SLEEK_H = STRIP_L - STRIP_TAB + 1.0                                   # 55.9 mm tall
SLEEK_T = 4.0
SLEEK_OUT, SLEEK_DOWN = 44.0, 30.0          # lens: out from the wall, and down from the top of the plate
RECESS = 0.4                                # shallow pockets on the back that show where each strip goes


def rbox(x0, x1, y0, y1, z0, z1, r):
    """A box with every edge and corner rounded to radius r."""
    pts = [(x, y, z) for x in (x0 + r, x1 - r) for y in (y0 + r, y1 - r) for z in (z0 + r, z1 - r)]
    return Manifold.batch_hull([Manifold.sphere(r, SEG).translate(p) for p in pts])


def xdisc(x0, x1, y, z, r):
    """A disc whose axis runs out of the wall (x)."""
    return Manifold.cylinder(x1 - x0, r, r, SEG).rotate([0, 90, 0]).translate([x0, y, z])


def build_sleek():
    zc = SLEEK_W / 2
    lens = np.array([SLEEK_OUT, -SLEEK_DOWN, zc])
    plug_end = PLUG_END if PLUG_END is not None else (-1 if frame()[0][1] > 0 else 1)
    L, W, T = CAM_L + 2 * FIT, CAM_W + 2 * FIT, CAM_T + FIT
    R, C = 9.0, 1.4                          # plate corner radius, and the soft bevel round its front edge
    ys, zs = (-SLEEK_H + R, -R), (zc - SLEEK_W / 2 + R, zc + SLEEK_W / 2 - R)
    plate = Manifold.batch_hull([xdisc(0, SLEEK_T - C, y, z, R) for y in ys for z in zs] +
                                [xdisc(SLEEK_T - C, SLEEK_T, y, z, R - C) for y in ys for z in zs])
    # Strip pockets on the back, open at the bottom so the pull tabs come straight out.
    for i in range(STRIPS):
        z0 = zc - SLEEK_W / 2 + MARGIN + i * (STRIP_W + STRIP_GAP) - 0.2
        plate = plate - box(-1, RECESS, -SLEEK_H - 1, -1.2, z0, z0 + STRIP_W + 0.4)
    # Cradle: a rounded shell round the camera, with a rounded window for the lens and one open end.
    shell = placed(rbox(-L / 2 - WALL, L / 2 + WALL, -W / 2 - WALL, W / 2 + WALL, -T - WALL, 1.2, 2.0), lens)
    pocket = box(-L / 2, L / 2, -W / 2, W / 2, -T, 0)
    win = Manifold.batch_hull([Manifold.cylinder(8, 1.6, 1.6, SEG).translate([x, y, -2])
                               for x in (-L / 2 + 3.1, L / 2 - 3.1) for y in (-W / 2 + LIP + 1.6, W / 2 - LIP - 1.6)])
    slide = box(-L / 2, L / 2, -W / 2 - 0.05, W / 2 + 0.05, -T - 0.05, 0).translate([plug_end * L, 0, 0])
    stop = box(-0.6, 0.6, -W / 2, W / 2, -T, -T + 0.5).translate([plug_end * (L / 2 - 1.5), 0, 0])
    # Neck: one smooth taper from a disc on the plate to the back of the cradle.
    root = xdisc(SLEEK_T - 1.0, SLEEK_T, -SLEEK_H / 2, zc, 13.0)
    back = placed(rbox(-L / 2 - WALL + 1, L / 2 + WALL - 1, -W / 2 - WALL + 1, W / 2 + WALL - 1, -T - WALL + 0.3, -T - WALL + 1.8, 0.6), lens)
    neck = Manifold.batch_hull([root, back])
    part = plate + neck + shell
    part = part - placed(pocket + slide + win, lens)
    part = part + placed(stop, lens)
    return part ^ box(0, 400, -400, 400, -400, 400)


def lens_pos():
    return np.array([SLEEK_OUT, -SLEEK_DOWN, SLEEK_W / 2]) if not CORNER else np.array([OUT, -DOWN, ALONG])


def main():
    part = build() if CORNER else build_sleek()
    mesh: Mesh = part.to_mesh()
    tm = trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts))
    out = pathlib.Path(__file__).with_name(f"{SPOT}_mount.stl")
    tm.export(out)
    ext = tm.bounds[1] - tm.bounds[0]
    print(f"wrote {out.name}: {len(tm.faces)} triangles, {ext[0]:.0f} × {ext[1]:.0f} × {ext[2]:.0f} mm, "
          f"watertight {tm.is_watertight}, volume {tm.volume / 1000:.1f} cm³")
    r, u, f = frame()
    print("aim (room x, y, z):", np.round(f, 3), " camera right:", np.round(r, 3))


if __name__ == "__main__":
    main()
