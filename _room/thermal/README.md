# Thermal camera

A Waveshare **Thermal-90 USB Camera (B)** (80×62 pixels, 90°×67°, ±1.5 °C, USB-C) hangs on the left wall (as you walk in) 85 cm from the window corner, right above the PC, and plugs
into the PC, which is always on. A small Python program on the PC reads it, works out the temperature of each surface it can
see, and sends a one-minute summary to Supabase through the `room` edge function.

Not bought yet as of 2026-11-16. Everything below is built and tested with a fake camera; the steps marked *on arrival* still
need the real one.

## What it measures

Thermometers measure air; the camera measures surfaces. What it adds:

| Column (°C) | What it is |
|---|---|
| `window_c` | Skipped for now: it sees the glass at about 50°, where glass reflects a lot of the room. Turn on once real frames show it's usable |
| `pc_c` | The PC case (its power draw is already logged in `pc_power`); in `stats` only |
| `unit_c`, `unit_state`, `unit_leak` | The heat/AC unit under the window: heating, cooling or off, and whether it's off but letting cold air through |
| `walls_c` | Median of the walls, closet and ceiling: what your body radiates to, which is a big part of how warm the room feels |
| `floor_c`, `floor_min_c` | Floor, and its coldest 5% |
| `bed_c`, `head_c`, `in_bed` | The bed, its warmest spot, and whether you're in it |
| `people_px` | Pixels at body temperature outside the PC, unit and lamps |

Rows go into `public.room_thermal` (schema in `schema.sql`), one a minute; every 15 minutes the row also carries the whole frame
(`frame.dc_i16_b64`: little-endian int16 tenths of a °C, 62 rows of 80). Whole frames are dropped after 30 days.

## Pieces

- `room_scene.py`: the room as labelled boxes (same layout as the room view). Ray-traces every camera pixel to the surface it
  sees, so the program knows which pixels are window, unit, bed and so on. Also makes fake frames for testing.
- `thermal_agent.py`: the program. Averages about two frames a second over each minute (that cuts the noise about 10×),
  corrects every pixel for its surface's emissivity, applies the calibration, and posts. See its docstring for flags.
- `mount/mount.py` → `mount/above_pc_mount.stl`: the 3D-printed mount, all flat faces, about 12 g, 42 × 27 × 40 mm. It
  holds the camera on the desk wall 85 cm from the window corner, above the PC, aimed toward the bed side and 55° down.
  - **Camera:** it pushes in from the front and clicks under two angled catches along its front edges. Waveshare's photos
    show the USB-C plug coming out of a long side near one end (the lens sits toward the other end), so the plug goes
    through a slot in the bottom rail. `LENS_X`, `PLUG_X`, `PLUG_Z` and the `CAM_*` sizes are read off photos: measure.
  - **Cable:** a 90° USB-C adapter (male-to-female, the L-shaped kind) goes on the plug and turns the cable to run along
    the wall, out the window-side end of the mount, through a bay cut into the wedge. A USB-C female-to-male (or
    female-to-USB-A) extension plugs onto the adapter and drops down the wall to the PC, below and behind the camera's view.
  - **Strip:** one 3M Command Adjustables Mini refill strip, the near-square one (1.03" × 1.32", rated 0.5 lb / 227 g).
    The 28 × 26.5 mm plate covers only the sticky part; the pull tab (assumed about 8 mm, check it) hangs free below.
  - **Gravity:** the camera sits as close to the wall as its view and the adapter bay allow: its weight is about 25 mm
    out, a peel load of about 8 N·mm. About 50 g with the cable's share on a 227 g strip, roughly a 4.5× margin.
  - **Printing:** no supports. `best_up()` tries every flat face as the bed face; the best is standing on the mount's
    flat top edge (plate top and cradle top are flush): no bridges, about 30 mm² past 45°, 980 mm² of first layer.
    PETG or PLA, 0.2 mm layers, 4 walls, 15% gyroid infill. The camera's view (90° × 67° plus 3°) is cut out of the part.
- `install.ps1`: copies the program to `%USERPROFILE%\room-thermal`, makes a venv with `pysenxor-lite` (Meridian's library for
  this sensor), and adds the scheduled task "Room thermal camera" (starts at logon, restarts if it stops).
- Edge function `room`, action `thermal`: accepts only the key labelled `thermal camera` in `room_keys`. That key lives only
  in `%USERPROFILE%\room-thermal\thermal.env` on the PC (never commit it).

## Calibration

1. **Per surface.** The camera is set to emissivity 1.0, so it reports what a perfect black surface would. The program then
   corrects each pixel with its own surface's emissivity (glass 0.84 at this angle, paint 0.94, bedding 0.95, skin 0.98...)
   and the room's reflected temperature (the median wall). Values are in `room_scene.EMISSIVITY`.
2. **Against the thermometer.** Black electrical tape on a piece of card (about 15×15 cm), hung in free air within 10 cm of the
   desk thermometer (Outdoor Meter 53), where the camera can see it. A card in free air sits at air temperature, which a wall
   doesn't. Every steady minute the program pairs the card's reading with the thermometer's and fits `true = a·reading + b`
   over the last week (two-day half-life). It fits just the offset until the room has swung at least 2 °C, then the gain too.
   The fit lives in `calib.json` and goes out with every row (`stats.cal`). In a simulated day it recovered a 3% gain error
   and a 0.9 °C offset to within 0.01 °C.

## On arrival

1. Measure the camera (Waveshare lists 32 × 18.5 mm; thickness unknown) and which end the USB-C plug comes out of. Fix `CAM_*`
   and the lens and plug positions (`LENS_X`, `PLUG_X`, `PLUG_Z`) in `mount/mount.py`, run it, and print
   `above_pc_mount.stl` as described above.
2. Stick it on the desk wall 85 cm from the window corner (above the PC) with Command strips, top about 2.23 m up. A short USB-C cable reaches the PC below.
3. `powershell -ExecutionPolicy Bypass -File install.ps1`
4. Hang the reference card by the desk thermometer, then from `%USERPROFILE%\room-thermal`:
   `venv\Scripts\python thermal_agent.py --find-card` and hold a warm hand right behind the card for 20 seconds.
5. `venv\Scripts\python thermal_agent.py --once --dry-run --snapshot snap.png`, then have Claude look at `snap.png`. The white
   outlines are where the program thinks each surface is; if they're off, nudge `pose` (yaw, tilt, roll, flip_h, flip_v) in
   `config.json`.
6. After the first day, check `select * from room_thermal order by ts desc limit 20` and the `stats.cal` numbers.

## Not done yet

- The blind controller and the room view don't use these numbers yet. Next step once there's a week of data: feed `walls_c`
  and `window_c` into the model, and show the camera in the app.
