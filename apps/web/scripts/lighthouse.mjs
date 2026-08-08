#!/usr/bin/env node
/* Analyse des Core Web Vitals avec Lighthouse.
 * Usage : node scripts/lighthouse.mjs [url]   (défaut http://localhost:3000)
 * Exige Google Chrome (CHEMIN : CHROME_PATH ou binaire détecté).
 * Échec si un score seuil n'est pas atteint.
 */

import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const url = process.argv[2] ?? "http://localhost:3000";

const thresholds = {
  performance: Number(process.env.LH_PERFORMANCE ?? "70"),
  accessibility: Number(process.env.LH_ACCESSIBILITY ?? "90"),
  "best-practices": Number(process.env.LH_BEST_PRACTICES ?? "80"),
  seo: Number(process.env.LH_SEO ?? "80"),
};

function findChrome() {
  const candidates = [
    process.env.CHROME_PATH,
    process.env.CHROME_BIN,
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

const chromePath = findChrome();
if (!chromePath) {
  console.error(
    "Chrome introuvable. Définissez CHROME_PATH (ou installez Chromium, ex. npx playwright install chromium).",
  );
  process.exit(1);
}

const output = join(tmpdir(), `lighthouse-${Date.now()}.json`);
const args = [
  "lighthouse",
  url,
  "--output=json",
  `--output-path=${output}`,
  "--quiet",
  "--chrome-flags=--headless --no-sandbox --disable-gpu",
  "--preset=desktop",
  "--chrome-path",
  chromePath,
];

execFileSync("npx", args, { stdio: "inherit", shell: process.platform === "win32" });

const report = JSON.parse((await import("node:fs/promises")).readFile(output, "utf8"));
const scores = Object.fromEntries(
  Object.entries(report.categories).map(([key, category]) => [key, Math.round(category.score * 100)]),
);
const metrics = report.audits;

console.log("\nScores Lighthouse :");
for (const [key, value] of Object.entries(scores)) console.log(`  ${key.padEnd(16)} ${value}`);

console.log("\nCore Web Vitals (desktop) :");
for (const metric of ["largest-contentful-paint", "cumulative-layout-shift", "total-blocking-time", "interactive", "first-contentful-paint", "speed-index"]) {
  const audit = metrics[metric];
  if (audit) console.log(`  ${metric.padEnd(30)} ${audit.displayValue ?? audit.score}`);
}

let failed = false;
for (const [key, threshold] of Object.entries(thresholds)) {
  if ((scores[key] ?? 0) < threshold) {
    failed = true;
    console.error(`  ✗ ${key} : ${scores[key]} < ${threshold}`);
  }
}
if (failed) process.exit(1);
console.log("\nTous les seuils Core Web Vitals sont atteints.");
