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


# ---- the angular single-plate version (used when the spot isn't a corner) ----
# All flat faces, no curves. best_up() tries every flat face of the part as the print-bed face and keeps the one with the
# least overhang, so it prints without supports; report() says what's left to bridge.
#
# One 3M Command Adjustables Mini refill strip, the near-square one (1.03" x 1.32", 26.2 x 33.5 mm, rated 0.5 lb / 227 g).
# Its pull tab (about 8 mm; check it on the real strip) must stay free, so the plate covers only the sticky part and the
# tab hangs out below it. Camera + mount + the cable's share is about 45 g, roughly a 5x margin. The camera is pulled in
# as close to the wall as its view allows, so the lever that tries to peel the top of the strip off is as short as it can be.
SM_W, SM_L, SM_TAB = 26.2, 33.5, 8.0
STRIP_THICK = 1.0                          # a single foam strip; the plate sits this far off the wall
PT = 2.4                                   # plate thickness: 12 layers at 0.2 mm, stiff enough for a strip this size
RAIL, BED = 1.6, 1.6                       # cradle walls and back (4 perimeters at 0.4 mm)
PRINT_UP = None                            # filled in by build_angular(): the direction that's "up" on the print bed
# Where things are on the camera (from Waveshare's photos; measure on arrival). Camera coordinates: x along the long side,
# y along the short side, z out of the lens face.
LENS_X = -8.0                              # the lens sits toward one end
PLUG_X, PLUG_SIDE, PLUG_Z = 8.0, -1, -6.0  # the USB-C plug sticks out of a long side, toward the other end, near the back
PLUG_W = 8.4                               # USB-C plug width
# A 90° USB-C adapter (male-to-female) on the plug turns the cable to run along the wall; this is the room left for it.
ADAPTER_DEEP, ADAPTER_W, ADAPTER_T, ADAPTER_RUN = 15.0, 14.0, 9.0, 40.0
CATCH = 0.7                                # how far the snap catches overlap the camera's front edges


def holder_parts():
    """The cradle in camera coordinates (lens face at z = 0, body behind it). The camera pushes in from the front and
    clicks under two angled catches; its plug passes through a slot in the bottom rail into the adapter bay."""
    L, W, T = CAM_L + 2 * FIT, CAM_W + 2 * FIT, CAM_T + FIT
    front = 1.6
    outer = box(-L / 2 - RAIL, L / 2 + RAIL, -W / 2 - RAIL, W / 2 + RAIL, -T - BED, front)
    pocket = box(-L / 2, L / 2, -W / 2, W / 2, -T, 30)
    sy = PLUG_SIDE
    ylo, yhi = (-W / 2 - ADAPTER_DEEP, -W / 2 + 0.01) if sy < 0 else (W / 2 - 0.01, W / 2 + ADAPTER_DEEP)
    slot = box(PLUG_X - ADAPTER_W / 2, PLUG_X + ADAPTER_W / 2, ylo, yhi, PLUG_Z - ADAPTER_T / 2, 30)
    run = box(PLUG_X - ADAPTER_W / 2, L / 2 + RAIL + ADAPTER_RUN, ylo, yhi, PLUG_Z - ADAPTER_T / 2, 30)   # cable out the end
    cut = pocket + slot + run
    catches = Manifold()
    for side in (1, -1):
        # Along each long front edge, away from the plug slot: a ramp that the camera pushes past and clicks under.
        xs = [(-L / 2 + 1, L / 2 - 1)] if side != sy else [(-L / 2 + 1, PLUG_X - ADAPTER_W / 2 - 1)]
        for x0, x1 in xs:
            edge = side * W / 2
            into = edge + side * 0.6                                    # reach into the rail so it fuses
            lip = box(x0, x1, min(into, edge - side * CATCH), max(into, edge - side * CATCH), 0, 0.4)
            top = box(x0, x1, min(into, edge - side * 0.05), max(into, edge - side * 0.05), front - 0.05, front)
            catches = catches + Manifold.batch_hull([lip, top])
    return outer, cut, catches, L, W, T


def corners(m: Manifold):
    return np.asarray(m.to_mesh().vert_properties)[:, :3]


def build_angular(up_override=None):
    global PRINT_UP
    outer, cut, catches, L, W, T = holder_parts()
    r, u, f = frame()
    R = np.column_stack([r, u, f])
    # Pull the cradle in until it, and the adapter bay, just clear the plate.
    need = corners(outer + cut ^ box(-60, 60, -60, 60, -20, 2)) @ R.T
    lens_x = (STRIP_THICK + PT + 0.6) - need[:, 0].min()
    pts = corners(outer) @ R.T
    lens_y = -pts[:, 1].max()                                     # cradle top flush with the plate top
    lens = np.array([lens_x, lens_y, 0.0])
    cradle = placed(outer, lens)
    cv = corners(cradle)
    ph = SM_L - SM_TAB + 1.0                                      # plate covers the strip's sticky part; the tab hangs below
    zc = (cv[:, 2].min() + cv[:, 2].max()) / 2
    pw = SM_W + 2.0
    plate = box(STRIP_THICK, STRIP_THICK + PT, -ph, 0, zc - pw / 2, zc + pw / 2)
    body = Manifold.batch_hull([plate, cradle])
    th, tv = math.tan(math.radians(45 + 3)), math.tan(math.radians(33.5 + 3))
    far = 400.0
    view = Manifold.batch_hull([box(-0.3, 0.3, -0.3, 0.3, -0.8, -0.2)] +
                               [box(-0.1, 0.1, -0.1, 0.1, -0.1, 0.1).translate([sx * th * far, sy * tv * far, far]) for sx in (-1, 1) for sy in (-1, 1)])
    part = body - placed(cut + view.translate([LENS_X, 0, 1.0]), lens) + placed(catches, lens)
    part = part ^ box(STRIP_THICK, 400, -400, 400, -400, 400)     # nothing behind the plate's back
    PRINT_UP = up_override if up_override is not None else best_up(part)
    return part, lens


def best_up(part):
    """Try every flat face of the hull as the bed face; keep the one with the least overhang (bridges count a third)."""
    m = part.to_mesh(); v = np.asarray(m.vert_properties)[:, :3]; tri = v[np.asarray(m.tri_verts)]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); area = np.linalg.norm(n, axis=1) / 2
    n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    h = Manifold.batch_hull([part]).to_mesh(); hv = np.asarray(h.vert_properties)[:, :3]; ht = hv[np.asarray(h.tri_verts)]
    hn = np.cross(ht[:, 1] - ht[:, 0], ht[:, 2] - ht[:, 0]); hn = hn / np.linalg.norm(hn, axis=1, keepdims=True)
    best = None
    for c in np.unique(np.round(hn, 3), axis=0):
        up = -c / np.linalg.norm(c)
        hh = tri @ up; on = np.all(np.abs(hh - hh.min()) < 0.05, axis=1); down = n @ -up
        over = (~on) & (down > math.cos(math.radians(45)) + 1e-6); flat = over & (down > 0.98)
        score = area[over & ~flat].sum() + area[flat].sum() / 3 - 0.05 * area[on].sum()
        if best is None or score < best[0]:
            best = (score, up)
    return best[1]


def lens_pos():
    return build_angular()[1] if not CORNER else np.array([OUT, -DOWN, ALONG])


def report(part, lens):
    """Weight, the load on the strip, and what a printer has to bridge or overhang."""
    m = part.to_mesh()
    v = np.asarray(m.vert_properties)[:, :3]; tri = v[np.asarray(m.tri_verts)]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); area = np.linalg.norm(n, axis=1) / 2
    n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    vol = part.volume() / 1000
    out = {"volume_cm3": round(vol, 1)}
    for name, up in (("planned orientation", PRINT_UP), ("plate down", np.array([1.0, 0, 0]))):
        h = tri @ up
        on_bed = np.all(np.abs(h - h.min()) < 0.05, axis=1)
        down = (n @ -up)
        over = (~on_bed) & (down > math.cos(math.radians(45)) + 1e-6)
        flat = over & (down > 0.98)
        out[name] = {"overhang_mm2": round(float(area[over & ~flat].sum())), "flat_bridge_mm2": round(float(area[flat].sum())),
                     "bed_contact_mm2": round(float(area[on_bed].sum()))}
    # Mass: walls and top/bottom skins print solid, the rest at ~20% infill; call it 55% of solid PETG/PLA (1.25 g/cm3).
    grams = vol * 1.25 * 0.55
    r, u, f = frame()
    cam_c = lens - f * (CAM_T / 2)
    com_x = (grams * float(np.mean(v[:, 0])) + 22 * cam_c[0]) / (grams + 22)
    out.update(mount_g=round(grams, 1), camera_g=22, lever_mm=round(com_x, 1),
               peel_Nmm=round((grams + 22) / 1000 * 9.81 * com_x, 1))
    return out


def main():
    part = build() if CORNER else build_angular()[0]
    mesh: Mesh = part.to_mesh()
    tm = trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts))
    out = pathlib.Path(__file__).with_name(f"{SPOT}_mount.stl")
    tm.export(out)
    ext = tm.bounds[1] - tm.bounds[0]
    print(f"wrote {out.name}: {len(tm.faces)} triangles, {ext[0]:.0f} × {ext[1]:.0f} × {ext[2]:.0f} mm, "
          f"watertight {tm.is_watertight}, volume {tm.volume / 1000:.1f} cm³")
    r, u, f = frame()
    print("aim (room x, y, z):", np.round(f, 3), " camera right:", np.round(r, 3))
    if not CORNER:
        print(report(*build_angular()))


if __name__ == "__main__":
    main()
