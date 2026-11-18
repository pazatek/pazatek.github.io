# Lamp relay

Runs on the always-on PC from `C:\Users\richa\room-lights-relay` (this folder is a copy of its source; `node_modules`,
`.matter`, `relay.env` and the logs stay on the PC). It holds the two Govee H600B bulbs as a second Matter admin and takes
commands from the Room Coach app over the Supabase Realtime channel `room-lights`:

    phone --websocket--> Supabase Realtime --websocket--> relay.mjs --Matter, local Wi-Fi--> bulb

## Contract

- `cmd` (app to relay): `{ lamp, on?, brightness? 1-100, k? 2700-6500, hue? 0-360, sat? 0-100, t, sig }`.
  - `sig` is HMAC-SHA256 with the room app key over `lamp|on|brightness|k|hue|sat|t`, with a missing field written as an empty string.
  - The relay drops a command whose signature is wrong or whose `t` is more than 10 s off the PC's clock.
- `state` (relay to app), sent on every change and in reply to `hello`: `{ lamp, on, brightness, k, hue, sat, mode: "ct"|"hs", online, t }`.
- Presence `{ relay: true }` while connected. The app has to join with `presence: { enabled: true }` or Realtime never sends it.
- One command per lamp is in flight at a time. While it runs, newer ones replace each other, and the app sends at most every 120 ms while a slider is dragged.

## Files

- `relay.mjs`: the service. It logs to `relay.log` (rotates at 5 MB).
- `pair.mjs <pixar|little> <code> [ip]`: commissions a bulb.
  - The bulb has to be in pairing mode from the home app it's already in; a code alone isn't enough.
  - Pass its IP if discovery misses it. `browse.mjs` lists Matter devices and shows which one is open to pairing; `srv.mjs <instance>` resolves its address.
- `lamp.mjs <name> on|off|toggle`: quick test, prints the round trip.
- `test_cmd.mjs '<json>'`: sends a signed command the way the app does, using the first key in `relay.env`.
- `run.cmd` restarts the relay 5 s after any exit. `start-hidden.vbs` runs that with no window, and a shortcut to it in the Startup folder starts it at login.
- `relay.env`: `ROOM_KEYS=<key>[,<key>...]`, the keys commands may be signed with. Never commit or print it.

## State (2026-11-17)

- pixar: node 1, at 192.168.50.50. Each command takes 200-350 ms for the bulb to acknowledge.
- little: not paired yet.
