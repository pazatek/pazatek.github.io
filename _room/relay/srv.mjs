import mdns from "multicast-dns";
const m = mdns({ interface: "192.168.50.101" }), out = {};
m.on("response", (r) => { for (const a of [...r.answers, ...r.additionals]) if (["SRV", "A", "AAAA"].includes(a.type)) out[a.type + " " + a.name] = a.data; });
const ask = () => m.query({ questions: [{ name: "_matterc._udp.local", type: "PTR" }, { name: process.argv[2], type: "SRV" }] });
ask(); const t = setInterval(ask, 1500);
setTimeout(() => { console.log(JSON.stringify(out, null, 1)); clearInterval(t); m.destroy(); process.exit(0); }, 6000);
