// List Matter devices answering on mDNS for 8 s: _matter._tcp (already paired somewhere) and _matterc._udp (open to pairing).
import mdns from "multicast-dns";
const m = mdns({ interface: "192.168.50.101" }), seen = new Map();
m.on("response", (r) => {
  for (const a of [...r.answers, ...r.additionals]) {
    if (a.type === "PTR" && /_matterc?\._(tcp|udp)\.local$/.test(a.name)) seen.set(a.data, a.name);
    if (a.type === "TXT" && seen.has(a.name)) seen.set(a.name, seen.get(a.name) + " " + a.data.map(String).join(" "));
    if ((a.type === "A" || a.type === "AAAA")) seen.set("host " + a.name, a.data);
  }
});
for (const n of ["_matter._tcp.local", "_matterc._udp.local"]) m.query({ questions: [{ name: n, type: "PTR" }] });
setInterval(() => { for (const n of ["_matter._tcp.local", "_matterc._udp.local"]) m.query({ questions: [{ name: n, type: "PTR" }] }); }, 2000);
setTimeout(() => { for (const [k, v] of seen) console.log(k, "=>", v); console.log("count", seen.size); m.destroy(); process.exit(0); }, 8000);
