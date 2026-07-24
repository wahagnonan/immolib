import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  compress: true,
  poweredByHeader: false,
  reactStrictMode: true,
  experimental: {
    optimizePackageImports: ["lucide-react"],
  },
  // Django REST Framework attend les URLs avec leur slash final, y compris
  // pour les POST. On évite que Next.js le retire avant la réécriture.
  skipTrailingSlashRedirect: true,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Permissions-Policy",
            value:
              "camera=(), microphone=(), geolocation=(), browsing-topics=()",
          },
        ],
      },
    ];
  },
  async rewrites() {
    const backendUrl = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
    return [
      {
        source: "/backend/:path*",
        destination: `${backendUrl}/api/v1/:path*/`,
      },
    ];
  },
};

export default nextConfig;
