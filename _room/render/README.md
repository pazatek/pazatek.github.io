# Photoreal room (in progress)

`build_scene.py` rebuilds the bedroom in Blender from the coordinates in `core.js` and renders it with Cycles. It uses the
app's own orthographic isometric camera, so a render lines up pixel for pixel with what the app draws.

    scp build_scene.py chair.obj mac:room-render/
    ssh mac 'cd ~/room-render && /Applications/Blender.app/Contents/MacOS/Blender -b -P build_scene.py -- --out out/x.png --samples 128 --width 1100 [--night] [--layer all|day|pixar|little|fan|fill]'

- `chair.obj` is the Uplift Pursuit mesh from `core.js` (`CHAIR`), already in Blender axes.
- Modelled from the product pages: Hampton Bay Mena 44" fan, IKEA FORSÅ (pixar), IKEA STORSEGEL (little).
- Each light renders on its own (`--layer`). Light adds up, so the app can rebuild any lamp colour and brightness by
  summing the layers in a shader, each scaled by its lamp's live RGB. That part isn't built yet.
- Timing: about 3-5 minutes per 1100 px frame at 128 samples on the M3 Pro.

Still to model from photos: the real floor, wall colour, bedding, dresser, desk, PC, blind, posters, door.
