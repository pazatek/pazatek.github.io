# Photoreal room (in progress)

`build_scene.py` rebuilds the bedroom in Blender from the coordinates in `core.js` and renders it with Cycles. It uses the
app's own orthographic isometric camera, so a render lines up pixel for pixel with what the app draws.

    scp build_scene.py chair.obj mac:room-render/
    ssh mac 'cd ~/room-render && /Applications/Blender.app/Contents/MacOS/Blender -b -P build_scene.py -- --out out/x.png --samples 128 --width 1100 [--night] [--layer all|day|pixar|little|fan|fill]'

- `chair.obj` is the Uplift Pursuit mesh from `core.js` (`CHAIR`), already in Blender axes.
- Modelled from the product pages: Hampton Bay Mena 44" fan, IKEA FORSÅ (pixar), IKEA STORSEGEL (little).
- Each light renders on its own (`--layer`), in white light. Light adds up, so the app rebuilds any lamp colour and
  brightness by summing the layers.

## In the app

    ssh mac 'cd ~/room-render && ./render_layers.sh 1400 160'      # about 35 min: day, pixar, little, fan, fill (EXR), then encode_layers.py
    scp 'mac:room-render/out/layers/{*.webp,alpha.png,layers.json}' ../../room/photo/

- `encode_layers.py` writes one 8-bit sRGB WebP per layer, scaled so its brightest 0.3% fits (the scale is in `layers.json`).
  It also writes `alpha.png` (the room's silhouette) and `camera.json`, the image positions of known room points.
- `core.js` (`photo`) loads them only on the home screen app (`PHOTO_BASE`). It sums the layers in WebGL, then tone-maps.
  - The sum is `day * sun + pixar * rgb * brightness + little * rgb * brightness + fill`.
  - The lamp RGB comes from the relay state (`lampRGB`: Kelvin, or hue/sat for colour mode). The daylight weight is the outdoor `sun_wm2` / 250.
  - Tone mapping is an AgX fit, like Blender's view.
  - The camera points give the scale and offset that line the image up with the app's own projection, so lamp taps, the lamp card, airflow and the door overlay still land in the right place.
  - The drawn room stays for the apartment view and as the fallback when WebGL or the images aren't there.
- Fixed in the render (not live yet): the blind at 60%, the window closed, the fan's blades standing still (the app lays a blur disc over them while the fan runs).

## Scene notes

- Cut-away: the walls nearest the camera, and the ceiling, are hidden from the camera but still block and bounce light.
  Their tops and cut ends ("caps") get their own linked light, as in the app's drawing.
- The headboard and dresser stand against the cut-away door wall. A linked fill light shows their backs.
  - A light-linking blocker collection must not be empty: Blender then treats everything as a blocker. It holds one far-away cube.
- All glass casts no shadow. Light through glass is a caustic, which is off, so otherwise the sun and lamps would stop at every pane.
- Posters: Piotr's three 20 x 28 in prints (Downloads/poster-upscale/out/print_20x28), cropped to the mat window.
  - Frames: IKEA RÖDALM 61 x 91 cm, birch effect. 63 x 93 cm outside, 3 cm deep, mat opening 49 x 69 cm.
  - The crops (`tex/poster_*.jpg`) aren't committed (copyrighted art). Rebuild them from the print files.
- Floor: three planks cut from Piotr's floor photo (`tex/floor_planks.jpg`), white-balanced. Each strip of floor picks one of them at a random offset.
