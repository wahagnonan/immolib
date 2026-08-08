import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { expect, type Page } from "@playwright/test";

type E2EIdentity = {
  email: string;
  phoneNational: string;
  password: string;
};

const identityPath = join(process.cwd(), ".auth", "identity.json");

export function e2eIdentity(): E2EIdentity {
  if (existsSync(identityPath)) {
    return JSON.parse(readFileSync(identityPath, "utf8")) as E2EIdentity;
  }
  const stamp = Date.now();
  const identity: E2EIdentity = {
    email: `e2e-${stamp}@example.com`,
    phoneNational: `07${String(stamp).slice(-8)}`,
    password: "MotDePasseE2E123!",
  };
  mkdirSync(dirname(identityPath), { recursive: true });
  writeFileSync(identityPath, JSON.stringify(identity));
  return identity;
}

export function uniqueName(prefix: string) {
  return `${prefix} ${Date.now()}`;
}

export async function registerOwner(page: Page) {
  const identity = e2eIdentity();

  await page.goto("/inscription");
  await expect(page.getByRole("button", { name: "Créer mon compte" })).toBeEnabled({
    timeout: 30_000,
  });

  await page.fill("input[autocomplete='given-name']", "Jean");
  await page.fill("input[autocomplete='family-name']", "Dupont");
  await page.fill("input[autocomplete='tel']", identity.phoneNational);
  await page.fill("input[autocomplete='email']", identity.email);

  const passwords = page.locator("input[autocomplete='new-password']");
  await passwords.nth(0).fill(identity.password);
  await passwords.nth(1).fill(identity.password);

  await page.getByRole("button", { name: "Créer mon compte" }).click();

  await expect(page.getByText(/Vérifiez votre (email|téléphone)/)).toBeVisible({
    timeout: 45_000,
  });

  const banner = page.getByText(/Code de développement exposé par l’API/);
  const code = (await banner.textContent())?.match(/\d{6}/)?.[0];
  expect(code, "L'API doit exposer le code OTP (EXPOSE_TEST_OTP=true)").toBeTruthy();

  await page.fill("input[autocomplete='one-time-code']", code!);
  await page.getByRole("button", { name: "Vérifier et me connecter" }).click();

  await expect(page).toHaveURL(/\/tableau-de-bord/, { timeout: 30_000 });
}
