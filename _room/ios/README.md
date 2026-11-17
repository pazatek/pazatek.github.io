# Room: iPhone Live Activity

A small native app whose only job is a Live Activity: the room's readings on the lock screen and in the Dynamic Island,
pushed by the `room` function about once a minute while Piotr is home and awake. A home screen widget can't do this,
because iOS refreshes those at most every 15 to 60 minutes.

## How it works

1. The app hands ActivityKit's push tokens to the `room` function (`action: live_token`), which stores them in `room_live`:
   - `start`: the push-to-start token, so the server can start an activity while the app is closed.
   - one row per running activity, holding its update token.
2. Every minute `room-tick` runs `live()` in `functions/room.ts`:
   - Home (`lights_presence` 'me' = home) and nothing running: it sends a push-to-start, at most once every 15 minutes.
   - Running: it pushes new readings when they change, and at least every 5 minutes. High priority goes out at most every 2 minutes or when the advice changes; the rest go at low priority.
   - Presence changes to asleep or away: it ends the activity. It does the same after 7¾ hours (iOS's limit is 8) and then starts a fresh one.
3. `liveState()` builds the content. Its keys must match `RoomAttributes.ContentState`. The app shows the same thing (`action: live_state`) and has Start now / End buttons.

## Files

- `App/`: the app (the token hand-off is in `Live.swift`; the room key is in the Keychain).
- `Widget/`: the Live Activity's views.
- `Shared/`: the attributes and views both targets compile.
- `Config/`: Info.plists and entitlements.
- `gen_project.py` writes `RoomCoach.xcodeproj`. Rerun it after adding or removing a `.swift` file.

## Needs

- The paid Apple Developer Program. Push notifications don't work with a free Apple ID.
- A current Xcode on the Mac. Xcode 15.4 has no iOS platform installed and can't target the phone.
- An APNs key (.p8) from developer.apple.com → Keys, stored as `room` function secrets: `APNS_KEY_P8` (the file's text), `APNS_KEY_ID` and `APNS_TEAM_ID`. Never commit it.
- The `room_live` table (see below) and the updated `room` function deployed.

```sql
create table public.room_live (
  id text primary key,                       -- 'start', 'apns_jwt', or an activity id
  kind text not null check (kind in ('start', 'update', 'jwt')),
  token text not null,
  env text not null default 'sandbox' check (env in ('sandbox', 'production')),
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  last_state jsonb,
  last_push timestamptz,
  last_hi timestamptz,
  updated_at timestamptz not null default now()
);
alter table public.room_live enable row level security;  -- no policies: only the service role reads it
```

## Build and install (on the Mac)

    python3 gen_project.py
    xcodebuild -project RoomCoach.xcodeproj -scheme RoomCoach -destination 'platform=iOS,name=<phone>' -allowProvisioningUpdates DEVELOPMENT_TEAM=<team id> build
    xcrun devicectl device install app --device <phone id> build/.../RoomCoach.app

Debug builds register as `sandbox`, so the server pushes through APNs' sandbox host. The first time, paste the room key into the app.

## Checked so far

- Both targets type-check against the iOS 17.5 SDK.
- The JWT signing code produces a valid ES256 token (tested in Node).
- Not built for a device yet, and no push has been sent. The server part is in `functions/room.ts` but not deployed.
