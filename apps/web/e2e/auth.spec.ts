import { expect, test } from "@playwright/test";
import { e2eIdentity } from "./helpers";

test.describe("Parcours public : authentification", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("affiche une erreur avec des identifiants invalides", async ({ page }) => {
    await page.goto("/connexion");
    await expect(page.getByRole("button", { name: "Se connecter" })).toBeEnabled({
      timeout: 30_000,
    });

    await page.fill("input[autocomplete='email']", "inconnu@example.com");
    await page.fill("input[autocomplete='current-password']", "mauvais");
    await page.getByRole("button", { name: "Se connecter" }).click();

    await expect(
      page.getByRole("alert").filter({ hasText: "Email ou mot de passe incorrect." }),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("se connecte avec l'adresse email", async ({ page }) => {
    const identity = e2eIdentity();
    await page.goto("/connexion");
    await expect(page.getByRole("button", { name: "Se connecter" })).toBeEnabled({
      timeout: 30_000,
    });

    await page.fill("input[autocomplete='email']", identity.email);
    await page.fill("input[autocomplete='current-password']", identity.password);
    await page.getByRole("button", { name: "Se connecter" }).click();

    await expect(page).toHaveURL(/\/tableau-de-bord/, { timeout: 30_000 });
  });

  test("l'inscription affiche l'indicatif +225 par défaut", async ({ page }) => {
    await page.goto("/inscription");

    const select = page.getByLabel("Indicatif du pays");
    await expect(select).toHaveValue("CI");
    await expect(select.locator("option[value='CI']")).toContainText("+225");
    await expect(select.locator("option")).toHaveCount(245);
  });

  test("des mots de passe différents bloquent l'inscription", async ({ page }) => {
    const identity = e2eIdentity();
    await page.goto("/inscription");
    await expect(page.getByRole("button", { name: "Créer mon compte" })).toBeEnabled({
      timeout: 30_000,
    });

    await page.fill("input[autocomplete='given-name']", "Jean");
    await page.fill("input[autocomplete='family-name']", "Dupont");
    await page.fill("input[autocomplete='tel']", identity.phoneNational);
    await page.fill("input[autocomplete='email']", `autre-${identity.email}`);

    const passwords = page.locator("input[autocomplete='new-password']");
    await passwords.nth(0).fill(identity.password);
    await passwords.nth(1).fill("autre-mot-de-passe");

    await page.getByRole("button", { name: "Créer mon compte" }).click();

    await expect(page.getByText("Les deux mots de passe ne correspondent pas.")).toBeVisible({
      timeout: 15_000,
    });
  });
});
