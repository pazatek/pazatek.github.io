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
- `mount/mount.py` → `mount/above_pc_mount.stl`: the 3D-printed mount, all flat faces with every outside edge chamfered
  (1 mm at 45°, no edge sharper than 80°), about 16 g, 50 × 27 × 40 mm. It holds the camera on the desk wall 85 cm from
  the window corner, above the PC, aimed toward the bed side and 55° down. The STL is already turned the way it prints,
  with three shims laid beside it, so it drops straight onto the bed.
  - **Camera:** sizes from Waveshare's outline drawing for the (B) USB camera: body 32.0 × 18.5 mm, lens centre 8.2 mm
    from one end (barrel 9.2 mm, sticks out about 3 mm on the 90°), and a rigid male USB-C plug out of the bottom long
    side, centred 18.75 mm from the lens end and 9.75 mm long. The camera pushes in from the front and clicks under four
    angled catches (1 mm over its front edges).
  - **Thickness:** not published anywhere (photos say about 10 mm, one reseller lists 12 mm with the lens). So the pocket
    is 12 mm deep and the shims (0.5, 1 and 2 mm) go behind the camera to fill the rest: stack whichever fit snug. Works
    for any body from 8.5 to 12 mm.
  - **Cable:** straight out of the bottom. A plain USB-C extension cable (female end onto the camera, USB-A or USB-C male
    into the PC) plugs straight onto the plug; its female end sits in a slot open from the pocket floor to the front (room
    for one up to about 13 × 7.5 mm and 22 mm long, at any depth the plug turns out to be), and the cable bends down
    along the wall right under the mount, behind the camera's view.
  - **Strip:** one 3M Command Adjustables Mini refill strip, the near-square one (1.03" × 1.32", rated 0.5 lb / 227 g).
    The 28 × 26.5 mm plate covers only the sticky part; the pull tab (assumed about 8 mm, check it) hangs free below.
  - **Gravity:** the camera's weight is about 33 mm out from the wall, a peel load of about 12 N·mm. About 55 g with the
    cable's share on a 227 g strip, roughly a 4× margin.
  - **Printing:** no supports. It stands on the mount's flat top edge: no bridges, about 50 mm² past 45° (the catch
    ramps), 1,200 mm² of first layer, at least 1.2 mm of wall everywhere. PETG or PLA, 0.2 mm layers, 4 walls, 15% gyroid
    infill. The camera's view (90° × 67° plus 3°) is cut out of the part, checked clear.
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

1. Print `mount/above_pc_mount.stl` as is (it fits any camera thickness from 8.5 to 12 mm). Push the camera in with the
   extension cable already on its plug, and stack shims behind it until it clicks in snug.
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
