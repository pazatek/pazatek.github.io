"""Photoreal Room Coach room, built in Blender from the same coordinates the app's 2D renderer uses (core.js), rendered with Cycles.

Run on the Mac:
    /Applications/Blender.app/Contents/MacOS/Blender -b -P build_scene.py -- --out out/test.png [--samples 128] [--width 1200]
        [--layer all|day|pixar|little|fan|fill] [--night] [--blend out/room.blend]

Coordinates: the app works in metres with x along the door wall toward the bed, y up, z along the desk wall toward the window.
That frame is left-handed, so Blender gets (X, Y, Z) = (x, z, y), which also mirrors it into Blender's right-handed frame.
The camera is the app's true isometric view (35.26 degrees down, looking toward +x +z), orthographic, so a render lines up
with the app's drawing and the app can lay these images under its own overlays (door, window gap, fan).

Layers: every light source is rendered on its own (--layer). Light adds up, so the app can rebuild any lamp brightness and
colour live as   image = day*d + pixar*rgb_p*b_p + little*rgb_l*b_l + fan*f + fill,   each layer rendered with white light.
"""
import math
import sys
import random

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(name, default=None, flag=False):
    if flag:
        return f"--{name}" in argv
    return argv[argv.index(f"--{name}") + 1] if f"--{name}" in argv else default

OUT = arg("out", "out/test.png")
SAMPLES = int(arg("samples", 128))
WIDTH = int(arg("width", 1200))
LAYER = arg("layer", "all")
NIGHT = arg("night", flag=True)
BLEND = arg("blend")

# ---- room constants (core.js) ----
W, D, DM, NX, H, T = 3.33, 3.685, 2.865, 1.65, 2.4, 0.09
WX0, WX1, WY0, WY1 = 0.14, 1.46, 0.92, 2.0
AIM, JOINT = (0.8, 1.46, D), (0.27, 0.92, 2.88)  # FORSÅ stands on the PC (photos, 2026-11-17)
MINI = (1.56, 0.95, 0.27)
FAN = (1.665, 2.1, 1.435)

def B(x, y, z):
    return Vector((x, z, y))

def norm(v):
    l = math.sqrt(sum(c * c for c in v)) or 1
    return tuple(c / l for c in v)

AIMDIR = norm(tuple(a - j for a, j in zip(AIM, JOINT)))
BULB = tuple(j + d * 0.15 for j, d in zip(JOINT, AIMDIR))

# ---- scene ----
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
random.seed(7)

def collection(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c

C_ROOM, C_DAY, C_PIXAR, C_LITTLE, C_FAN, C_FILL = (collection(n) for n in ("room", "light_day", "light_pixar", "light_little", "light_fan", "light_fill"))

def hexcol(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb) + (1.0,)

def material(name, color="#ffffff", rough=0.5, metal=0.0, **kw):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = hexcol(color) if isinstance(color, str) else color
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    for k, v in kw.items():
        p.inputs[k].default_value = v
    return m

def add_noise_bump(m, scale=60.0, strength=0.04):
    nt = m.node_tree
    tex = nt.nodes.new("ShaderNodeTexNoise"); tex.inputs["Scale"].default_value = scale
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = strength
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], nt.nodes["Principled BSDF"].inputs["Normal"])
    return m

def wood(name, base="#c9965c", dark="#8f6337", scale=6.0, rough=0.45):
    """Procedural wood grain: stretched noise driving a two-colour ramp, along the object's long axis."""
    m = material(name, base, rough)
    nt = m.node_tree
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping"); mapping.inputs["Scale"].default_value = (1.0, 1.0, 14.0)
    noise = nt.nodes.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = scale; noise.inputs["Detail"].default_value = 8
    wave = nt.nodes.new("ShaderNodeTexWave"); wave.inputs["Scale"].default_value = 3.0; wave.inputs["Distortion"].default_value = 6.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = hexcol(dark); ramp.color_ramp.elements[1].color = hexcol(base)
    nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMath"); mix.operation = "MULTIPLY"
    nt.links.new(wave.outputs["Fac"], mix.inputs[0]); nt.links.new(noise.outputs["Fac"], mix.inputs[1])
    nt.links.new(mix.outputs["Value"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    return m

def planks(name, base="#a89f93", dark="#8a8275", rough=0.42):
    """Laminate planks: fine grain stretched along each plank (Blender X), and every plank a slightly different tone."""
    m = material(name, base, rough)
    nt = m.node_tree
    coord = nt.nodes.new("ShaderNodeTexCoord"); info = nt.nodes.new("ShaderNodeObjectInfo")
    mapping = nt.nodes.new("ShaderNodeMapping"); mapping.inputs["Scale"].default_value = (2.0, 60.0, 60.0)
    grain = nt.nodes.new("ShaderNodeTexNoise"); grain.inputs["Scale"].default_value = 3.0; grain.inputs["Detail"].default_value = 10; grain.inputs["Roughness"].default_value = 0.6
    nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"]); nt.links.new(mapping.outputs["Vector"], grain.inputs["Vector"])
    tone = nt.nodes.new("ShaderNodeMath"); tone.operation = "MULTIPLY_ADD"
    tone.inputs[1].default_value = 0.35; tone.inputs[2].default_value = 0.3
    nt.links.new(info.outputs["Random"], tone.inputs[0])
    mix = nt.nodes.new("ShaderNodeMath"); mix.operation = "ADD"
    g2 = nt.nodes.new("ShaderNodeMath"); g2.operation = "MULTIPLY"; g2.inputs[1].default_value = 0.45
    nt.links.new(grain.outputs["Fac"], g2.inputs[0]); nt.links.new(g2.outputs[0], mix.inputs[0]); nt.links.new(tone.outputs[0], mix.inputs[1])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = hexcol(dark); ramp.color_ramp.elements[1].color = hexcol(base)
    nt.links.new(mix.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.03
    nt.links.new(grain.outputs["Fac"], bump.inputs["Height"]); nt.links.new(bump.outputs["Normal"], nt.nodes["Principled BSDF"].inputs["Normal"])
    return m

M = {
    "wall": add_noise_bump(material("wall", "#e7e7e3", 0.92), 80, 0.02),
    "trim": material("trim", "#f4f4f2", 0.35),
    "floor": planks("floor"),
    "desk_top": material("desk_top", "#1b1b1e", 0.42),
    "desk_leg": material("desk_leg", "#2a2a2e", 0.35, 0.6),
    "white_plastic": material("white_plastic", "#efeeeb", 0.3),
    "screen": material("screen", "#050507", 0.08, **{"Coat Weight": 1.0}),
    "pc_glass": material("pc_glass", "#1d222b", 0.05, **{"Coat Weight": 1.0}),
    "bed_frame": material("bed_frame", "#5e5a57", 0.8, **{"Sheen Weight": 0.6}),
    "headboard": material("headboard", "#8e8e96", 0.85, **{"Sheen Weight": 0.6}),
    "duvet": material("duvet", "#f6f5f2", 0.9, **{"Sheen Weight": 0.8}),
    "stripe": material("stripe", "#4f86e8", 0.9, **{"Sheen Weight": 0.6}),
    "pillow": material("pillow", "#fbfaf7", 0.9, **{"Sheen Weight": 0.8}),
    "dresser": wood("dresser", "#c9a274", "#a47e52", 5.0, 0.45),
    "ash": wood("ash", "#d9b98a", "#b08d5e", 8.0, 0.5),
    "nickel": material("nickel", "#d8d9d6", 0.16, 1.0),
    "black_matte": material("black_matte", "#141416", 0.55),
    "black_metal": material("black_metal", "#1a1a1c", 0.4, 0.8),
    "ptac": material("ptac", "#e7e1cf", 0.5),
    "ptac_grille": material("ptac_grille", "#bdb6a3", 0.6),
    "mirror": material("mirror", "#ffffff", 0.02, 1.0),
    "mirror_frame": material("mirror_frame", "#c8c8c8", 0.3, 1.0),
    "frame_wood": wood("frame_wood", "#d9b98a", "#b89466", 10.0, 0.5),
    "mat_paper": material("mat_paper", "#f7f5f0", 0.9),
    "glass": material("glass", "#ffffff", 0.0, **{"Transmission Weight": 1.0, "IOR": 1.5}),
    "blind": material("blind", "#f2f1ec", 0.95, **{"Sheen Weight": 0.4}),
    "sword_blade": material("sword_blade", "#2b2b30", 0.25, 0.9),
    "gold": material("gold", "#c9a44a", 0.3, 1.0),
    "grass": material("grass", "#4f8a3f", 0.8),
    "desk_wood": wood("desk_wood", "#6e6156", "#4b4239", 7.0, 0.55),
    "desk_mat": material("desk_mat", "#141416", 0.95, **{"Sheen Weight": 0.3}),
    "oak": wood("oak", "#c9ab84", "#a88b65", 6.0, 0.45),
    "black_frame": material("black_frame", "#18181a", 0.45, 0.6),
    "fleece": material("fleece", "#e2602a", 0.95, **{"Sheen Weight": 1.0}),
    "printer_grey": material("printer_grey", "#cfd0ce", 0.45),
    "printer_dark": material("printer_dark", "#3b3c3f", 0.45),
    "laptop": material("laptop", "#2b2c2f", 0.35, 0.8),
    "photo_print": material("photo_print", "#3c4a35", 0.6),
    "slab": material("slab", "#151414", 1.0, **{"Specular IOR Level": 0.0}),
}
for name, hexc in (("art_teal", "#1aa39a"), ("art_yellow", "#f2c230"), ("art_green", "#1e5a3a"), ("art_navy", "#1b3a7a")):
    M[name] = material(name, hexc, 0.85)

def image_material(name, path, rough=0.5, uv=True):
    m = material(name, "#ffffff", rough)
    nt = m.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(path)
    if uv:
        nt.links.new(nt.nodes.new("ShaderNodeUVMap").outputs["UV"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    return m, tex

import os
HERE = os.path.dirname(os.path.abspath(__file__))
M["floor_photo"], _ft = image_material("floor_photo", os.path.join(HERE, "tex", "floor_planks.jpg"), 0.4)
_ft.extension = "REPEAT"
M["poster_fuji"], _ = image_material("poster_fuji", os.path.join(HERE, "tex", "poster_fuji.jpg"), 0.6)

def stripes(name, base, line, period=0.012, width=0.25, axis="Y"):
    """Pinstripe fabric: thin lines every `period` metres along one Blender axis."""
    m = material(name, base, 0.9, **{"Sheen Weight": 0.8})
    nt = m.node_tree
    coord = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Object"], sep.inputs["Vector"])
    frac = nt.nodes.new("ShaderNodeMath"); frac.operation = "WRAP"; frac.inputs[1].default_value = 0; frac.inputs[2].default_value = period
    nt.links.new(sep.outputs["X" if axis == "X" else "Y"], frac.inputs[0])
    lt = nt.nodes.new("ShaderNodeMath"); lt.operation = "LESS_THAN"; lt.inputs[1].default_value = period * width
    nt.links.new(frac.outputs[0], lt.inputs[0])
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
    mix.inputs[6].default_value = hexcol(base); mix.inputs[7].default_value = hexcol(line)
    nt.links.new(lt.outputs[0], mix.inputs[0]); nt.links.new(mix.outputs[2], nt.nodes["Principled BSDF"].inputs["Base Color"])
    return m

M["sheet"] = stripes("sheet", "#f1f0ed", "#7f8b99", 0.011, 0.3, "X")
M["duvet_stripe"] = stripes("duvet_stripe", "#c9ced6", "#f2f2f0", 0.016, 0.35, "X")

# The lamp shades: fabric that glows when lit from inside.
def shade_material(name, color):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    diff = nt.nodes.new("ShaderNodeBsdfDiffuse"); diff.inputs["Color"].default_value = hexcol(color)
    trans = nt.nodes.new("ShaderNodeBsdfTranslucent"); trans.inputs["Color"].default_value = hexcol(color)
    mix = nt.nodes.new("ShaderNodeMixShader"); mix.inputs["Fac"].default_value = 0.45
    nt.links.new(diff.outputs[0], mix.inputs[1]); nt.links.new(trans.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return m
M["linen"] = shade_material("linen", "#f3efe6")
M["frost"] = shade_material("frost", "#ffffff")

def link(obj, coll=C_ROOM):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    coll.objects.link(obj)
    return obj

def box(x0, x1, y0, y1, z0, z1, mat, name="box", bevel=0.004, coll=C_ROOM):
    """An axis-aligned box in app coordinates."""
    mesh = bpy.data.meshes.new(name)
    a, b = B(x0, y0, z0), B(x1, y1, z1)
    xs, ys, zs = (a.x, b.x), (a.y, b.y), (a.z, b.z)
    verts = [(xs[i], ys[j], zs[k]) for i in (0, 1) for j in (0, 1) for k in (0, 1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    mesh.from_pydata(verts, [], faces); mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    obj.data.materials.append(mat)
    if bevel and min(x1 - x0, y1 - y0, z1 - z0) > 2.5 * bevel:
        mod = obj.modifiers.new("bevel", "BEVEL"); mod.width = bevel; mod.segments = 2; mod.limit_method = "ANGLE"
    return obj

def hidden_from_camera(obj):
    obj.visible_camera = False
    return obj

def cylinder(p0, p1, r0, r1=None, mat=None, name="cyl", verts=32, cap=True, coll=C_ROOM):
    """A cylinder or cone between two app-coordinate points."""
    r1 = r0 if r1 is None else r1
    a, b = B(*p0), B(*p1)
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r0, radius2=r1, depth=(b - a).length, end_fill_type="NGON" if cap else "NOTHING")
    obj = bpy.context.active_object; obj.name = name
    obj.location = (a + b) / 2
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = (b - a).normalized().to_track_quat("Z", "Y")
    if mat:
        obj.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return link(obj, coll)

# ---- shell: floor, walls with the window, closet with mirror doors ----
def plank(x0, x1, z0, z1, strip, off):
    mesh = bpy.data.meshes.new("plank")
    a, b = B(x0, -0.02, z0), B(x1, 0, z1)
    verts = [(a.x, a.y, b.z), (b.x, a.y, b.z), (b.x, b.y, b.z), (a.x, b.y, b.z), (a.x, a.y, a.z), (b.x, a.y, a.z), (b.x, b.y, a.z), (a.x, b.y, a.z)]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    mesh.from_pydata(verts, [], faces); mesh.update()
    uv = mesh.uv_layers.new(name="UVMap")
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            v = mesh.vertices[mesh.loops[li].vertex_index].co
            # 1 texture width = 1.02 m of board; v picks the strip (0..2) in the stacked atlas
            uv.data[li].uv = (v.x / 1.02 + off, (strip + 0.02 + 0.96 * (v.y - a.y) / max(1e-6, b.y - a.y)) / 3)
    obj = bpy.data.objects.new("plank", mesh); C_ROOM.objects.link(obj); obj.data.materials.append(M["floor_photo"])
    return obj

PW = 0.19
for k in range(int(D / PW) + 1):
    z0, z1 = k * PW, min(D, (k + 1) * PW)
    if z1 - z0 < 0.005:
        continue
    plank(0, W if z0 < DM else NX, z0 + 0.0008, z1 - 0.0008, random.randrange(3), random.random() * 3)
box(0, W + T, -0.18, -0.02, 0, D + T, M["slab"], "slab", bevel=0)

# Window wall (z = D), built around the opening.
box(0, NX, 0, WY0, D, D + T, M["wall"], "wall_win_low", bevel=0)
box(0, NX, WY1, H, D, D + T, M["wall"], "wall_win_high", bevel=0)
box(0, WX0, WY0, WY1, D, D + T, M["wall"], "wall_win_l", bevel=0)
box(WX1, NX, WY0, WY1, D, D + T, M["wall"], "wall_win_r", bevel=0)
box(NX, W + T, 0, H, DM, D + T, M["wall"], "closet_block", bevel=0)
box(W, W + T, 0, H, 0, DM, M["wall"], "wall_posters", bevel=0)
# Walls the camera looks through (the app's cutaway) still bounce light and keep daylight out, as in the real room.
for o in (box(-T, 0, 0, H, -T, D + T, M["wall"], "wall_desk_near", bevel=0), box(-T, W + T, 0, H, -T, 0, M["wall"], "wall_door_near", bevel=0),
          box(-T, W + T, H, H + 0.1, -T, D + T, M["wall"], "ceiling", bevel=0)):
    hidden_from_camera(o)
# Skirting.
box(0, NX, 0, 0.08, D - 0.012, D, M["trim"], "skirt_win", bevel=0.002)
box(W - 0.012, W, 0, 0.08, 0, DM, M["trim"], "skirt_posters", bevel=0.002)

# Window: frame, a fixed pane and a sliding sash, sill, glass.
box(WX0 - 0.06, WX1 + 0.06, WY0 - 0.05, WY0, D - 0.07, D, M["trim"], "sill")
box(WX0 - 0.06, WX1 + 0.06, WY1, WY1 + 0.13, D - 0.09, D, M["trim"], "header")
for x0, x1 in ((WX0 - 0.03, WX0), (WX1, WX1 + 0.03)):
    box(x0, x1, WY0, WY1, D - 0.07, D, M["trim"], "jamb")
wm = (WX0 + WX1) / 2
for a, b, z in ((WX0, wm, D - 0.02), (wm, WX1, D - 0.045)):
    for (x0, x1, y0, y1) in ((a, b, WY0, WY0 + 0.035), (a, b, WY1 - 0.035, WY1), (a, a + 0.035, WY0, WY1), (b - 0.035, b, WY0, WY1)):
        box(x0, x1, y0, y1, z - 0.012, z + 0.012, M["trim"], "sash", bevel=0.002)
    box(a + 0.035, b - 0.035, WY0 + 0.035, WY1 - 0.035, z - 0.003, z + 0.003, M["glass"], "pane", bevel=0)
# Roller blind in a white cassette; BLIND_DOWN is how far it is pulled (0 up, 1 down).
BLIND_DOWN = float(arg("blind", 0.6))
box(WX0 - 0.05, WX1 + 0.05, WY1 - 0.07, WY1 + 0.005, D - 0.09, D - 0.035, M["trim"], "blind_cassette", bevel=0.004)
if BLIND_DOWN > 0.01:
    yb = WY1 - 0.07 - BLIND_DOWN * (WY1 - WY0 - 0.04)
    box(WX0 - 0.03, WX1 + 0.03, yb, WY1 - 0.07, D - 0.068, D - 0.064, M["blind"], "blind_fabric", bevel=0)
    box(WX0 - 0.03, WX1 + 0.03, yb - 0.02, yb, D - 0.072, D - 0.060, M["trim"], "blind_bar", bevel=0.002)
# Outside: lawn, so the window shows something like the real view.
hidden_from_camera(box(-3, 5, -0.4, -0.3, D + T, D + 8, M["grass"], "lawn", bevel=0))

# Closet with mirrored sliding doors on its front (z = DM).
for x0, x1 in ((1.85, 2.585), (2.595, W)):
    box(x0, x1, 0.04, 2.0, DM - 0.012, DM - 0.002, M["mirror"], "mirror", bevel=0)
    box(x0, x1, 0.02, 0.04, DM - 0.016, DM, M["mirror_frame"], "mirror_track", bevel=0.001)
    box(x0, x1, 2.0, 2.03, DM - 0.016, DM, M["mirror_frame"], "mirror_track", bevel=0.001)

# ---- heat/AC unit: GE Zoneline, cream, louvred front, vent grille and control door on top ----
PX0, PX1, PY0, PY1, PD = 0.35, 1.35, 0.28, 0.72, D - 0.21
box(PX0, PX1, PY0, PY1, PD, D, M["ptac"], "ptac", bevel=0.035)
for i in range(11):
    y = PY0 + 0.03 + i * 0.024
    box(PX0 + 0.02, PX1 - 0.02, y, y + 0.012, PD - 0.006, PD + 0.004, M["ptac"], "ptac_louvre", bevel=0.003)
box(PX0 + 0.05, PX0 + 0.72, PY1 - 0.004, PY1 + 0.002, PD + 0.03, D - 0.05, M["ptac_grille"], "ptac_vent", bevel=0)
for i in range(4):
    x = PX0 + 0.05 + i * 0.17
    box(x, x + 0.006, PY1, PY1 + 0.004, PD + 0.03, D - 0.05, M["ptac"], "ptac_vent_rib", bevel=0)
box(PX0 + 0.76, PX1 - 0.05, PY1 - 0.003, PY1 + 0.003, PD + 0.03, D - 0.05, M["ptac"], "ptac_door", bevel=0.004)

# ---- desk: rustic wood top on a black metal frame, black desk mat ----
for lx, lz in ((0.01, 2.53), (0.51, 2.53), (0.01, 1.605), (0.51, 1.605)):
    box(lx, lx + 0.035, 0, 0.73, lz, lz + 0.035, M["black_frame"], "desk_leg", bevel=0.003)
for lz in (1.605, 2.53):
    box(0.01, 0.545, 0.1, 0.13, lz, lz + 0.035, M["black_frame"], "desk_rail", bevel=0.002)
    box(0.01, 0.545, 0.69, 0.73, lz, lz + 0.035, M["black_frame"], "desk_rail", bevel=0.002)
box(0.0, 0.03, 0.69, 0.73, 1.605, 2.565, M["black_frame"], "desk_rail", bevel=0.002)
box(0, 0.56, 0.73, 0.76, 1.6, 2.57, M["desk_wood"], "desk_top", bevel=0.004)
box(0.12, 0.55, 0.76, 0.764, 1.72, 2.47, M["desk_mat"], "desk_mat", bevel=0.002)
box(0.30, 0.42, 0.764, 0.79, 1.95, 2.28, M["white_plastic"], "keyboard", bevel=0.006)
box(0.305, 0.41, 0.79, 0.794, 1.96, 2.27, M["mat_paper"], "keycaps", bevel=0.002)
# headphones: two cups and a band, lying on the mat
for zc in (2.33, 2.43):
    cylinder((0.44, 0.764, zc), (0.44, 0.80, zc), 0.045, mat=M["white_plastic"], name="ear_cup", verts=24)
cylinder((0.40, 0.79, 2.33), (0.40, 0.79, 2.43), 0.012, mat=M["white_plastic"], name="headband", verts=12)
# monitor (MSI 27") on a gas-spring arm clamped at the back edge
box(0.06, 0.09, 0.68, 0.79, 2.12, 2.20, M["black_frame"], "monitor_clamp", bevel=0.003)
cylinder((0.075, 0.76, 2.16), (0.075, 1.0, 2.16), 0.018, mat=M["black_frame"], name="arm_post")
cylinder((0.075, 1.0, 2.16), (0.13, 1.02, 2.06), 0.016, mat=M["black_frame"], name="arm_seg")
box(0.13, 0.155, 0.92, 1.28, 1.76, 2.37, M["black_matte"], "monitor", bevel=0.004)
box(0.155, 0.157, 0.935, 1.27, 1.772, 2.358, M["screen"], "screen", bevel=0)
# laptop on a second arm, reaching toward the window
cylinder((0.06, 0.76, 2.50), (0.06, 1.02, 2.50), 0.018, mat=M["black_frame"], name="laptop_post")
cylinder((0.06, 1.02, 2.50), (0.30, 1.07, 2.78), 0.016, mat=M["black_frame"], name="laptop_arm")
box(0.24, 0.52, 1.05, 1.062, 2.72, 3.02, M["black_frame"], "laptop_tray", bevel=0.002)
box(0.25, 0.51, 1.062, 1.075, 2.73, 3.01, M["laptop"], "laptop_base", bevel=0.003)
box(0.24, 0.252, 1.075, 1.29, 2.73, 3.01, M["laptop"], "laptop_lid", bevel=0.003)
box(0.252, 0.254, 1.09, 1.28, 2.745, 2.995, M["screen"], "laptop_screen", bevel=0)
# Elgato boom arm and mic at the door end
box(0.03, 0.08, 0.68, 0.79, 1.61, 1.66, M["black_frame"], "boom_clamp", bevel=0.003)
cylinder((0.055, 0.79, 1.635), (0.055, 0.92, 1.635), 0.016, mat=M["black_frame"], name="boom_post")
cylinder((0.055, 0.92, 1.635), (0.42, 1.22, 1.62), 0.018, mat=M["black_frame"], name="boom")
cylinder((0.42, 1.12, 1.62), (0.42, 1.27, 1.62), 0.022, mat=M["black_metal"], name="mic")
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.034, location=B(0.42, 1.30, 1.62)); _o = link(bpy.context.active_object); _o.data.materials.append(M["desk_mat"]); _o.scale.z = 1.25

# ---- PC: white case, perforated top, glass side toward the desk ----
PCY = 0.42
box(0.05, 0.47, 0.0, PCY, 2.585, 2.855, M["white_plastic"], "pc", bevel=0.006)
box(0.08, 0.44, 0.04, PCY - 0.03, 2.583, 2.586, M["pc_glass"], "pc_glass", bevel=0)
box(0.40, 0.47, PCY - 0.004, PCY + 0.001, 2.62, 2.82, M["mat_paper"], "pc_io", bevel=0)

# FORSÅ ("pixar") stands on the PC; its dome points at the window wall.
base, elbow = (0.26, PCY + 0.02, 2.71), (0.25, PCY + 0.26, 2.79)
cylinder((0.26, PCY, 2.71), base, 0.075, 0.068, mat=M["nickel"], name="forsa_base", verts=48)
for a, b in ((base, elbow), (elbow, JOINT)):
    for dz in (-0.012, 0.012):
        cylinder((a[0], a[1], a[2] + dz), (b[0], b[1], b[2] + dz), 0.005, mat=M["nickel"], name="forsa_arm", verts=10)
    cylinder((a[0] + 0.015, a[1], a[2]), (b[0] + 0.015, b[1], b[2]), 0.0035, mat=M["nickel"], name="forsa_spring", verts=8)
for j in (elbow, JOINT):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.013, location=B(*j)); o = bpy.context.active_object; o.data.materials.append(M["nickel"]); bpy.ops.object.shade_smooth(); link(o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.085, location=B(*tuple(j + d * 0.09 for j, d in zip(JOINT, AIMDIR))), segments=64, ring_count=32)
shell = link(bpy.context.active_object); shell.name = "forsa_shade"; shell.data.materials.append(M["nickel"]); bpy.ops.object.shade_smooth()
# cut the dome open on the side it shines from: keep the half behind the bulb
shell.rotation_mode = "QUATERNION"; shell.rotation_quaternion = B(*AIMDIR).to_track_quat("Z", "Y")
import bmesh
_bm = bmesh.new(); _bm.from_mesh(shell.data)
bmesh.ops.delete(_bm, geom=[v for v in _bm.verts if v.co.z > 0.01], context="VERTS")
_bm.to_mesh(shell.data); _bm.free()
shell.modifiers.new("solid", "SOLIDIFY").thickness = 0.0015
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.03, location=B(*tuple(j + d * 0.1 for j, d in zip(JOINT, AIMDIR))))
pixar_bulb = link(bpy.context.active_object); pixar_bulb.name = "pixar_bulb"; pixar_bulb.data.materials.append(M["frost"])

# ---- bed: black metal platform frame, oak-plank headboard, striped sheets, orange fleece ----
BX0, BX1, BZ0, BZ1, RAIL, MTOP = 1.80, 3.30, 0.065, 2.035, 0.30, 0.54
for x in (BX0, BX1 - 0.03):
    box(x, x + 0.03, RAIL - 0.05, RAIL, BZ0, BZ1, M["black_frame"], "bed_rail", bevel=0.002)
box(BX0, BX1, RAIL - 0.05, RAIL, BZ1 - 0.03, BZ1, M["black_frame"], "bed_rail", bevel=0.002)
for i in range(14):
    z = BZ0 + 0.06 + i * 0.135
    box(BX0 + 0.03, BX1 - 0.03, RAIL - 0.02, RAIL, z, z + 0.05, M["black_frame"], "bed_slat", bevel=0)
for x in (BX0, (BX0 + BX1) / 2 - 0.015, BX1 - 0.03):
    for z in (BZ0 + 0.02, (BZ0 + BZ1) / 2, BZ1 - 0.04):
        box(x, x + 0.03, 0, RAIL - 0.05, z, z + 0.03, M["black_frame"], "bed_leg", bevel=0.002)
box(BX0 + 0.01, BX1 - 0.01, RAIL, MTOP, BZ0 + 0.01, BZ1 - 0.01, M["sheet"], "mattress", bevel=0.04)
for px0 in (1.95, 2.65):
    p = box(px0, px0 + 0.58, MTOP - 0.01, MTOP + 0.13, 0.11, 0.52, M["sheet"], "pillow", bevel=0.06)
# duvet folded back toward the foot, the orange Illinois fleece on top of it
box(BX0 + 0.03, BX1 - 0.03, MTOP - 0.005, MTOP + 0.06, 1.35, BZ1 - 0.02, M["duvet_stripe"], "duvet", bevel=0.03)
box(BX0 + 0.06, BX1 - 0.06, MTOP + 0.06, MTOP + 0.11, 1.30, 1.55, M["duvet_stripe"], "duvet_fold", bevel=0.025)
box(BX0 + 0.02, BX0 + 0.75, MTOP + 0.06, MTOP + 0.1, 1.45, 1.98, M["fleece"], "fleece", bevel=0.02)
# headboard against the door wall: black frame, three oak planks
HB = 1.02
# It stands against the cut-away door wall, so like that wall it is hidden from the camera but still shades the bed.
hb = [box(x, x + 0.03, 0, HB, 0.0, 0.03, M["black_frame"], "hb_post", bevel=0.002) for x in (BX0, BX1 - 0.03)]
hb.append(box(BX0, BX1, HB - 0.03, HB, 0.0, 0.03, M["black_frame"], "hb_top", bevel=0.002))
for i, (y0_, y1_) in enumerate(((0.38, 0.55), (0.585, 0.755), (0.79, 0.96))):
    hb.append(box(BX0 + 0.03, BX1 - 0.03, y0_, y1_, 0.004, 0.026, M["oak"], "hb_plank", bevel=0.002))
    hb.append(box(BX0 + 0.03, BX1 - 0.03, y1_, y1_ + 0.035, 0.008, 0.022, M["black_frame"], "hb_bar", bevel=0))
for o in hb:
    hidden_from_camera(o)

# ---- dresser: two stacked two-drawer units, light oak with black edges and bar handles ----
DX0, DX1, DZ1 = 0.80, 1.77, 0.435
for y0_, y1_ in ((0.0, 0.47), (0.475, 0.95)):
    box(DX0, DX1, y0_, y1_, 0, DZ1, M["black_frame"], "dresser_carcass", bevel=0.004)
    box(DX0 + 0.015, DX1 - 0.015, y0_ + 0.015, y1_ - 0.015, DZ1 - 0.002, DZ1 + 0.004, M["oak"], "drawer_front", bevel=0.002)
    box(DX0 - 0.002, DX0, y0_ + 0.015, y1_ - 0.015, 0.015, DZ1 - 0.015, M["oak"], "dresser_side", bevel=0)
    mid = (y0_ + y1_) / 2
    box(DX0 + 0.015, DX1 - 0.015, mid - 0.003, mid + 0.003, DZ1 + 0.003, DZ1 + 0.005, M["black_frame"], "drawer_gap", bevel=0)
    for yh in (y1_ - 0.05, mid - 0.05):
        box(1.17, 1.40, yh, yh + 0.018, DZ1 + 0.004, DZ1 + 0.02, M["black_frame"], "drawer_handle", bevel=0.002)
box(DX0 + 0.01, DX1 - 0.01, 0.95, 0.953, 0.01, DZ1 - 0.01, M["oak"], "dresser_top", bevel=0)
# CO2 meter, mug
box(1.18, 1.30, 0.953, 1.03, 0.30, 0.33, M["white_plastic"], "co2_meter", bevel=0.006)
cylinder((1.62, 0.953, 0.33), (1.62, 1.06, 0.33), 0.04, mat=M["white_plastic"], name="mug", verts=32)
# sword stand: black two-tier rack with two katanas
box(0.98, 1.60, 0.953, 0.975, 0.03, 0.13, M["black_matte"], "sword_base")
for x in (1.02, 1.52):
    box(x, x + 0.03, 0.975, 1.27, 0.06, 0.10, M["black_matte"], "sword_post")
for y, L in ((1.10, 0.95), (1.25, 1.05)):
    cylinder((1.29 - L / 2, y, 0.08), (1.29 + L / 2, y + 0.025, 0.08), 0.013, mat=M["black_metal"], name="saya")
    cylinder((1.29 - L / 2 - 0.25, y - 0.012, 0.08), (1.29 - L / 2, y, 0.08), 0.012, mat=M["black_matte"], name="tsuka")
    cylinder((1.29 - L / 2 - 0.004, y - 0.03, 0.08), (1.29 - L / 2 + 0.004, y + 0.03, 0.08), 0.03, mat=M["gold"], name="tsuba", verts=24)

# STORSEGEL table lamp ("little"): three ash legs and a white linen drum.
cx, y0, cz = MINI
for a in (0.5, 2.6, 4.7):
    cylinder((cx + 0.09 * math.cos(a), y0, cz + 0.09 * math.sin(a)), (cx + 0.025 * math.cos(a), y0 + 0.17, cz + 0.025 * math.sin(a)), 0.009, mat=M["ash"], name="storsegel_leg", verts=12)
cylinder((cx, y0 + 0.13, cz), (cx, y0 + 0.30, cz), 0.088, mat=M["linen"], name="storsegel_shade", verts=64, cap=False)
little_bulb = cylinder((cx, y0 + 0.17, cz), (cx, y0 + 0.24, cz), 0.022, mat=M["frost"], name="little_bulb", verts=24)

# ---- posters on the bed wall: light wood frames, white mats ----
px = W - 0.002
POSTERS = ((2.305, ("#1aa39a", "#d65a8c")), (1.425, ("#2f6b3a", "#e8762b")), (0.555, None))
for pz, cols in POSTERS:
    box(px - 0.025, px, 1.14, 2.05, pz - 0.305, pz + 0.305, M["frame_wood"], "poster_frame", bevel=0.003)
    box(px - 0.027, px - 0.025, 1.17, 2.02, pz - 0.275, pz + 0.275, M["mat_paper"], "poster_mat", bevel=0)
    if cols is None:
        mesh = bpy.data.meshes.new("poster_art")
        corners = [B(px - 0.029, 1.22, pz + 0.215), B(px - 0.029, 1.22, pz - 0.215), B(px - 0.029, 1.97, pz - 0.215), B(px - 0.029, 1.97, pz + 0.215)]
        mesh.from_pydata(corners, [], [(0, 1, 2, 3)]); mesh.update()
        uv = mesh.uv_layers.new(name="UVMap")
        for li, (u, v) in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
            uv.data[li].uv = (u, v)
        o = bpy.data.objects.new("poster_fuji", mesh); C_ROOM.objects.link(o); o.data.materials.append(M["poster_fuji"])
    else:
        box(px - 0.029, px - 0.027, 1.22, 1.97, pz - 0.215, pz + 0.215, material("poster_bg", cols[0], 0.8), "poster_art", bevel=0)
        box(px - 0.031, px - 0.029, 1.35, 1.75, pz - 0.12, pz + 0.08, material("poster_fg", cols[1], 0.8), "poster_figure", bevel=0)

# framed photo on the closet's side wall, next to the window
box(NX - 0.022, NX, 1.22, 1.56, 3.05, 3.55, M["frame_wood"], "photo_frame", bevel=0.003)
box(NX - 0.024, NX - 0.022, 1.26, 1.52, 3.09, 3.51, M["mat_paper"], "photo_mat", bevel=0)
box(NX - 0.026, NX - 0.024, 1.31, 1.47, 3.17, 3.43, M["photo_print"], "photo", bevel=0)

# corner between the AC and the closet: printer with the router on it
box(1.38, 1.63, 0.0, 0.2, D - 0.40, D - 0.02, M["printer_grey"], "printer", bevel=0.01)
box(1.38, 1.63, 0.06, 0.12, D - 0.402, D - 0.38, M["printer_dark"], "printer_tray", bevel=0.003)
box(1.41, 1.60, 0.2, 0.245, D - 0.36, D - 0.08, M["black_matte"], "router", bevel=0.006)
for (ax, az) in ((1.42, D - 0.34), (1.59, D - 0.34), (1.42, D - 0.10), (1.59, D - 0.10)):
    cylinder((ax, 0.245, az), (ax, 0.40, az + 0.02), 0.007, mat=M["black_matte"], name="antenna", verts=8)

# ---- ceiling fan: Hampton Bay Mena 44", matte black, five blades, LED light kit ----
fx, fy, fz = FAN
cylinder((fx, H, fz), (fx, H - 0.04, fz), 0.07, 0.06, mat=M["black_matte"], name="fan_canopy", verts=48)
cylinder((fx, H - 0.04, fz), (fx, fy + 0.07, fz), 0.011, mat=M["black_matte"], name="fan_rod", verts=16)
cylinder((fx, fy + 0.07, fz), (fx, fy - 0.03, fz), 0.085, 0.1, mat=M["black_matte"], name="fan_motor", verts=64)
cylinder((fx, fy - 0.03, fz), (fx, fy - 0.07, fz), 0.07, 0.055, mat=M["black_matte"], name="fan_lightkit", verts=48)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.055, location=B(fx, fy - 0.07, fz)); dome = link(bpy.context.active_object)
dome.scale.z = 0.45; dome.data.materials.append(M["frost"]); bpy.ops.object.shade_smooth(); dome.name = "fan_dome"
R_FAN = 0.56
for i in range(5):
    t = i * 2 * math.pi / 5 + 0.3
    c, s = math.cos(t), math.sin(t)
    # blade: a thin tapered board, pitched 12 degrees
    mesh = bpy.data.meshes.new("blade")
    r0, r1, w0, w1, th = 0.13, R_FAN, 0.05, 0.065, 0.006
    pts = []
    for r, w in ((r0, w0), (r1, w1)):
        for side in (-1, 1):
            for up in (0, 1):
                tilt = side * w * math.sin(math.radians(12))
                pts.append(B(fx + r * c - side * w * s, fy + 0.005 + tilt + up * th, fz + r * s + side * w * c))
    faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    mesh.from_pydata(pts, [], faces); mesh.update()
    o = bpy.data.objects.new("fan_blade", mesh); C_ROOM.objects.link(o); o.data.materials.append(M["black_matte"])
    o.modifiers.new("bevel", "BEVEL").width = 0.002
    cylinder((fx + 0.06 * c, fy + 0.0, fz + 0.06 * s), (fx + 0.14 * c, fy + 0.005, fz + 0.14 * s), 0.012, mat=M["black_metal"], name="blade_iron", verts=10)
for dx in (-0.03, 0.03):
    cylinder((fx + dx, fy - 0.05, fz + 0.02), (fx + dx, fy - 0.3, fz + 0.02), 0.0015, mat=M["nickel"], name="pull_chain", verts=6)

# ---- chair: the same Uplift Pursuit mesh the app draws ----
import os
here = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.obj_import(filepath=os.path.join(here, "chair.obj"), forward_axis="Y", up_axis="Z")
chair_mats = {"frame_white": material("chair_white", "#ededE8".lower(), 0.35), "shell_grey": material("chair_grey", "#9ea1a3", 0.5),
              "dark": material("chair_dark", "#3d3d40", 0.5), "fabric": material("chair_fabric", "#54667a", 0.9, **{"Sheen Weight": 0.7})}
for o in list(bpy.context.selected_objects):
    link(o)
    for slot in o.material_slots:
        key = slot.material.name.split(".")[0] if slot.material else None
        if key in chair_mats:
            slot.material = chair_mats[key]
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35)) if hasattr(bpy.ops.object, "shade_smooth_by_angle") else bpy.ops.object.shade_smooth()

# ---- lights (one collection each, so each can be rendered on its own) ----
def light(kind, name, loc, energy, coll, size=0.05, direction=None, spot=None, blend=0.3, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy; ld.color = color
    if kind in ("POINT", "SPOT"):
        ld.shadow_soft_size = size
    if kind == "SPOT":
        ld.spot_size = spot; ld.spot_blend = blend
    o = bpy.data.objects.new(name, ld); coll.objects.link(o)
    o.location = loc
    if direction is not None:
        o.rotation_mode = "QUATERNION"; o.rotation_quaternion = Vector(direction).to_track_quat("-Z", "Y")
    return o

# 800 lm bulbs (Govee H600B). Cycles watts here are tuned by eye; the app rescales each layer anyway.
light("SPOT", "pixar_spot", B(*BULB), 40, C_PIXAR, size=0.03, direction=B(*AIMDIR) - B(0, 0, 0), spot=math.radians(95), blend=0.45, color=(1, 0.86, 0.68))
light("POINT", "little_point", B(cx, y0 + 0.21, cz), 22, C_LITTLE, size=0.03, color=(1, 0.86, 0.68))
light("POINT", "fan_point", B(fx, fy - 0.1, fz), 25, C_FAN, size=0.05, color=(1, 0.95, 0.88))
# A dim, even fill so shadowed corners are never pure black (the room's other light: hallway, screens, standby LEDs).
light("AREA", "fill", B(W / 2, H - 0.05, D / 2), 6, C_FILL, direction=Vector((0, 0, -1))).data.size = 2.5

# Daylight: sky world + a sun coming in through the window.
world = bpy.data.worlds.new("world"); scene.world = world; world.use_nodes = True
wnt = world.node_tree; bg = wnt.nodes["Background"]
sky = wnt.nodes.new("ShaderNodeTexSky")
for t in ("MULTIPLE_SCATTERING", "SINGLE_SCATTERING", "NISHITA"):
    try:
        sky.sky_type = t
        break
    except Exception:
        pass
try:
    sky.sun_elevation = math.radians(22); sky.sun_rotation = math.radians(200)
except Exception:
    pass
wnt.links.new(sky.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 0.0 if NIGHT else 1.0
sun = light("SUN", "sun", (0, 0, 10), 0 if NIGHT else 4.5, C_DAY, direction=Vector((-0.35, -0.85, -0.42)), color=(1, 0.93, 0.82))
sun.data.angle = math.radians(1.5)

# ---- which layer this render is ----
lights_on = {"all": {"day", "pixar", "little", "fan", "fill"}, "lamps": {"pixar", "little", "fill"}}.get(LAYER, {LAYER})
for key, coll in (("day", C_DAY), ("pixar", C_PIXAR), ("little", C_LITTLE), ("fan", C_FAN), ("fill", C_FILL)):
    coll.hide_render = key not in lights_on
if "day" not in lights_on:
    bg.inputs["Strength"].default_value = 0.0
# Glowing bulbs and shades only in their own layer.
def glow(obj, on, strength, color=(1, 0.86, 0.68)):
    m = material(obj.name + "_glow", (*color, 1.0), 0.5, **{"Emission Color": (*color, 1.0), "Emission Strength": strength if on else 0.0})
    obj.data.materials.clear(); obj.data.materials.append(m)
glow(pixar_bulb, "pixar" in lights_on, 40)
glow(little_bulb, "little" in lights_on, 30)
glow(dome, "fan" in lights_on, 12, (1, 0.95, 0.88))

# ---- camera: the app's isometric view, orthographic ----
cam_d = bpy.data.cameras.new("cam"); cam_d.type = "ORTHO"
cam = bpy.data.objects.new("cam", cam_d); scene.collection.objects.link(cam); scene.camera = cam
centre = B(W / 2, H / 2, D / 2)
view = Vector((-1, -1, 1)).normalized()
cam.location = centre + view * 20
cam.rotation_mode = "QUATERNION"; cam.rotation_quaternion = (-view).to_track_quat("-Z", "Y")
cam_d.clip_end = 60
# Fit the room's bounding box (as core.js size() does) with a small margin.
corners = [B(x, y, z) for x in (0, W + T) for z in (0, D + T) for y in (-0.18, H)]
rot = cam.rotation_quaternion.to_matrix().inverted()
pts = [rot @ (p - cam.location) for p in corners]
xs, ys = [p.x for p in pts], [p.y for p in pts]
wspan, hspan = max(xs) - min(xs), max(ys) - min(ys)
aspect = hspan / wspan
cam_d.ortho_scale = max(wspan, hspan) * 1.04
cam_d.shift_x = (max(xs) + min(xs)) / 2 / cam_d.ortho_scale
cam_d.shift_y = (max(ys) + min(ys)) / 2 / cam_d.ortho_scale
scene.render.resolution_x = WIDTH
scene.render.resolution_y = int(round(WIDTH * aspect))
scene.render.resolution_percentage = 100
scene.render.film_transparent = True

# ---- Cycles on the Mac GPU ----
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
for dev in ("METAL", "OPTIX", "CUDA"):
    try:
        prefs.compute_device_type = dev
        prefs.get_devices()
        if any(d.type == dev for d in prefs.devices):
            break
    except Exception:
        pass
for d in prefs.devices:
    d.use = True
scene.cycles.device = "GPU"
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 8
scene.cycles.caustics_reflective = False
scene.cycles.caustics_refractive = False
scene.view_settings.view_transform = "AgX"
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
scene.view_settings.exposure = 0.0

if OUT.endswith(".exr"):
    scene.render.image_settings.file_format = "OPEN_EXR"; scene.render.image_settings.color_depth = "16"
else:
    scene.render.image_settings.file_format = "PNG"; scene.render.image_settings.color_mode = "RGBA"
scene.render.filepath = os.path.join(here, OUT)
if BLEND:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(here, BLEND))
bpy.ops.render.render(write_still=True)
print("RENDERED", scene.render.filepath, scene.render.resolution_x, scene.render.resolution_y, "layer", LAYER)
