const configuredUrl = process.env.NEXT_PUBLIC_APP_URL?.trim();

export const siteUrl = new URL(configuredUrl || "http://localhost:3000");

export const siteDescription =
  "ImmoLib — Application de gestion locative pour maisons en Côte d'Ivoire. Suivez baux, loyers, paiements et quittances. Espace bailleur et locataire.";
