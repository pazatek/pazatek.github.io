import "jsr:@supabase/functions-js/edge-runtime.d.ts";

// Signing keys for the lamp relay (see _room/relay). The app signs lamp commands with a short-lived key; the relay on the PC
// derives the same key from a shared secret, so neither the app key nor the secret ever crosses the public Realtime channel.
//   POST {action:token} + x-room-key -> { exp, key }   key = hex(HMAC-SHA256(secret, "lamp|" + exp)), exp = now + 12 h (ms)
//   GET  ?relay=1                    -> { s }          the secret, RSA-OAEP(SHA-256) encrypted to the relay's public key
// The secret is made here on first use and kept in room_secrets ('lamp_relay'); the relay's public key is 'lamp_relay_pub'.

const ORIGINS = new Set(["https://piotrzatek.com", "https://www.piotrzatek.com", "https://pazatek.github.io"]);
const BASE = Deno.env.get("SUPABASE_URL")!;
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db = { apikey: SERVICE, Authorization: `Bearer ${SERVICE}`, "Content-Type": "application/json" };
const hex = (b: ArrayBuffer | Uint8Array) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");

async function secretRow(name: string) {
  const r = await fetch(`${BASE}/rest/v1/room_secrets?name=eq.${name}&select=value`, { headers: db });
  if (!r.ok) throw new Error(`room_secrets http ${r.status}`);
  return ((await r.json()) as { value: string }[])[0]?.value ?? null;
}
async function secret() {
  const have = await secretRow("lamp_relay");
  if (have) return have;
  const made = hex(crypto.getRandomValues(new Uint8Array(32)));
  // ignore-duplicates: if two calls race, both then read back the one that won
  await fetch(`${BASE}/rest/v1/room_secrets?on_conflict=name`, { method: "POST", headers: { ...db, Prefer: "resolution=ignore-duplicates,return=minimal" }, body: JSON.stringify({ name: "lamp_relay", value: made }) });
  return (await secretRow("lamp_relay"))!;
}
async function hmac(keyBytes: Uint8Array, msg: string) {
  const k = await crypto.subtle.importKey("raw", keyBytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return hex(await crypto.subtle.sign("HMAC", k, new TextEncoder().encode(msg)));
}
const fromHex = (h: string) => Uint8Array.from(h.match(/../g)!.map((x) => parseInt(x, 16)));

Deno.serve(async (req: Request) => {
  const o = req.headers.get("origin") ?? "";
  const headers = {
    "Access-Control-Allow-Origin": ORIGINS.has(o) ? o : "https://piotrzatek.com", "Access-Control-Allow-Headers": "x-room-key, content-type",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Max-Age": "86400", Vary: "Origin", "Content-Type": "application/json", "Cache-Control": "no-store",
  };
  const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers });
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers });
  try {
    if (req.method === "GET" && new URL(req.url).searchParams.get("relay") === "1") {
      const pem = await secretRow("lamp_relay_pub");
      if (!pem) return reply({ error: "no relay key" }, 404);
      const der = Uint8Array.from(atob(pem.replace(/-----[^-]+-----|\s/g, "")), (c) => c.charCodeAt(0));
      const pub = await crypto.subtle.importKey("spki", der, { name: "RSA-OAEP", hash: "SHA-256" }, false, ["encrypt"]);
      const s = await crypto.subtle.encrypt({ name: "RSA-OAEP" }, pub, fromHex(await secret()));
      return reply({ s: btoa(String.fromCharCode(...new Uint8Array(s))) });
    }
    if (req.method !== "POST") return reply({ error: "method" }, 405);
    const key = req.headers.get("x-room-key") ?? "";
    if (key.length < 16 || key.length > 128) return reply({ error: "key" }, 401);
    const label = await fetch(`${BASE}/rest/v1/rpc/room_key_label`, { method: "POST", headers: db, body: JSON.stringify({ p_key: key }) }).then((r) => r.json());
    if (!label) return reply({ error: "key" }, 401);
    const body = await req.json().catch(() => ({}));
    if (body.action !== "token") return reply({ error: "action" }, 400);
    const exp = Date.now() + 12 * 3600000;
    return reply({ exp, key: await hmac(fromHex(await secret()), `lamp|${exp}`) });
  } catch (e) {
    return reply({ error: "server", detail: (e as Error).message.slice(0, 200) }, 502);
  }
});
