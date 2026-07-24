import { test, expect } from "@playwright/test";

test.describe("Parcours complet : Inscription et vérification", () => {
  test("s'inscrit et vérifie le téléphone", async ({ page }) => {
    await page.goto("/inscription");

    await page.fill("input[autocomplete='given-name']", "Jean");
    await page.fill("input[autocomplete='family-name']", "Dupont");
    await page.fill("input[autocomplete='tel']", "+22507000000");
    await page.fill("input[autocomplete='email']", "jean@example.com");
    await page.fill("input[autocomplete='new-password']", "MotDePasse123!");

    const confirmInputs = page.locator("input[autocomplete='new-password']");
    await confirmInputs.nth(1).fill("MotDePasse123!");

    await page.click("button[type='submit']");

    await expect(page.getByText(/Vérifiez votre (email|téléphone)/)).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Parcours complet : Connexion", () => {
  test("se connecte et accède au tableau de bord", async ({ page }) => {
    await page.goto("/connexion");

    await page.fill("input[autocomplete='tel']", "+22507000000");
    await page.fill("input.autocomplete='current-password'", "MotDePasse123!");

    await page.click("button[type='submit']");

    await expect(page).toHaveURL(/\/tableau-de-bord/, { timeout: 10000 });
  });

  test("affiche une erreur avec des identifiants invalides", async ({ page }) => {
    await page.goto("/connexion");

    await page.fill("input[autocomplete='tel']", "+22507000000");
    await page.fill("input[autocomplete='current-password']", "mauvais");

    await page.click("button[type='submit']");

    await expect(page.getByRole("alert")).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Parcours complet : Création d'une maison", () => {
  test("crée une maison avec succès", async ({ page }) => {
    await page.goto("/maisons");

    await page.click("text=Nouvelle maison");
    await page.fill("input[placeholder='Ex. Villa des Lauriers']", "Villa Test E2E");
    await page.fill("input[placeholder='Rue, quartier ou lot']", "Rue 123");
    await page.fill("input[placeholder='Cocody']", "Cocody");
    await page.fill("input[placeholder='Abidjan']", "Abidjan");

    await page.click("text=Créer la maison");

    await expect(page.getByText("Maison ajoutée avec succès.")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Villa Test E2E")).toBeVisible();
  });
});

test.describe("Parcours complet : Ajout d'un locataire", () => {
  test("ajoute un locataire à une maison", async ({ page }) => {
    await page.goto("/locataires");

    await page.click("text=Nouveau locataire");
    await page.fill("input[placeholder='Kouamé Alphonse']", "Kouamé Alphonse");
    await page.fill("input[placeholder='+225 07 00 00 00 00']", "+22507000000");
    await page.selectOption("select", { index: 1 });

    await page.click("button[type='submit']");

    await expect(page.getByText("Locataire ajouté avec succès.")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Kouamé Alphonse")).toBeVisible();
  });
});

test.describe("Parcours complet : Création et activation d'un bail", () => {
  test("crée un bail", async ({ page }) => {
    await page.goto("/baux");

    await page.click("text=Nouveau bail");
    await page.selectOption("select", { index: 1 });
    await page.fill("input[placeholder='Ex. 200000']", "200000");
    await page.fill("input[placeholder='Ex. 15000']", "15000");
    await page.fill("input[placeholder='Ex. 200000']", "200000");
    await page.click("text=Créer le bail");

    await expect(page.getByText("Bail créé avec succès.")).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Parcours complet : Génération d'échéances", () => {
  test("génère les échéances mensuelles", async ({ page }) => {
    await page.goto("/echeances");

    await page.click("text=Générer les échéances");
    await page.selectOption("select", { index: 1 });

    await page.click("text=Générer");

    await expect(page.getByText(/échéance(s)? générée(s)?/)).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Parcours complet : Enregistrement d'un paiement", () => {
  test("enregistre un paiement", async ({ page }) => {
    await page.goto("/paiements");

    await page.click("text=Nouveau paiement");
    await page.fill("input[placeholder='Ex. 200000']", "200000");
    await page.click("text=Enregistrer le paiement");

    await expect(page.getByText("Paiement enregistré.")).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Parcours complet : Génération et consultation d'une quittance", () => {
  test("génère une quittance", async ({ page }) => {
    await page.goto("/documents");

    await page.click("text=Générer un document");
    await page.selectOption("select", { index: 1 });
    await page.click("text=Générer");

    await expect(page.getByText("Document généré.")).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Parcours complet : Invitation d'un locataire", () => {
  test("invite un locataire", async ({ page }) => {
    await page.goto("/locataires");

    await page.click("text=Inviter");
    await page.click("text=Envoyer l'invitation");

    await expect(page.getByText(/Invitation envoyée/)).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Parcours complet : Remboursement ou affectation d'une caution", () => {
  test("rembourse une caution", async ({ page }) => {
    await page.goto("/paiements");

    await page.click("text=Caution");
    await page.click("text=Rembourser");
    await page.fill("input[placeholder='Ex. 200000']", "200000");

    await expect(page.getByText("Mouvement enregistré.")).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Parcours complet : Signalement d'un incident", () => {
  test("signale un incident de maintenance", async ({ page }) => {
    await page.goto("/incidents");

    await page.click("text=Signaler un incident");
    await page.fill("input[placeholder='Ex. fuite sous l'évier']", "Fuite sous l'évier");
    await page.fill("textarea", "De l'eau s'écoule sous la canalisation.");
    await page.selectOption("select", { index: 1 });

    await page.click("text=Enregistrer");

    await expect(page.getByText("Incident enregistré et ajouté au suivi.")).toBeVisible({ timeout: 10000 });
  });
});