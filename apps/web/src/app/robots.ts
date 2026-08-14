import type { MetadataRoute } from "next";

import { siteUrl } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: ["/", "/verifier-quittance"],
      disallow: [
        "/backend/",
        "/baux",
        "/connexion",
        "/coproprietaires",
        "/documents/",
        "/echeances",
        "/espace-locataire",
        "/incidents",
        "/invitation-locataire/",
        "/locataires",
        "/maisons",
        "/paiements",
        "/parametres/",
        "/tableau-de-bord",
        "/verification-telephone",
      ],
    },
    sitemap: new URL("/sitemap.xml", siteUrl).toString(),
  };
}
