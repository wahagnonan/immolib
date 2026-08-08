import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

const identityPath = join(process.cwd(), ".auth", "identity.json");

export default function globalSetup() {
  const stamp = Date.now();
  const identity = {
    email: `e2e-${stamp}@example.com`,
    phoneNational: `07${String(stamp).slice(-8)}`,
    password: "MotDePasseE2E123!",
  };
  mkdirSync(dirname(identityPath), { recursive: true });
  rmSync(identityPath, { force: true });
  writeFileSync(identityPath, JSON.stringify(identity));
}
