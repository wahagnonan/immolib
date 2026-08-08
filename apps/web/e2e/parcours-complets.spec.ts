import { expect, test } from "@playwright/test";
import { uniqueName } from "./helpers";

test.describe("Parcours complet : gestion locative", () => {
  test("chaîne maison → locataire → bail → échéances → paiement P2P → incident", async ({
    page,
  }) => {
    test.setTimeout(180_000);
    const houseName = uniqueName("Villa E2E");
    const tenantName = uniqueName("Kouamé E2E");
    const tenantPhone = `07${String(Date.now()).slice(-8)}`;

    // 1. Créer une maison
    await page.goto("/maisons");
    await page.getByRole("button", { name: "Nouvelle maison" }).click();
    await page.getByPlaceholder("Ex. Villa des Lauriers").fill(houseName);
    await page.getByPlaceholder("Cocody").fill("Cocody");
    await page.getByPlaceholder("Rue, quartier ou lot").fill("Rue 123");
    await page.getByRole("button", { name: "Créer la maison" }).click();
    await expect(page.getByText("Maison ajoutée avec succès.")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(houseName)).toBeVisible();

    // 2. Ajouter un locataire
    await page.goto("/locataires");
    await page.getByRole("button", { name: "Ajouter un locataire" }).click();
    await page
      .getByRole("combobox")
      .filter({ has: page.getByText(/Sélectionner une maison/) })
      .selectOption({ label: `${houseName} — Cocody` });
    await page.getByPlaceholder("Ex. Aïcha Koné").fill(tenantName);
    await page.fill("input[autocomplete='tel']", tenantPhone);
    await page.getByRole("button", { name: "Ajouter le locataire" }).click();
    await expect(page.getByText("Locataire ajouté avec succès.")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(tenantName)).toBeVisible();

    // 3. Créer puis activer un bail
    await page.goto("/baux");
    await page.getByRole("button", { name: "Nouveau bail" }).click();
    await page.getByLabel("Maison *").selectOption({ label: houseName });
    await page.getByLabel("Locataire *").selectOption({ label: tenantName });
    await page.getByLabel("Date de début *").fill("2026-08-01");
    await page.getByLabel("Loyer mensuel *").fill("200000");
    await page.getByLabel("Jour limite *").fill("5");
    await page.getByRole("button", { name: "Créer le brouillon" }).click();
    await expect(
      page.getByText("Bail créé en brouillon. Vérifiez-le avant de l’activer."),
    ).toBeVisible({ timeout: 15_000 });
    await page.getByRole("button", { name: "Activer le bail" }).click();
    await expect(page.getByText("Bail activé et maison occupée.")).toBeVisible({
      timeout: 15_000,
    });

    // 4. Générer les échéances du mois
    await page.goto("/echeances");
    await page.getByRole("button", { name: "Générer ce mois" }).click();
    await expect(page.getByText(/créée\(s\)/)).toBeVisible({ timeout: 15_000 });

    // 5. Ajouter un moyen de paiement Mobile Money
    await page.goto("/moyens-paiement");
    await page.getByRole("button", { name: "Ajouter un compte" }).click();
    await page.getByLabel("Opérateur *").selectOption({ label: "Orange Money" });
    await page.fill("input[autocomplete='tel']", "0700000000");
    await page.getByRole("button", { name: "Enregistrer le compte" }).click();
    await expect(
      page.getByText("Moyen de paiement ajouté."),
    ).toBeVisible({ timeout: 15_000 });

    // 6. Initier puis confirmer un paiement (simulation P2P)
    await page.goto("/paiements");
    await page.getByRole("button", { name: "Initier un paiement" }).click();
    await page
      .getByLabel("Échéance *")
      .selectOption({ label: new RegExp(houseName) });
    await page
      .getByRole("button", { name: "Initier" })
      .click();
    await expect(page.getByText("En attente de confirmation")).toBeVisible({
      timeout: 15_000,
    });
    await page
      .getByRole("button", { name: "Confirmer la réception" })
      .first()
      .click();
    await expect(
      page.getByText("Paiement confirmé. Quittance générée."),
    ).toBeVisible({ timeout: 15_000 });

    // 7. Signaler un incident sur le bail actif
    await page.goto("/incidents");
    await page.getByRole("button", { name: "Signaler un incident" }).click();
    await page
      .getByLabel("Bail concerné *")
      .selectOption({ label: `${houseName} — ${tenantName}` });
    await page.getByLabel("Catégorie *").selectOption({ label: "Plomberie" });
    await page.getByPlaceholder("Ex. fuite sous l’évier").fill("Fuite sous l'évier");
    await page
      .getByPlaceholder("Décrivez le problème et son impact.")
      .fill("De l'eau s'écoule sous la canalisation.");
    await page.getByRole("button", { name: "Enregistrer" }).click();
    await expect(
      page.getByText("Incident enregistré et ajouté au suivi."),
    ).toBeVisible({ timeout: 15_000 });
  });
});
