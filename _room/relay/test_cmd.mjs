// Send one signed command like the app does:  node test_cmd.mjs '{"lamp":"pixar","brightness":40}'
// Uses the first key in relay.env; prints what came back on the channel for 3 s.
import { createClient } from "@supabase/supabase-js";
import { createHmac } from "node:crypto";
import { readFileSync } from "node:fs";
const key = readFileSync(new URL("./relay.env", import.meta.url), "utf8").match(/ROOM_KEYS=([^,\r\n]+)/)[1];
const c = JSON.parse(process.argv[2]); c.t = Date.now();
const f = (v) => (v === undefined || v === null ? "" : String(v));
c.sig = createHmac("sha256", key).update([c.lamp, c.on, c.brightness, c.k, c.hue, c.sat, c.t].map(f).join("|")).digest("hex");
const s = createClient("https://hxaftcofwrffwjxtjeoj.supabase.co", "sb_publishable_4TJE66VMSen-hl22kWL-Rw_8RXH_UOH");
const ch = s.channel("room-lights", { config: { broadcast: { self: false } } });
ch.on("broadcast", { event: "state" }, ({ payload }) => console.log("state", JSON.stringify(payload)));
ch.on("presence", { event: "sync" }, () => console.log("presence", JSON.stringify(Object.keys(ch.presenceState()))));
ch.subscribe(async (st) => {
  if (st !== "SUBSCRIBED") return;
  const t0 = Date.now();
  await ch.send({ type: "broadcast", event: "cmd", payload: c });
  console.log("sent", JSON.stringify({ ...c, sig: "…" }));
  setTimeout(() => { console.log("done", Date.now() - t0, "ms"); process.exit(0); }, 3000);
});
