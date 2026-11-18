// Quick test:  node lamp.mjs <pixar|little> <on|off|toggle>   prints how long the bulb took to acknowledge.
import { OnOff } from "@matter/main/clusters";
import { NodeId } from "@matter/main";
import { startController, lamps } from "./matter.mjs";

const [name, what = "toggle"] = process.argv.slice(2);
const id = lamps()[name];
if (!id) { console.log(`no lamp "${name}" paired; have:`, lamps()); process.exit(1); }

const controller = await startController();
try {
  const node = await controller.getNode(NodeId(BigInt(id)));
  node.connect();
  if (!node.isConnected) await node.events.initializedFromRemote;
  const dev = node.getDevices().find((d) => d.getClusterClient(OnOff.Complete));
  const onOff = dev.getClusterClient(OnOff.Complete);
  console.log(`${name} was ${(await onOff.getOnOffAttribute()) ? "on" : "off"}`);
  const t0 = performance.now();
  await (what === "on" ? onOff.on() : what === "off" ? onOff.off() : onOff.toggle());
  console.log(`${what} acknowledged in ${(performance.now() - t0).toFixed(0)} ms`);
} catch (e) {
  console.log("FAILED:", e?.message ?? e);
  process.exitCode = 1;
} finally {
  await controller.close();
}
