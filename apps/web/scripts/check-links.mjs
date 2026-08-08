#!/usr/bin/env node
/* Vérifie qu'aucun lien interne du site ne pointe vers une page 404/500.
 * Usage : node scripts/check-links.mjs [baseUrl]   (défaut http://localhost:3000)
 */

const baseUrl = (process.argv[2] ?? "http://localhost:3000").replace(/\/$/, "");
const maxPages = Number(process.env.MAX_PAGES ?? "200");

const HREF_RE = /\bhref\s*=\s*"([^"]+)"/g;
const SKIP_EXT = /\.(png|jpe?g|gif|svg|webp|ico|pdf|woff2?|css|js|map|txt|json|xml)(\?|$)/i;

async function extractLinks(url) {
  const response = await fetch(url, {
    headers: { "User-Agent": "immolib-link-checker" },
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) return { status: response.status, links: [] };
  const html = await response.text();
  const links = [];
  for (const match of html.matchAll(HREF_RE)) {
    const raw = match[1].split("#")[0];
    if (!raw || raw.startsWith("mailto:") || raw.startsWith("tel:") || raw.startsWith("data:")) {
      continue;
    }
    let target;
    try {
      target = new URL(raw, url).href;
    } catch {
      continue;
    }
    if (target.origin === baseUrl) links.push(target);
  }
  return { status: response.status, links };
}

const visited = new Set();
const queued = [baseUrl];
const broken = [];

while (queued.length && visited.size < maxPages) {
  const url = queued.shift();
  if (visited.has(url)) continue;
  visited.add(url);

  const { status, links } = await extractLinks(url);
  if (status >= 400) {
    broken.push({ url, status });
    console.error(`  ${status}  ${url}`);
    continue;
  }
  for (const link of links) {
    if (!visited.has(link) && !queued.includes(link) && !SKIP_EXT.test(link)) {
      queued.push(link);
    }
  }
}

// Vérifie aussi chaque lien externe découvert pendant le crawl.
const externalLinks = [...queued, ...visited].filter(
  (url) => url.startsWith("http") && new URL(url).origin !== baseUrl,
);

console.log(`\n${visited.size} pages internes vérifiées (${broken.length} cassée(s)).`);
if (externalLinks.length) {
  console.log(`${externalLinks.length} liens externes détectés (non vérifiés par défaut).`);
}

if (broken.length) {
  console.error("\nLiens brisés :");
  for (const item of broken) console.error(`  ${item.status}  ${item.url}`);
  process.exit(1);
}
