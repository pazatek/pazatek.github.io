# Lamp relay

Runs on the always-on PC from `C:\Users\richa\room-lights-relay` (this folder is a copy of its source; `node_modules`,
`.matter`, `relay.env` and the logs stay on the PC). It holds the two Govee H600B bulbs as a second Matter admin and takes
commands from the Room Coach app over the Supabase Realtime channel `room-lights`:

    phone --websocket--> Supabase Realtime --websocket--> relay.mjs --Matter, local Wi-Fi--> bulb

## Contract

- `cmd` (app to relay): `{ lamp, on?, brightness? 1-100, k? 2700-6500, hue? 0-360, sat? 0-100, t, sig }`.
  - `exp` and `sig`: the app gets a 12-hour signing key from the `lamp` edge function (`functions/lamp.ts`), which checks its app key: key = HMAC(secret, "lamp|" + exp).
  - `sig` is HMAC-SHA256 with that key over `lamp|on|brightness|k|hue|sat|t`, with a missing field written as an empty string.
  - The relay derives the same key from `exp`. It gets the secret from `lamp?relay=1`, encrypted to its own RSA key (`relay_key.pem`, which stays on the PC), so the secret never sits in a file or crosses the channel in the clear.
  - Commands signed with a key listed in `relay.env` (`ROOM_KEYS`) are also accepted, for tests.
  - The relay drops a command whose signature is wrong or whose `t` is more than 10 s off the PC's clock.
- `state` (relay to app), sent on every change and in reply to `hello`: `{ lamp, on, brightness, k, hue, sat, mode: "ct"|"hs", online, t }`.
- Presence `{ relay: true }` while connected. The app has to join with `presence: { enabled: true }` or Realtime never sends it.
- One command per lamp is in flight at a time. While it runs, newer ones replace each other. The app sends at most every 80 ms while a control is dragged.
- Commands under 400 ms apart fade over 0.2 s (Matter transitionTime 2), so a drag glides; a single tap changes at once. Color and brightness go out together.
- `done` (relay to app) after the bulb acknowledges: `{ lamp, t, total, bulb }`. The app shows tap-to-lamp time as half its round trip minus `total`, plus `bulb`.
- State is read from the subscription cache, not from the bulb: reading the bulb after every command slowed the next one.

## Files

- `relay.mjs`: the service. It logs to `relay.log` (rotates at 5 MB).
- `pair.mjs <pixar|little> <code> [ip]`: commissions a bulb.
  - The bulb has to be in pairing mode from the home app it's already in; a code alone isn't enough.
  - Pass its IP if discovery misses it. `browse.mjs` lists Matter devices and shows which one is open to pairing; `srv.mjs <instance>` resolves its address.
- `lamp.mjs <name> on|off|toggle`: quick test, prints the round trip.
- `bench.mjs [n]`: times n separate taps on pixar's brightness and puts it back.
- `test_exp.mjs '<json>'`: sends a command signed the way the app does (12-hour key). `test_cmd.mjs` signs with the first `ROOM_KEYS` key instead.
- `run.cmd` restarts the relay 5 s after any exit. `start-hidden.vbs` runs that with no window, and a shortcut to it in the Startup folder starts it at login.
- `relay.env`: optional `ROOM_KEYS=<key>[,<key>...]` test keys. Never commit or print it.
- Started at login by `Startup\Room lamp relay.lnk`, which runs `start-hidden.vbs`.

## State (2026-11-17)

- pixar: node 1, at 192.168.50.50.
- Measured 2026-11-17 from the PC (bench.mjs, 10 taps): about 32 ms through Supabase one way and 153 ms for the bulb to acknowledge, so about 185 ms tap to lamp. An occasional 1.7 s outlier is the bulb's Wi-Fi dropping a packet and resending.
- From the phone it was about 100 ms to reach the PC. The PC's clock is about 0.66 s fast, so the log's "sent … ago" reads high by that much.
- little: not paired yet.
