// Commission one bulb on the local network:  node pair.mjs <pixar|little> <11- or 21-digit manual pairing code>
// Get the code from the Govee Home app (device settings, Matter); it's only valid for a few minutes.
import { GeneralCommissioning } from "@matter/main/clusters";
import { Seconds } from "@matter/main";
import { ManualPairingCodeCodec } from "@matter/types";
import { startController, saveLamp, lamps } from "./matter.mjs";

const [name, raw, ip] = process.argv.slice(2); // optional ip: the bulb's address, when discovery misses it
if (!["pixar", "little"].includes(name) || !raw) {
  console.log("usage: node pair.mjs <pixar|little> <pairing code>");
  process.exit(1);
}
const code = raw.replace(/\D/g, "");
const pc = ManualPairingCodeCodec.decode(code);
console.log(`pairing ${name}: short discriminator ${pc.shortDiscriminator}`);

const controller = await startController({ quiet: false });
try {
  const nodeId = await controller.commissionNode({
    commissioning: {
      regulatoryLocation: GeneralCommissioning.RegulatoryLocationType.IndoorOutdoor,
      regulatoryCountryCode: "US",
    },
    discovery: {
      identifierData: { shortDiscriminator: pc.shortDiscriminator },
      discoveryCapabilities: { onIpNetwork: true },
      timeout: Seconds(90),
      ...(ip ? { knownAddress: { type: "udp", ip, port: 5540 } } : {}),
    },
    passcode: pc.passcode,
  });
  saveLamp(name, nodeId);
  console.log(`PAIRED ${name} as node ${nodeId}`);
  console.log("lamps:", lamps());
} catch (e) {
  console.log("PAIR FAILED:", e?.message ?? e);
  process.exitCode = 1;
} finally {
  await controller.close();
}
