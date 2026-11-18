"""Encodes the linear EXR light layers for the app: one 8-bit sRGB WebP per layer, scaled so its brightest 0.3% just fits,
plus alpha.png (the room's silhouette) and layers.json with each layer's scale. The app decodes, multiplies back by the scale,
sums the layers with each lamp's live colour and brightness, then tone-maps (AgX, like Blender's view)."""
import json
import os
import sys

import bpy
import numpy as np

d = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
meta = {"layers": {}}
alpha = None
for name in ("day", "pixar", "little", "fan", "fill"):
    src = os.path.join(d, name + ".exr")
    if not os.path.exists(src):
        continue
    img = bpy.data.images.load(src)
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    rgb, a = px[..., :3], px[..., 3]
    if alpha is None:
        alpha = a
    lit = rgb.max(axis=2)[a > 0.5]
    scale = float(np.percentile(lit, 99.7)) if lit.size else 1.0
    scale = scale if scale > 1e-6 else 1.0
    enc = np.clip(rgb / scale, 0, 1)
    enc = np.where(enc <= 0.0031308, enc * 12.92, 1.055 * np.power(enc, 1 / 2.4) - 0.055)
    out = bpy.data.images.new(name + "_web", w, h, alpha=False)
    out.pixels = np.concatenate([enc, np.ones((h, w, 1), np.float32)], axis=2).ravel()
    out.file_format = "WEBP"
    out.save(filepath=os.path.join(d, name + ".webp"), quality=88)
    meta["layers"][name] = {"scale": scale}
    print("layer", name, w, h, "scale", round(scale, 4))
if alpha is not None:
    h, w = alpha.shape
    m = bpy.data.images.new("alpha_web", w, h, alpha=False)
    m.pixels = np.repeat(np.clip(alpha, 0, 1)[..., None], 4, axis=2).ravel()
    m.file_format = "PNG"
    m.save(filepath=os.path.join(d, "alpha.png"))
cam = os.path.join(d, "camera.json")
if os.path.exists(cam):
    meta["camera"] = json.load(open(cam))
json.dump(meta, open(os.path.join(d, "layers.json"), "w"), indent=1)
print("ENCODED", d)
