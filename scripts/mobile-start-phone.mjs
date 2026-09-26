#!/usr/bin/env node
/**
 * Start Expo for a physical phone (Expo Go) against production API.
 * Writes mobile/.env.local from .env.production (gitignored) so local .env is untouched.
 */
import { copyFileSync, existsSync } from "node:fs";
import { spawn } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const mobileRoot = join(dirname(fileURLToPath(import.meta.url)), "..", "mobile");
const productionEnv = join(mobileRoot, ".env.production");
const localEnv = join(mobileRoot, ".env.local");

if (!existsSync(productionEnv)) {
  console.error("Missing mobile/.env.production — cannot start phone session.");
  process.exit(1);
}

copyFileSync(productionEnv, localEnv);
console.log("Using production API from .env.production → .env.local");
console.log("Scan the QR with Expo Go on your iPhone (or Android).");
console.log("Android customers still use the sideload APK — this is for UI/API smoke tests.\n");

const child = spawn("npx", ["expo", "start", "--tunnel"], {
  cwd: mobileRoot,
  stdio: "inherit",
  env: process.env,
  shell: process.platform === "win32",
});

child.on("exit", (code) => process.exit(code ?? 0));
