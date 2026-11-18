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
AIM, JOINT = (0.8, 1.46, D), (0.3, 0.68, 3.1)
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
    "wall": add_noise_bump(material("wall", "#e4e1db", 0.92), 80, 0.02),
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
    "ptac": material("ptac", "#e3d6b8", 0.55),
    "ptac_grille": material("ptac_grille", "#a99c7e", 0.6),
    "mirror": material("mirror", "#ffffff", 0.02, 1.0),
    "mirror_frame": material("mirror_frame", "#c8c8c8", 0.3, 1.0),
    "frame_wood": wood("frame_wood", "#d9b98a", "#b89466", 10.0, 0.5),
    "mat_paper": material("mat_paper", "#f7f5f0", 0.9),
    "glass": material("glass", "#ffffff", 0.0, **{"Transmission Weight": 1.0, "IOR": 1.5}),
    "blind": material("blind", "#e6e2d8", 0.95, **{"Sheen Weight": 0.4}),
    "sword_blade": material("sword_blade", "#2b2b30", 0.25, 0.9),
    "gold": material("gold", "#c9a44a", 0.3, 1.0),
    "grass": material("grass", "#4f8a3f", 0.8),
    "slab": material("slab", "#2a2826", 1.0),
}
for name, hexc in (("art_teal", "#1aa39a"), ("art_yellow", "#f2c230"), ("art_green", "#1e5a3a"), ("art_navy", "#1b3a7a")):
    M[name] = material(name, hexc, 0.85)

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
for k, z0 in enumerate([i * 0.21 for i in range(int(D / 0.21) + 1)]):
    z1 = min(D, z0 + 0.21)
    if z1 <= z0:
        continue
    xe = W if z0 < DM else NX
    plank = box(0, xe, -0.02, 0, z0 + 0.001, z1 - 0.001, M["floor"], "plank", bevel=0.0015)
    plank["tone"] = random.random()
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
# Roller blind, rolled up under the header.
cylinder((WX0 - 0.04, WY1 - 0.02, D - 0.06), (WX1 + 0.04, WY1 - 0.02, D - 0.06), 0.03, mat=M["blind"], name="blind_roll")
# Outside: lawn, so the window shows something like the real view.
hidden_from_camera(box(-3, 5, -0.4, -0.3, D + T, D + 8, M["grass"], "lawn", bevel=0))

# Closet with mirrored sliding doors on its front (z = DM).
for x0, x1 in ((1.85, 2.585), (2.595, W)):
    box(x0, x1, 0.04, 2.0, DM - 0.012, DM - 0.002, M["mirror"], "mirror", bevel=0)
    box(x0, x1, 0.02, 0.04, DM - 0.016, DM, M["mirror_frame"], "mirror_track", bevel=0.001)
    box(x0, x1, 2.0, 2.03, DM - 0.016, DM, M["mirror_frame"], "mirror_track", bevel=0.001)

# ---- heat/AC unit under the window ----
box(0.35, 1.35, 0.28, 0.72, D - 0.24, D, M["ptac"], "ptac", bevel=0.01)
for i in range(18):
    x = 0.47 + i * 0.043
    box(x, x + 0.022, 0.718, 0.724, D - 0.19, D - 0.07, M["ptac_grille"], "ptac_slat", bevel=0)

# ---- desk, monitor, keyboard, PC ----
for lx, lz in ((0.02, 2.5), (0.48, 2.5), (0.02, 1.62), (0.48, 1.62)):
    box(lx, lx + 0.05, 0, 0.68, lz, lz + 0.05, M["desk_leg"], "desk_leg")
box(0, 0.55, 0.68, 0.76, 1.605, 2.565, M["desk_top"], "desk_top", bevel=0.006)
box(0.30, 0.37, 0.76, 0.785, 2.36, 2.42, M["white_plastic"], "mouse", bevel=0.01)
box(0.28, 0.42, 0.76, 0.778, 1.88, 2.26, M["white_plastic"], "keyboard", bevel=0.004)
box(0.10, 0.135, 0.9, 1.28, 1.74, 2.36, M["black_matte"], "monitor", bevel=0.004)
box(0.135, 0.137, 0.915, 1.265, 1.755, 2.345, M["screen"], "screen", bevel=0)
cylinder((0.07, 0.76, 1.68), (0.07, 1.14, 1.68), 0.018, mat=M["black_metal"], name="monitor_post")
cylinder((0.05, 1.12, 1.68), (0.10, 1.09, 2.05), 0.012, mat=M["black_metal"], name="monitor_arm")
box(0.05, 0.47, 0, 0.38, 2.585, 2.855, M["white_plastic"], "pc", bevel=0.008)
box(0.09, 0.43, 0.05, 0.33, 2.583, 2.586, M["pc_glass"], "pc_glass", bevel=0)

# ---- bed ----
box(1.80, 3.30, 0.12, 0.34, 0.065, 2.035, M["bed_frame"], "bed_base", bevel=0.02)
for (x, z) in ((1.84, 0.1), (3.22, 0.1), (1.84, 1.95), (3.22, 1.95)):
    box(x, x + 0.04, 0, 0.12, z, z + 0.04, M["black_matte"], "bed_foot")
duvet = box(1.80, 3.30, 0.34, 0.72, 0.065, 2.035, M["duvet"], "mattress", bevel=0.05)
for i in range(int(1.5 / 0.075)):
    x = 1.85 + i * 0.075
    box(x, x + 0.012, 0.719, 0.723, 0.1, 2.0, M["stripe"], "stripe", bevel=0)
for px in (1.9, 2.6):
    p = box(px, px + 0.6, 0.72, 0.85, 0.12, 0.52, M["pillow"], "pillow", bevel=0.06)
box(1.80, 3.30, 0.12, 1.1, 0, 0.065, M["headboard"], "headboard", bevel=0.02)

# ---- dresser with the little lamp and the sword stand ----
box(0.80, 1.77, 0, 0.95, 0, 0.435, M["dresser"], "dresser", bevel=0.006)
for y in (0.32, 0.635):
    box(0.80, 1.77, y - 0.004, y + 0.004, 0.433, 0.437, M["black_matte"], "drawer_gap", bevel=0)
box(1.284, 1.287, 0.02, 0.93, 0.433, 0.437, M["black_matte"], "drawer_gap", bevel=0)
box(0.88, 0.98, 0.95, 1.04, 0.28, 0.38, M["white_plastic"], "white_box", bevel=0.004)
box(0.98, 1.60, 0.95, 0.975, 0.03, 0.13, M["black_matte"], "sword_base")
for x in (1.0, 1.55):
    box(x, x + 0.03, 0.975, 1.27, 0.06, 0.10, M["black_matte"], "sword_post")
for y in (1.08, 1.21):
    cylinder((0.86, y, 0.08), (1.72, y + 0.02, 0.08), 0.009, mat=M["sword_blade"], name="sword")
    cylinder((1.06, y - 0.03, 0.08), (1.06, y + 0.04, 0.08), 0.012, mat=M["gold"], name="guard")

# STORSEGEL table lamp ("little"): three ash legs and a white linen drum.
cx, y0, cz = MINI
for a in (0.5, 2.6, 4.7):
    cylinder((cx + 0.09 * math.cos(a), y0, cz + 0.09 * math.sin(a)), (cx + 0.025 * math.cos(a), y0 + 0.17, cz + 0.025 * math.sin(a)), 0.009, mat=M["ash"], name="storsegel_leg", verts=12)
cylinder((cx, y0 + 0.13, cz), (cx, y0 + 0.30, cz), 0.088, mat=M["linen"], name="storsegel_shade", verts=64, cap=False)
little_bulb = cylinder((cx, y0 + 0.17, cz), (cx, y0 + 0.24, cz), 0.022, mat=M["frost"], name="little_bulb", verts=24)

# FORSÅ work lamp ("pixar"): weighted base, two arms, nickel dome aimed at the window.
base, elbow = (0.24, 0.028, 3.06), (0.24, 0.38, 2.94)
cylinder((0.24, 0, 3.06), base, 0.078, 0.07, mat=M["nickel"], name="forsa_base", verts=48)
for a, b in ((base, elbow), (elbow, JOINT)):
    cylinder(a, b, 0.007, mat=M["nickel"], name="forsa_arm", verts=12)
    cylinder(tuple(c + 0.012 for c in a), tuple(c + 0.012 for c in b), 0.003, mat=M["nickel"], name="forsa_spring", verts=8)
for j in (elbow, JOINT):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.014, location=B(*j)); o = bpy.context.active_object; o.data.materials.append(M["nickel"]); bpy.ops.object.shade_smooth(); link(o)
dome0 = tuple(j + d * 0.02 for j, d in zip(JOINT, AIMDIR)); dome1 = tuple(j + d * 0.17 for j, d in zip(JOINT, AIMDIR))
cylinder(dome0, dome1, 0.032, 0.075, mat=M["nickel"], name="forsa_shade", verts=64, cap=False)
shell = bpy.context.active_object
shell.modifiers.new("solid", "SOLIDIFY").thickness = 0.0015
pixar_bulb = bpy.ops.mesh.primitive_uv_sphere_add(radius=0.03, location=B(*tuple(j + d * 0.1 for j, d in zip(JOINT, AIMDIR))))
pixar_bulb = link(bpy.context.active_object); pixar_bulb.name = "pixar_bulb"; pixar_bulb.data.materials.append(M["frost"])

# ---- posters on the bed wall ----
px = W - 0.002
for pz, upper, lower in ((2.305, "art_teal", "art_teal"), (1.425, "art_yellow", "art_green"), (0.555, "art_navy", "art_navy")):
    box(px - 0.025, px, 1.14, 2.05, pz - 0.305, pz + 0.305, M["frame_wood"], "poster_frame", bevel=0.003)
    box(px - 0.027, px - 0.025, 1.17, 2.02, pz - 0.275, pz + 0.275, M["mat_paper"], "poster_mat", bevel=0)
    if upper == lower:
        box(px - 0.029, px - 0.027, 1.24, 1.95, pz - 0.205, pz + 0.205, M[upper], "poster_art", bevel=0)
    else:
        # diagonal split: one triangle each colour
        for mat, tri in ((M[upper], ((1.95, pz + 0.205), (1.95, pz - 0.205), (1.24, pz + 0.205))), (M[lower], ((1.95, pz - 0.205), (1.24, pz - 0.205), (1.24, pz + 0.205)))):
            mesh = bpy.data.meshes.new("poster_tri")
            mesh.from_pydata([B(px - 0.029, y, z) for y, z in tri], [], [(0, 1, 2)])
            o = bpy.data.objects.new("poster_tri", mesh); C_ROOM.objects.link(o); o.data.materials.append(mat)

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
