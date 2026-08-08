import { expect, test } from "@playwright/test";

const pages = ["/", "/connexion", "/inscription", "/mot-de-passe-oublie"];

test.describe("Tests responsive : pas de débordement horizontal", () => {
  for (const path of pages) {
    test(`page ${path} ne déborde pas sur mobile`, async ({ page }) => {
      await page.goto(path, { waitUntil: "networkidle" });

      const overflow = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }));

      expect(
        overflow.scrollWidth,
        `Débordement horizontal détecté sur ${path} (scrollWidth=${overflow.scrollWidth}, clientWidth=${overflow.clientWidth})`,
      ).toBeLessThanOrEqual(overflow.clientWidth);
    });
  }
});
