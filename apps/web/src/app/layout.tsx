import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { AuthProvider } from "@/components/auth/auth-provider";
import { PwaInstallBanner } from "@/components/pwa-install-banner";
import { siteDescription, siteUrl } from "@/lib/site";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: siteUrl,
  title: {
    default: "ImmoLib — Gestion locative simple",
    template: "%s · ImmoLib",
  },
  description: siteDescription,
  applicationName: "ImmoLib",
  authors: [{ name: "ImmoLib" }],
  creator: "ImmoLib",
  publisher: "ImmoLib",
  category: "Gestion locative",
  icons: {
    icon: [{ url: "/icon", type: "image/png", sizes: "512x512" }],
    apple: [{ url: "/apple-icon", type: "image/png", sizes: "180x180" }],
  },
  keywords: [
    "gestion locative",
    "quittance de loyer",
    "bailleur",
    "locataire",
    "maison",
    "loyer",
    "Côte d’Ivoire",
  ],
  openGraph: {
    type: "website",
    locale: "fr_CI",
    siteName: "ImmoLib",
    title: "ImmoLib — Gestion locative simple",
    description: siteDescription,
  },
  twitter: {
    card: "summary",
    title: "ImmoLib — Gestion locative simple",
    description: siteDescription,
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  colorScheme: "light",
  themeColor: "#d4342b",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body>
        <a className="skip-link" href="#contenu-principal">
          Aller au contenu principal
        </a>
        <AuthProvider>{children}</AuthProvider>
        <PwaInstallBanner />
      </body>
    </html>
  );
}
