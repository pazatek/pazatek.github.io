# Room Coach

Piotr's bedroom air, temperature, blind and lamp app. Two front ends share one core:

- **Home screen app**: `room/index.html`, served by GitHub Pages at piotrzatek.com/room. Talks to the `room` and `blind` Supabase edge functions with the app key (entered once in the app, stored on the phone).
- **Claude artifact**: `artifact.html`, published to https://claude.ai/artifact/X6UQxKJrWEi6AcUYrLSrGM. Reads `select public.room_snapshot() as snap` through the Supabase connector.

GitHub Pages' Jekyll build skips `_`-prefixed folders, so nothing in here is published.

## Build

    cd _room && python3 build.py

`build.py` joins `core.css`, `core.html` and `core.js` with each front end's own code and writes `../room/index.html` and `artifact.html`. The artifact's own code (the model constants, `inputs`, `advise`, the Supabase call) is cut out of the existing `artifact.html`, and the site's out of `site_old.html`, so a change to the model (`K`, `advise`, `inputs`) has to be made in both of those files. Everything visual lives in `core.*`.

## Check

    node tests/room_test.js                      # site: prints the headline state
    node tests/coach_test.js | grep -E "PAGEERROR|overflow"   # artifact: must print "overflow false" and no PAGEERROR
    node tests/full_test.js                      # screenshot of the 3D view
    node tests/age_test.js                       # screenshot with a sample snapshot

The tests need Playwright with Chromium. The page must never scroll; `overflow false` is that check.

## Ship

Commit and push `room/` to `main`, then republish `artifact.html` to the artifact URL above.

## Pieces

- `core.js`: the advice UI, plus `viz`, a Canvas 2D isometric renderer. Layers are baked once per lamp on/off combination. The desk chair is Uplift's Pursuit model (`CHAIR`), drawn with its own depth buffer; `chair/bake.py <stl> <3mf>` regenerates that data from the vendor's files, which are not kept here.
- `functions/room.ts`: source of the `room` edge function (snapshot, advice, push alerts, the night blind controller `steer()`). The `blind` (Tuya), `air` (SwitchBot poll) and `lights` (Govee scheduler, owned by another session, treat as read-only) functions exist only in Supabase; fetch them from there before editing.
- Supabase project `hxaftcofwrffwjxtjeoj`. Tables `air_readings`, `air_outdoor`, `pc_power`, `room_state`, `room_blind`, `room_notify`, `room_push_subs`. `room_snapshot()` is the one read both front ends use. pg_cron jobs: `room-tick` (1 min), `air-poll` and `lights-tick` (30 s).
- `lamp-relay-handoff.md`: plan for the Matter relay on the gaming PC that makes the two lamps tappable with low latency. Not built yet; the app's lamp taps broadcast on the `room-lights` realtime channel and nothing answers.

## Rules that came out of building it

- Secrets (SwitchBot, Tuya, the app key) live in Supabase edge function secrets or on the phone. Never commit or print them. The publishable key in the site code is meant to be public.
- Blind: 0% is fully up, 100% fully down. Speed stays at 20 (40 is too loud, creeping was rejected). The Tuya commands `border`, `control_back` and `reset` stay blocked.
- Comfort bands: awake 70 to 73°F (aim 71.5), sleep 65 to 68°F (aim 66.5).
- Overnight the window stays at a quarter and the blind is the throttle.

## Open

- Tune the night blind controller's step size from its first real nights.
- Blind position only refreshes while the app is open (no background poll job).
- Thermal camera not bought yet; firmware and ingestion to follow.
- Apartment view waits on a higher-resolution scan.
