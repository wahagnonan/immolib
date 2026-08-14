import type { MetadataRoute } from "next";

import { siteUrl } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: new URL("/", siteUrl).toString(),
      changeFrequency: "monthly",
      priority: 1,
    },
    {
      url: new URL("/verifier-quittance", siteUrl).toString(),
      changeFrequency: "yearly",
      priority: 0.7,
    },
    {
      url: new URL("/inscription", siteUrl).toString(),
      changeFrequency: "yearly",
      priority: 0.6,
    },
    {
      url: new URL("/connexion", siteUrl).toString(),
      changeFrequency: "yearly",
      priority: 0.3,
    },
  ];
}
