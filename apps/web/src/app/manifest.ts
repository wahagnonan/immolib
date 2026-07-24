import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ImmoLib — Gestion locative simple",
    short_name: "ImmoLib",
    description:
      "Gestion des maisons, loyers, paiements et quittances pour bailleurs et locataires.",
    start_url: "/",
    display: "standalone",
    background_color: "#f9f6f5",
    theme_color: "#d4342b",
    lang: "fr-CI",
    icons: [
      {
        src: "/icon",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
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
