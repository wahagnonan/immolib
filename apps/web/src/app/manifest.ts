import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ImmoLib — Gestion locative pour maisons",
    short_name: "ImmoLib",
    description:
      "Application de gestion locative. Suivez baux, loyers, paiements et quittances. Espace bailleur et locataire.",
    start_url: "/",
    display: "standalone",
    background_color: "#f9f6f5",
    theme_color: "#d4342b",
    orientation: "portrait-primary",
    lang: "fr-CI",
    scope: "/",
    categories: ["finance", "business"],
    shortcuts: [
      {
        name: "Tableau de bord",
        short_name: "Dashboard",
        url: "/tableau-de-bord",
        description: "Vue d'ensemble de vos locations",
      },
      {
        name: "Paiements",
        short_name: "Paiements",
        url: "/paiements",
        description: "Enregistrer un paiement",
      },
      {
        name: "Documents",
        short_name: "Docs",
        url: "/documents",
        description: "Reçus et quittances",
      },
    ],
    icons: [
      {
        src: "/icon",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icon",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icon",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
      {
        src: "/immolib-mark.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "maskable",
      },
    ],
  };
}
