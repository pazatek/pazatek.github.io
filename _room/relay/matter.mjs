// Shared Matter controller setup for the lamp relay. The fabric (keys, paired nodes) lives in ./.matter so a restart
// doesn't need re-pairing. This is a second Matter admin: the bulbs stay in the Govee app too.
import { Environment, Logger } from "@matter/main";
import { CommissioningController } from "@project-chip/matter.js";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { readFileSync, writeFileSync, existsSync } from "node:fs";

export const HERE = dirname(fileURLToPath(import.meta.url));
const NAMES = join(HERE, "lamps.json"); // { "pixar": "<nodeId>", "little": "<nodeId>" }

export function lamps() {
  return existsSync(NAMES) ? JSON.parse(readFileSync(NAMES, "utf8")) : {};
}
export function saveLamp(name, nodeId) {
  const all = lamps();
  all[name] = String(nodeId);
  writeFileSync(NAMES, JSON.stringify(all, null, 2));
}

export async function startController({ quiet = true } = {}) {
  const environment = Environment.default;
  environment.vars.set("storage.path", join(HERE, ".matter"));
  if (quiet) Logger.level = "warn";
  const controller = new CommissioningController({
    environment: { environment, id: "room-relay" },
    autoConnect: false,
    adminFabricLabel: "Room relay",
  });
  await controller.start();
  return controller;
}
