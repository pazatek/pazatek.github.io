"""Door-corner mount for the Waveshare Thermal-90 USB Camera (B).

Two plates stick to the two walls of the corner above the door (Command strips or VHB), and a cradle holds the camera
aimed the way the room model found best: 40° from the desk wall toward the bed, 33° down.

Room frame, millimetres, origin at the corner where the plates meet, top of the mount at y = 0:
  x runs along the door wall toward the drawer and bed, y is up, z runs along the desk wall toward the window.
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
PLUG_END = +1        # which short end the USB-C plug comes out of: +1 or -1 along the camera's long axis

# Aim (matches the room model and thermal_agent.py's POSE).
YAW, TILT = 40.0, -33.0
# Where the lens sits, measured from the corner (mm): out from each wall, and down from the top of the mount.
OUT, DOWN = 46.0, 28.0

PLATE, PLATE_H, PLATE_T = 72.0, 48.0, 4.0


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def frame():
    y, t = math.radians(YAW), math.radians(TILT)
    fwd = unit([math.sin(y) * math.cos(t), math.sin(t), math.cos(y) * math.cos(t)])
    right = unit(np.cross([0, 1, 0], fwd))
    up = np.cross(fwd, right)
    return right, up, fwd


def placed(m: Manifold, origin):
    """Move a part modelled in camera coordinates (x = long axis, y = short axis, z = optical axis) into the room."""
    r, u, f = frame()
    mat = np.column_stack([r, u, f, origin])  # 3×4
    return m.transform(mat)


def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def build():
    lens = np.array([OUT, -DOWN, OUT])
    L, W, T = CAM_L + 2 * FIT, CAM_W + 2 * FIT, CAM_T + FIT
    # Camera coordinates: lens face at z = 0, body behind it (z < 0).
    outer = box(-L / 2 - WALL, L / 2 + WALL, -W / 2 - WALL, W / 2 + WALL, -T - WALL, 0)
    pocket = box(-L / 2, L / 2, -W / 2, W / 2, -T, 5)
    window = box(-L / 2 + 1.5, L / 2 - 1.5, -W / 2 + LIP, W / 2 - LIP, -1, 5)       # opening in front of the lens face
    lips = box(-L / 2 - WALL, L / 2 + WALL, -W / 2 - WALL, W / 2 + WALL, 0, 1.2) - window
    # The plug end is left open: the camera slides in from there under the lips, and the plug and cable come out of it.
    slide = box(-L / 2, L / 2, -W / 2, W / 2, -T, 0).translate([PLUG_END * L, 0, 0])
    stop = box(-0.6, 0.6, -W / 2, W / 2, -T, -T + 0.5).translate([PLUG_END * (L / 2 - 0.6), 0, 0])  # small bump that clicks it in place
    cradle = placed(((outer + lips) - pocket - slide) + stop, lens)
    back = placed(box(-L / 2 - WALL, L / 2 + WALL, -W / 2 - WALL, W / 2 + WALL, -T - WALL, -T), lens)
    plug = slide

    plate_door = box(0, PLATE, -PLATE_H, 0, 0, PLATE_T)        # on the door wall (z = 0)
    plate_desk = box(0, PLATE_T, -PLATE_H, 0, 0, PLATE)        # on the desk wall (x = 0)
    knuckle = box(0, 14, -PLATE_H, 0, 0, 14)                   # solid corner where the plates meet
    stem = Manifold.batch_hull([back, knuckle])
    part = plate_door + plate_desk + knuckle + stem + cradle
    part = part - placed(pocket, lens) - placed(slide, lens) - placed(plug, lens)
    keep = box(0, 400, -400, 400, 0, 400)                      # nothing may poke into the walls
    return part ^ keep


def main():
    part = build()
    mesh: Mesh = part.to_mesh()
    tm = trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts))
    out = pathlib.Path(__file__).with_name("door_corner_mount.stl")
    tm.export(out)
    ext = tm.bounds[1] - tm.bounds[0]
    print(f"wrote {out.name}: {len(tm.faces)} triangles, {ext[0]:.0f} × {ext[1]:.0f} × {ext[2]:.0f} mm, "
          f"watertight {tm.is_watertight}, volume {tm.volume / 1000:.1f} cm³")
    r, u, f = frame()
    print("aim (room x, y, z):", np.round(f, 3), " camera right:", np.round(r, 3))


if __name__ == "__main__":
    main()
