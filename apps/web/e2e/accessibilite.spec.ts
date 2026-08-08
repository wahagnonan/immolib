import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const pages = ["/", "/connexion", "/inscription", "/mot-de-passe-oublie"];

test.describe("Tests d'accessibilité (axe-core)", () => {
  for (const path of pages) {
    test(`page ${path} ne présente pas de violation d'accessibilité`, async ({
      page,
    }) => {
      await page.goto(path, { waitUntil: "networkidle" });

      const results = await new AxeBuilder({ page }).analyze();

      expect(
        results.violations.map((violation) => ({
          id: violation.id,
          impact: violation.impact,
          nodes: violation.nodes.length,
          help: violation.help,
        })),
      ).toEqual([]);
    });
  }
});
