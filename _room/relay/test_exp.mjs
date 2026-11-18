// Sends a command signed the way the app does (12 h key + exp), deriving that key from the secret the relay itself loads.
import { createClient } from "@supabase/supabase-js";
import { createHmac, privateDecrypt, constants } from "node:crypto";
import { readFileSync } from "node:fs";
const URL = "https://hxaftcofwrffwjxtjeoj.supabase.co";
const { s: enc } = await (await fetch(`${URL}/functions/v1/lamp?relay=1`)).json();
const secret = privateDecrypt({ key: readFileSync(new globalThis.URL("./relay_key.pem", import.meta.url)), padding: constants.RSA_PKCS1_OAEP_PADDING, oaepHash: "sha256" }, Buffer.from(enc, "base64"));
const exp = Date.now() + 12 * 3600000, k = createHmac("sha256", secret).update(`lamp|${exp}`).digest();
const c = JSON.parse(process.argv[2]);
const sb = createClient(URL, "sb_publishable_4TJE66VMSen-hl22kWL-Rw_8RXH_UOH");
const ch = sb.channel("room-lights", { config: { broadcast: { self: false } } });
ch.on("broadcast", { event: "state" }, ({ payload }) => console.log("state", JSON.stringify(payload)));
ch.subscribe(async (st) => {
  if (st !== "SUBSCRIBED") return;
  c.t = Date.now(); c.exp = exp;
  const f = (v) => (v === undefined || v === null ? "" : String(v));
  c.sig = createHmac("sha256", k).update([c.lamp, c.on, c.brightness, c.k, c.hue, c.sat, c.t].map(f).join("|")).digest("hex");
  await ch.send({ type: "broadcast", event: "cmd", payload: c });
  setTimeout(() => process.exit(0), 2500);
});
