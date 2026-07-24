import { ArrowLeft, ShieldCheck } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { Brand } from "@/components/brand";
import { DocumentVerification } from "@/components/public/document-verification";

export const metadata: Metadata = {
  title: "Vérifier une quittance",
  description:
    "Contrôlez gratuitement l’authenticité d’un reçu ou d’une quittance ImmoLib grâce à sa référence.",
  alternates: { canonical: "/verifier-quittance" },
  robots: { index: true, follow: true },
};

export default async function VerificationPage({
  searchParams,
}: {
  searchParams: Promise<{ reference?: string | string[] }>;
}) {
  const params = await searchParams;
  const initialReference = Array.isArray(params.reference)
    ? params.reference[0] ?? ""
    : params.reference ?? "";

  return (
    <div className="min-h-screen bg-canvas">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex min-h-20 max-w-5xl items-center justify-between gap-4 px-4 sm:px-7">
          <Brand />
          <Link className="secondary-button" href="/">
            <ArrowLeft aria-hidden="true" size={17} />
            <span className="hidden sm:inline">Retour à l’accueil</span>
            <span className="sm:hidden">Retour</span>
          </Link>
        </div>
      </header>
      <main
        className="mx-auto max-w-3xl px-4 py-12 sm:px-7 sm:py-16"
        id="contenu-principal"
      >
        <div className="text-center">
          <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-brand-soft text-brand">
            <ShieldCheck aria-hidden="true" size={28} />
          </span>
          <p className="eyebrow mt-6">Service public ImmoLib</p>
          <h1 className="page-title">Vérifier un document</h1>
          <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-muted sm:text-base">
            Entrez le numéro inscrit sur le reçu ou la quittance. La réponse
            indique si le document existe et s’il est toujours actif.
          </p>
        </div>
        <div className="mt-9">
          <DocumentVerification initialReference={initialReference} />
        </div>
        <p className="mt-6 text-center text-xs leading-5 text-muted">
          Ce contrôle confirme l’enregistrement du document dans ImmoLib. Il ne
          remplace pas la lecture de son contenu ni un conseil juridique.
        </p>
      </main>
    </div>
  );
}
