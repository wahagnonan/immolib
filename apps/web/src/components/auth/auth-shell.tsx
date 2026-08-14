import { ArrowLeft, BadgeCheck, House, ShieldCheck, UsersRound } from "lucide-react";
import Link from "next/link";

import { Brand } from "@/components/brand";

const assurances = [
  {
    icon: House,
    title: "Pensé pour les biens",
    text: "ImmoLib reste volontairement concentré sur la gestion de biens immobiliers.",
  },
  {
    icon: ShieldCheck,
    title: "Session protégée",
    text: "Le mot de passe et les droits restent contrôlés par Django.",
  },
  {
    icon: UsersRound,
    title: "Invitations retrouvées",
    text: "Les invitations liées à votre téléphone sont acceptées à la connexion.",
  },
];

export function AuthShell({
  eyebrow,
  title,
  description,
  children,
  audience = "owner",
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: React.ReactNode;
  audience?: "owner" | "tenant";
}) {
  const isTenant = audience === "tenant";
  return (
    <main
      className="min-h-screen bg-white lg:grid lg:grid-cols-[minmax(380px,0.8fr)_minmax(520px,1.2fr)]"
      id="contenu-principal"
    >
      <aside className="hidden border-r border-line bg-canvas px-10 py-8 lg:flex lg:flex-col xl:px-14">
        <div>
          <Brand />
        </div>
        <div className="my-auto max-w-lg py-14">
          <div className="mb-8 h-1 w-12 bg-brand" />
          <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-brand">
            {isTenant ? "Invitation locataire" : "Espace bailleur"}
          </p>
          <h2 className="mt-4 text-4xl font-semibold tracking-[-0.05em] text-ink xl:text-5xl xl:leading-[1.05]">
            {isTenant
              ? "Vos quittances et paiements, au même endroit."
              : "Vos biens, vos loyers, une vue claire."}
          </h2>
          <p className="mt-5 max-w-lg text-base leading-7 text-muted">
            {isTenant
              ? "Rejoignez le bien enregistré par votre bailleur avec un compte sécurisé."
              : "ImmoLib rassemble les baux, échéances, paiements et quittances sans rendre la gestion compliquée."}
          </p>
          <div className="mt-10 divide-y divide-line border-y border-line">
            {assurances.map((item) => {
              const Icon = item.icon;
              return (
                <div className="flex items-start gap-4 py-5" key={item.title}>
                  <span className="grid size-9 shrink-0 place-items-center rounded-[9px] border border-line bg-white text-ink"><Icon aria-hidden="true" size={18} /></span>
                  <div><p className="font-semibold text-ink">{item.title}</p><p className="mt-1 text-sm leading-5 text-muted">{item.text}</p></div>
                </div>
              );
            })}
          </div>
        </div>
        <p className="flex items-center gap-2 text-xs font-medium text-muted"><BadgeCheck aria-hidden="true" size={16} /> Les autorisations sont toujours vérifiées par le backend.</p>
      </aside>

      <section className="flex min-h-screen flex-col bg-white px-4 py-5 sm:px-8 sm:py-8 lg:px-12 xl:px-20">
        <div className="flex items-center justify-between lg:hidden">
          <Brand />
          <Link className="inline-flex items-center gap-1.5 text-sm font-semibold text-muted" href="/">
            <ArrowLeft size={16} />
            Accueil
          </Link>
        </div>
        <div className="my-auto w-full max-w-lg self-center py-10">
          <div className="mb-8">
            <p className="eyebrow">{eyebrow}</p>
            <h1 className="page-title">{title}</h1>
            <p className="mt-3 text-sm leading-6 text-muted sm:text-base">{description}</p>
          </div>
          <div>{children}</div>
        </div>
        <p className="text-center text-xs text-muted">ImmoLib · Gestion locative en Côte d’Ivoire</p>
      </section>
    </main>
  );
}
