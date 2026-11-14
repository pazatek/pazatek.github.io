# Lamp relay for Room Coach: handoff for the Claude session on the gaming PC

Goal: tapping a lamp in the Room Coach web app switches the real bulb with as little delay as possible.
The bulbs are two Govee H600B (Matter over Wi-Fi) in Piotr's bedroom. This PC is always on and on the same
network, so it runs a small relay: it holds the bulbs as a Matter controller and listens for commands on a
Supabase Realtime channel. No cloud lighting API is in the path.

    phone (web app) --websocket--> Supabase Realtime --websocket--> relay on this PC --Matter, local Wi-Fi--> bulb

## What to build

A Node.js (20+) service, running natively on Windows (not WSL or Docker: Matter needs mDNS and IPv6 multicast
on the real LAN interface).

1. Matter controller using matter.js (https://github.com/matter-js/matter.js, the controller example in
   the repo is the starting point). Commission each bulb on-network with its manual pairing code. Piotr
   gets a code per bulb from the Govee Home app (device settings, Matter). A code may only be valid for a
   few minutes after the app shows it, so ask him for a fresh one right when you're ready to commission.
   Persist the fabric to a local folder so a restart doesn't need re-pairing. This is a second Matter admin;
   it must not remove the bulbs from the Govee app.
   Name the two nodes `pixar` (the silver arm lamp by the window) and `little` (the small tripod lamp on the
   wooden unit by the bed).
2. Keep a live subscription to each bulb's OnOff, LevelControl and ColorControl (colour temperature) state.
3. Supabase Realtime client (`@supabase/supabase-js`):
   - URL `https://hxaftcofwrffwjxtjeoj.supabase.co`
   - publishable key `sb_publishable_4TJE66VMSen-hl22kWL-Rw_8RXH_UOH` (public by design)
   - channel `room-lights`, broadcast with `self: false`, plus presence.
4. Start at login, single instance, restart on crash, log to a file. Same pattern as the PC heat logger.

## Message contract (fixed; the web app is built against this)

Broadcast event `cmd`, sent by the web app:

    { "lamp": "pixar" | "little", "on": true|false (optional), "brightness": 1..100 (optional),
      "k": 2700..6500 (optional), "t": <epoch milliseconds>, "sig": "<hex>" }

`sig` = HMAC-SHA256, key = ROOM_KEY (UTF-8), message = `lamp|on|brightness|k|t` with a missing field written
as an empty string, booleans as `true`/`false`. Example message: `pixar|true|||1794554000000`.
Reject a command when the signature is wrong or when `t` is more than 10 seconds from this PC's clock.
The channel is public, so the signature is the only thing that makes a command trusted. Compare in
constant time.

On a valid command, act immediately with zero transition time:
- `on` -> OnOff On / Off
- `brightness` -> LevelControl MoveToLevelWithOnOff, level = round(brightness * 2.54), transition 0
- `k` -> ColorControl MoveToColorTemperature, mireds = round(1000000 / k), transition 0

Broadcast event `state`, sent by the relay whenever a bulb's state changes (from any source) and in reply
to a `hello` event from the web app:

    { "lamp": "pixar" | "little", "on": bool, "brightness": 1..100, "k": number|null, "online": bool, "t": <epoch ms> }

Presence: track `{ "relay": true }` on the channel while connected, so the app knows the fast path is up.

## ROOM_KEY

The relay reads ROOM_KEY from a local `relay.env` next to the script (never committed, never printed in
logs or chat). It is the same private key the Room Coach home screen app uses. Piotr provides the file.

## Good to know

- A separate scheduler (`lights` edge function) drives these bulbs through Govee's cloud on a 30 second
  tick. It already treats any change it didn't make as a manual override and goes hands-off for a while,
  so the relay doesn't need to coordinate with it.
- Windows Firewall must allow the Node process UDP in/out on the private network (mDNS 5353 and Matter 5540),
  and IPv6 must be enabled on the adapter.
- If on-network commissioning can't find a bulb, it probably isn't in pairing mode: get a fresh code from the
  Govee app and retry within its window.

## Report back

When it's running, tell Piotr: both lamps commissioned (yes/no), measured time from receiving a `cmd` to the
bulb acknowledging it, and how the service is started at login.
