import { test as setup } from "@playwright/test";
import { registerOwner } from "./helpers";

setup("créer un compte propriétaire vérifié", async ({ page }) => {
  await registerOwner(page);
  await page.context().storageState({ path: ".auth/owner.json" });
});
