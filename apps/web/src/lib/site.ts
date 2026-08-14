const configuredUrl = process.env.NEXT_PUBLIC_APP_URL?.trim();

export const siteUrl = new URL(configuredUrl || "http://localhost:3000");

export const siteDescription =
  "Gérez vos biens, baux, loyers, paiements, quittances et incidents dans un espace clair pour le bailleur et le locataire.";
