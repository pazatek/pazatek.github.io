# Handoff, Nov 13 2026 (evening)

Context from the long chat this project was built in, beyond what `README.md` covers. Piotr's working preferences are in his Claude memory; the short version: short direct answers, no em dashes, no unsolicited tangents, formulas in one plain-English line, short but not clipped.

## Tonight, live

- His roommate is having a party. Bedroom CO2 peaked at 3,609 ppm at 8:49 pm and fell to 2,303 by 8:58 with the window wide and two orb fans blowing in.
- At 8:58 he carried the CO2 reader to the living room. It is on battery there, and on battery that model (SwitchBot Meter Pro CO2) samples CO2 only every 30 minutes, fixed. Until he presses the button on top of it or plugs it into USB, the stored CO2 value is still the bedroom's 2,303. He asked how long until the living room reaches 1,000 ppm and has no answer yet: get two or three living room readings from `air_readings`, then estimate.
- Setup he was advised on: bedroom door open, living room window cracked about 3 inches as the exit, fans at the bedroom window pushing in. He then asked about closing his door; advice was a quarter-open bedroom window with the fan off, and to open the living room window wider with a fan there.
- The outdoor weather feed was stale for about 100 minutes earlier in the evening and then recovered. Not investigated.

## Shipped today

- 3D view: squirrel and grass only through the window, airflow as a sheet falling from the window gap, trend arrows on the readings, PC (white Lian Li O11 Dynamic Mini), IKEA STORSEGEL lamp, two swords on a black stand on the wall side of the drawer, CO2 reader on the drawer's front-left corner turned 45 degrees (it points at the camera, so it shows as a sliver), smaller Pixar lamp with a round base, room view nearly edge to edge.
- Desk chair: Uplift's Pursuit model at full detail, colors from a low-poly 3MF Piotr supplied (white frame, charcoal mesh back and headrest, blue-grey seat).
- "Xs ago / Xm ago" under each reading. It counts from when the value last changed (`room_snapshot().since`, helper `room_value_since`), because the poll stores a row every 30 s regardless. Verified with sample data only, not yet seen on the home screen app with live data. Piotr read "8m ago" as stale data; if that keeps confusing him, consider wording or showing the poll time as well.
- Awake comfort band 70 to 73°F. Blind control through Tuya with Up / Half / Down / Auto in the app.

## Night blind controller

- An overnight test (window at a quarter, about 37°F outside) showed blind up settles near 64 to 65.5°F and 470 to 500 ppm, blind down near 68°F and 770 ppm; the blind cuts airflow by roughly 80%.
- `steer()` in the `room` function runs each minute after dark and uses the learned model in `functions/model.ts` (deployed alongside as `model.ts`): a first-order room, dT/dt = c − h·T − (gU·(1−p) + gD·p)·(T − out) + w·watts/100, fitted by ridge regression toward a prior (the 2026-11-13 measurement) on 10 minute buckets of `room_log` (one row per tick, via `room_fit_rows()`), 7 day half-life, h pinned to fix the scale, plus "step" rows from each blind move (the change in warming rate across a move) which are what teach it how strong the blind is. A bias (its recent miss, 2 h window, 30 min half-life) covers tonight's differences. It puts the blind where the room SETTLES at the aim, moves only if that settling point at the current height is 0.5°F or more off, by at least 10%, at most once per 20 minutes (`room_blind.steered_at`). CO2 at or above 1,000 forces it up by 10. Each decision is written to `room_model` (theta, sample counts, bias, settle_now, ideal_pct). `tests/model_sim.js` simulates 7 nights: old jump controller 11 to 21 moves a night mostly reversals; this one 4 to 5 with about 1. A manual blind command sets a 2 hour hold. In sleep mode it drops the blind fully at daylight, once.
- The app's Awake / Sleeping / Away switch now writes `lights_presence` (person me) through `POST {action:mode}` on the `room` function, and the app follows that row on every refresh. Before 2026-11-15 the switch only lived in the phone, so the server could steer for "awake" while the app said Sleeping.
- No real night has been reviewed yet. Two defaults he may want changed: the sunrise drop, and steering also running in awake mode after dark.

## Lamps

- Two Govee H600B lamps, "Pixar" (arm lamp) and "Little Lamp" (IKEA-style). He wants taps in the 3D view to switch them as close to instantly as possible. Plan: a matter.js controller on his Windows gaming PC, listening on the `room-lights` realtime channel (`lamp-relay-handoff.md`). Not built. He needs to hand that file plus `relay.env` (sent to him in chat, never commit it) to a Claude session on the gaming PC and generate a fresh Matter pairing code for each lamp.

## Thermal camera

- Goal: a cheap thermal camera so Claude can see the room. Budget target $50. Simulations put the best spot above the drawer facing the window, and the 55° lens ahead of the 110° one.
- Options found: bare MLX90640 BAA chip (110°) on eBay, $23 + $6, no returns, his ECE friend would solder (his stated choice, listing 146290720327); MLX90640 BAB module (55°) on eBay, $37.99; Waveshare 80×62 ESP32-S3 module, $86.99; Topdon TC001, about $180. An ESP32 board ($8.99) is in his Amazon guest cart. Nothing bought. After purchase: firmware and Supabase ingestion.

## Things that were refused or failed, so don't be surprised

- A `blind-poll` cron job was blocked by a permission rule, so the blind position only refreshes while the app is open. Needs his explicit go-ahead.
- Uplift's SketchUp file arrived corrupted in chat; the STL export worked. The vendor files are not in the repo.
- SwitchBot and Tuya credentials are entered by Piotr into Supabase secrets himself. Don't ask him to paste them into chat.
