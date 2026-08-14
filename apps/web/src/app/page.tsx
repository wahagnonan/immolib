import {
  ArrowRight,
  BadgeCheck,
  Building2,
  Check,
  FileCheck2,
  HandCoins,
  House,
  Menu,
  Search,
  ShieldCheck,
  Users,
  Wrench,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { Brand } from "@/components/brand";
import { siteDescription } from "@/lib/site";

export const metadata: Metadata = {
  title: "Gérez vos locations avec moins de stress",
  description: siteDescription,
  alternates: { canonical: "/" },
  robots: { index: true, follow: true },
  openGraph: {
    url: "/",
    title: "Gérez vos locations avec moins de stress",
    description: siteDescription,
  },
};

const capabilities = [
  {
    number: "01",
    title: "Vous savez exactement qui doit quoi",
    description:
      "Les échéances mensuelles sont reliées au bail, au locataire et au bien. Le solde restant est visible sans refaire les calculs.",
    items: ["Échéances mensuelles", "Retards identifiables", "Historique conservé"],
  },
  {
    number: "02",
    title: "Chaque paiement laisse une preuve",
    description:
      "Une déclaration en espèces peut être confirmée par le locataire. Un paiement Mobile Money authentique est validé par le fournisseur.",
    items: ["Reçu après paiement", "Quittance après solde complet", "Référence vérifiable"],
  },
  {
    number: "03",
    title: "Les échanges ne se perdent plus",
    description:
      "Invitations, documents et incidents restent liés au dossier locatif, même lorsque les notifications passent par plusieurs canaux.",
    items: ["Email, push, WhatsApp ou SMS", "Incidents suivis", "Historique partagé"],
  },
];

const plans = [
  {
    name: "Gratuit",
    price: "0 FCFA",
    limit: "1 bien",
    description: "Pour tester ImmoLib sur une première location.",
    features: ["Loyers, cautions et avances", "Documents vérifiables", "Partage manuel"],
  },
  {
    name: "Essentiel",
    price: "2 000 FCFA",
    limit: "Jusqu'à 5 biens",
    description: "Pour automatiser le suivi courant d'un petit patrimoine.",
    features: ["Rappels de paiement mensuels", "Copropriétaires", "Email et notifications push", "Historique complet"],
    highlighted: true,
  },
  {
    name: "Pro",
    price: "4 000 FCFA",
    limit: "Jusqu'à 15 biens",
    description: "Pour un bailleur qui pilote plusieurs locations.",
    features: ["Rappels automatisés", "Exports et rapports", "Statistiques avancées", "Assistance prioritaire"],
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      <header className="sticky top-0 z-40 border-b border-line bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-[72px] max-w-7xl items-center justify-between gap-5 px-4 sm:px-7">
          <Brand />
          <nav
            aria-label="Navigation publique"
            className="hidden items-center gap-7 lg:flex"
          >
            <a className="text-sm font-medium text-muted hover:text-ink" href="#services">
              Services
            </a>
            <a className="text-sm font-medium text-muted hover:text-ink" href="#fonctionnement">
              Comment ça marche
            </a>
            <a className="text-sm font-medium text-muted hover:text-ink" href="#tarifs">
              Tarifs
            </a>
            <Link
              className="text-sm font-medium text-muted hover:text-ink"
              href="/verifier-quittance"
            >
              Vérifier une quittance
            </Link>
          </nav>
          <div className="flex items-center gap-2">
            <Link className="hidden text-sm font-semibold text-ink sm:block sm:px-3" href="/connexion">
              Connexion
            </Link>
            <Link className="primary-button" href="/inscription">
              <span className="hidden sm:inline">Créer un compte</span>
              <span className="sm:hidden">Créer</span>
              <ArrowRight aria-hidden="true" size={17} />
            </Link>
            <details className="relative lg:hidden">
              <summary className="grid size-11 cursor-pointer list-none place-items-center rounded-[10px] border border-line text-ink">
                <span className="sr-only">Ouvrir la navigation</span>
                <Menu aria-hidden="true" size={19} />
              </summary>
              <nav
                aria-label="Navigation mobile"
                className="absolute right-0 top-[calc(100%+0.5rem)] w-64 rounded-[12px] border border-line bg-white p-2 shadow-[0_16px_36px_rgba(18,16,18,0.12)]"
              >
                <a className="block rounded-[8px] px-3 py-2.5 text-sm font-medium text-ink hover:bg-canvas" href="#services">
                  Services
                </a>
                <a className="block rounded-[8px] px-3 py-2.5 text-sm font-medium text-ink hover:bg-canvas" href="#fonctionnement">
                  Comment ça marche
                </a>
                <a className="block rounded-[8px] px-3 py-2.5 text-sm font-medium text-ink hover:bg-canvas" href="#tarifs">
                  Tarifs
                </a>
                <Link className="block rounded-[8px] px-3 py-2.5 text-sm font-medium text-ink hover:bg-canvas" href="/verifier-quittance">
                  Vérifier une quittance
                </Link>
                <Link className="block rounded-[8px] px-3 py-2.5 text-sm font-medium text-ink hover:bg-canvas sm:hidden" href="/connexion">
                  Connexion
                </Link>
              </nav>
            </details>
          </div>
        </div>
      </header>

      <main id="contenu-principal">
        <section className="border-b border-line bg-canvas">
          <div className="mx-auto grid max-w-7xl gap-12 px-4 py-16 sm:px-7 sm:py-24 lg:grid-cols-[minmax(0,0.92fr)_minmax(480px,1.08fr)] lg:items-center lg:py-28">
            <div>
              <div className="mb-7 flex w-fit items-center gap-2 rounded-full border border-line bg-white px-3 py-1.5 text-xs font-semibold text-ink">
                <span className="size-2 rounded-full bg-brand" />
                Gestion locative pensée pour les biens
              </div>
              <h1 className="max-w-3xl text-[2.75rem] font-semibold leading-[1.02] tracking-[-0.06em] text-ink sm:text-6xl lg:text-[4.35rem]">
                Gérez vos locations avec des faits, pas des souvenirs.
              </h1>
              <p className="mt-6 max-w-xl text-base leading-7 text-muted sm:text-lg">
                ImmoLib transforme chaque bail, loyer, paiement et incident en
                une information claire que le bailleur et le locataire peuvent
                retrouver au bon moment.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link className="primary-button px-5" href="/inscription">
                  Ajouter mon premier bien
                  <ArrowRight aria-hidden="true" size={17} />
                </Link>
                <a className="secondary-button px-5" href="#services">
                  Découvrir ImmoLib
                </a>
              </div>
              <ul className="mt-7 flex flex-wrap gap-x-6 gap-y-3 text-sm text-muted">
                <li className="flex items-center gap-2">
                  <Check className="text-brand" size={16} />
                  Pas de portefeuille interne
                </li>
                <li className="flex items-center gap-2">
                  <Check className="text-brand" size={16} />
                  Données séparées par rôle
                </li>
                <li className="flex items-center gap-2">
                  <Check className="text-brand" size={16} />
                  Documents vérifiables
                </li>
              </ul>
            </div>

            <div className="relative">
              <div className="overflow-hidden rounded-[18px] border border-[#d8d1cd] bg-white shadow-[0_24px_70px_rgba(18,16,18,0.12)]">
                <div className="flex items-center justify-between border-b border-line px-5 py-4">
                  <div className="flex items-center gap-2.5">
                    <span className="grid size-8 place-items-center rounded-[8px] bg-brand text-white">
                      <House size={16} />
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-ink">Tableau de bord</p>
                      <p className="text-[10px] text-muted">Suivi de votre patrimoine</p>
                    </div>
                  </div>
                  <span className="rounded-full border border-line px-2.5 py-1 text-[10px] font-semibold text-muted">
                    Données du compte
                  </span>
                </div>
                <div className="grid gap-4 p-5 sm:grid-cols-3">
                  <div className="rounded-[11px] border border-line p-4">
                    <p className="text-[10px] uppercase tracking-[0.08em] text-muted">Loyers</p>
                    <p className="mt-2 text-lg font-semibold text-ink">Suivis</p>
                    <p className="mt-2 text-[10px] text-muted">Échéances centralisées</p>
                  </div>
                  <div className="rounded-[11px] border border-line p-4">
                    <p className="text-[10px] uppercase tracking-[0.08em] text-muted">Paiements</p>
                    <p className="mt-2 text-lg font-semibold text-ink">Traçables</p>
                    <p className="mt-2 text-[10px] text-muted">Historique vérifiable</p>
                  </div>
                  <div className="rounded-[11px] border border-line p-4">
                    <p className="text-[10px] uppercase tracking-[0.08em] text-muted">Biens</p>
                    <p className="mt-2 text-lg font-semibold text-ink">Organisées</p>
                    <p className="mt-2 text-[10px] text-muted">Un dossier par bien</p>
                  </div>
                </div>
                <div className="grid gap-4 px-5 pb-5 md:grid-cols-[1.2fr_0.8fr]">
                  <div className="rounded-[11px] border border-line p-4">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-semibold text-ink">Flux mensuel</p>
                      <p className="text-[10px] text-muted">Vue synthétique</p>
                    </div>
                    <div className="mt-6 space-y-4">
                      {[
                        ["Échéances générées", "Prêtes à être suivies"],
                        ["Paiements rapprochés", "Confirmés ou à vérifier"],
                        ["Quittances disponibles", "Partageables par lien sécurisé"],
                      ].map(([label, detail]) => (
                        <div className="flex items-center gap-3" key={label}>
                          <span className="size-2.5 shrink-0 rounded-full bg-brand" />
                          <div className="min-w-0">
                            <p className="text-xs font-medium text-ink">{label}</p>
                            <p className="mt-0.5 text-[10px] text-muted">{detail}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-[11px] border border-line">
                    <div className="border-b border-line px-4 py-3">
                      <p className="text-xs font-semibold text-ink">Dernières activités</p>
                    </div>
                    <div className="divide-y divide-line px-4">
                      <div className="flex gap-3 py-3">
                        <BadgeCheck className="mt-0.5 text-brand" size={16} />
                        <div>
                          <p className="text-xs font-medium text-ink">Quittance générée</p>
                          <p className="mt-0.5 text-[10px] text-muted">Document traçable</p>
                        </div>
                      </div>
                      <div className="flex gap-3 py-3">
                        <HandCoins className="mt-0.5 text-ink" size={16} />
                        <div>
                          <p className="text-xs font-medium text-ink">Paiement confirmé</p>
                          <p className="mt-0.5 text-[10px] text-muted">Réconciliation automatique</p>
                        </div>
                      </div>
                      <div className="flex gap-3 py-3">
                        <Wrench className="mt-0.5 text-ink" size={16} />
                        <div>
                          <p className="text-xs font-medium text-ink">Incident pris en compte</p>
                          <p className="mt-0.5 text-[10px] text-muted">Historique partagé</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="absolute -bottom-5 -left-3 flex items-center gap-3 rounded-[12px] border border-line bg-white px-4 py-3 shadow-[0_14px_35px_rgba(18,16,18,0.12)] sm:-left-8">
                <span className="grid size-9 place-items-center rounded-full bg-[#edf5ef] text-[#275c3b]">
                  <ShieldCheck size={18} />
                </span>
                <div>
                  <p className="text-xs font-semibold text-ink">Quittance authentique</p>
                  <p className="mt-0.5 text-[10px] text-muted">Référence vérifiée</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-b border-line bg-white">
          <div className="mx-auto grid max-w-7xl divide-y divide-line px-4 sm:px-7 md:grid-cols-3 md:divide-x md:divide-y-0">
            <div className="py-7 md:pr-8">
              <p className="text-sm font-semibold text-ink">Une seule source de vérité</p>
              <p className="mt-1 text-sm text-muted">Pour le bail, le loyer et les preuves.</p>
            </div>
            <div className="py-7 md:px-8">
              <p className="text-sm font-semibold text-ink">Chaque rôle voit ce qui le concerne</p>
              <p className="mt-1 text-sm text-muted">Bailleur, copropriétaire ou locataire.</p>
            </div>
            <div className="py-7 md:pl-8">
              <p className="text-sm font-semibold text-ink">Les fonds restent chez le fournisseur</p>
              <p className="mt-1 text-sm text-muted">ImmoLib organise la preuve, pas l’argent.</p>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-20 sm:px-7 sm:py-28" id="services">
          <div className="grid gap-8 border-b border-line pb-12 lg:grid-cols-[0.75fr_1.25fr]">
            <p className="eyebrow">Pourquoi ImmoLib</p>
            <div>
              <h2 className="max-w-3xl text-3xl font-semibold tracking-[-0.045em] text-ink sm:text-5xl">
                Moins de discussions floues. Plus d’informations que chacun peut vérifier.
              </h2>
              <p className="mt-5 max-w-2xl text-base leading-7 text-muted">
                Le cahier, les captures d’écran et les messages dispersés ne
                suffisent pas pour suivre une location dans le temps. ImmoLib
                garde le contexte de chaque action.
              </p>
            </div>
          </div>

          <div className="divide-y divide-line">
            {capabilities.map((capability) => (
              <article
                className="grid gap-7 py-10 md:grid-cols-[80px_minmax(0,0.9fr)_minmax(300px,0.7fr)] md:items-start"
                key={capability.number}
              >
                <p className="font-mono text-sm text-brand">{capability.number}</p>
                <div>
                  <h3 className="text-2xl font-semibold tracking-[-0.035em] text-ink">
                    {capability.title}
                  </h3>
                  <p className="mt-3 max-w-2xl text-sm leading-7 text-muted">
                    {capability.description}
                  </p>
                </div>
                <ul className="space-y-3">
                  {capability.items.map((item) => (
                    <li className="flex items-center gap-3 text-sm font-medium text-ink" key={item}>
                      <Check className="text-brand" size={16} />
                      {item}
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>

        <section className="border-y border-line bg-canvas" id="fonctionnement">
          <div className="mx-auto max-w-7xl px-4 py-20 sm:px-7 sm:py-24">
            <div className="grid gap-10 lg:grid-cols-[0.85fr_1.15fr]">
              <div>
                <p className="eyebrow">Un démarrage guidé</p>
                <h2 className="text-3xl font-semibold tracking-[-0.045em] text-ink sm:text-4xl">
                  Du bien à la première quittance.
                </h2>
                <p className="mt-4 max-w-lg text-sm leading-7 text-muted">
                  Vous construisez le dossier dans l’ordre naturel de la
                  location. ImmoLib relie ensuite les opérations entre elles.
                </p>
                <Link className="primary-button mt-7" href="/inscription">
                  Commencer maintenant
                  <ArrowRight size={17} />
                </Link>
              </div>
              <ol className="divide-y divide-line border-y border-line">
                {[
                  ["1", "Ajoutez le bien", "Adresse, repère et éventuels copropriétaires."],
                  ["2", "Créez le bail", "Locataire, montant, date et moyens de paiement."],
                  ["3", "Suivez chaque mois", "Échéance, paiement, reçu et quittance restent liés."],
                ].map(([number, title, description]) => (
                  <li className="grid grid-cols-[44px_1fr] gap-4 py-6" key={number}>
                    <span className="grid size-8 place-items-center rounded-full border border-line bg-white text-xs font-semibold text-brand">
                      {number}
                    </span>
                    <div>
                      <p className="font-semibold text-ink">{title}</p>
                      <p className="mt-1 text-sm leading-6 text-muted">{description}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>

        <section className="mx-auto grid max-w-7xl gap-5 px-4 py-20 sm:px-7 sm:py-24 lg:grid-cols-2">
          <article className="rounded-[16px] border border-line bg-white p-7 sm:p-9">
            <span className="grid size-10 place-items-center rounded-[9px] bg-canvas text-ink">
              <Building2 size={19} />
            </span>
            <p className="mt-7 text-xs font-semibold uppercase tracking-[0.12em] text-muted">
              Pour le bailleur
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-ink">
              Une vision nette de chaque bien.
            </h2>
            <p className="mt-4 text-sm leading-7 text-muted">
              Voyez ce qui est attendu, reçu, contesté ou en retard. Partagez
              les documents et traitez les incidents depuis le même dossier.
            </p>
            <Link className="text-link mt-6" href="/inscription">
              Créer mon espace bailleur <ArrowRight size={16} />
            </Link>
          </article>
          <article className="rounded-[16px] border border-line bg-ink p-7 text-white sm:p-9">
            <span className="grid size-10 place-items-center rounded-[9px] bg-white/10 text-white">
              <Users size={19} />
            </span>
            <p className="mt-7 text-xs font-semibold uppercase tracking-[0.12em] text-white/55">
              Pour le locataire
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em]">
              Ses paiements et preuves restent accessibles.
            </h2>
            <p className="mt-4 text-sm leading-7 text-white/65">
              Même sans compte au départ, le locataire peut recevoir un lien
              sécurisé. Une fois inscrit, il retrouve son dossier locatif.
            </p>
            <Link className="mt-6 inline-flex items-center gap-1.5 text-sm font-semibold text-white" href="/connexion">
              Accéder à mon espace <ArrowRight size={16} />
            </Link>
          </article>
        </section>

        <section className="border-y border-line bg-canvas" id="tarifs">
          <div className="mx-auto max-w-7xl px-4 py-20 sm:px-7 sm:py-24">
            <div className="grid gap-8 lg:grid-cols-[0.7fr_1.3fr]">
              <div>
                <p className="eyebrow">Tarifs transparents</p>
                <h2 className="text-3xl font-semibold tracking-[-0.045em] text-ink sm:text-4xl">
                  Le bailleur choisit l’offre. Le locataire ne paie pas ImmoLib.
                </h2>
              </div>
              <p className="max-w-2xl text-sm leading-7 text-muted lg:pt-7">
                L’abonnement dépend du nombre de biens actifs, jamais du
                montant du loyer. Les SMS et les messages WhatsApp automatisés
                resteront des options à la consommation afin d’éviter de
                gonfler le prix de base.
              </p>
            </div>

            <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {plans.map((plan) => (
                <article
                  className={`rounded-[16px] border p-6 ${
                    plan.highlighted
                      ? "border-brand bg-white shadow-[0_18px_45px_rgba(18,16,18,0.08)]"
                      : "border-line bg-white"
                  }`}
                  key={plan.name}
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="font-semibold text-ink">{plan.name}</p>
                    {plan.highlighted ? (
                      <span className="rounded-full bg-brand-soft px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.08em] text-brand-dark">
                        Recommandé
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-5 text-2xl font-semibold tracking-[-0.04em] text-ink">
                    {plan.price}
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    {plan.price === "0 FCFA" ? "sans limite de durée" : "par mois"}
                  </p>
                  <p className="mt-5 text-sm font-semibold text-ink">{plan.limit}</p>
                  <p className="mt-2 min-h-12 text-sm leading-6 text-muted">
                    {plan.description}
                  </p>
                  <ul className="mt-5 space-y-3 border-t border-line pt-5">
                    {plan.features.map((feature) => (
                      <li className="flex gap-2 text-sm text-ink" key={feature}>
                        <Check className="mt-0.5 shrink-0 text-brand" size={15} />
                        {feature}
                      </li>
                    ))}
                  </ul>
                  <Link
                    className={plan.highlighted ? "primary-button mt-6 w-full" : "secondary-button mt-6 w-full"}
                    href="/inscription"
                  >
                    Commencer
                  </Link>
                </article>
              ))}
            </div>
            <p className="mt-5 text-xs leading-5 text-muted">
              Tarifs de lancement à valider pendant le pilote. Aucun
              prélèvement sur les loyers et aucune vente de données.
            </p>
          </div>
        </section>

        <section className="border-y border-line bg-canvas">
          <div className="mx-auto grid max-w-7xl gap-10 px-4 py-20 sm:px-7 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
            <div>
              <span className="grid size-11 place-items-center rounded-[10px] border border-line bg-white text-ink">
                <Search size={20} />
              </span>
              <p className="eyebrow mt-6">Contrôle public</p>
              <h2 className="text-3xl font-semibold tracking-[-0.045em] text-ink">
                Une quittance peut être vérifiée sans compte.
              </h2>
              <p className="mt-4 max-w-lg text-sm leading-7 text-muted">
                Saisissez la référence inscrite sur le document. ImmoLib indique
                s’il existe et s’il est toujours actif, sans afficher les
                coordonnées privées.
              </p>
            </div>
            <form
              action="/verifier-quittance"
              className="rounded-[14px] border border-line bg-white p-5 sm:p-7"
              method="get"
            >
              <label htmlFor="landing-reference">
                <span className="form-label">Numéro du reçu ou de la quittance</span>
                <div className="flex flex-col gap-3 sm:flex-row">
                  <input
                    autoComplete="off"
                    className="form-input font-mono uppercase"
                    id="landing-reference"
                    name="reference"
                    placeholder="IMM-QUT-2026-…"
                    required
                  />
                  <button className="primary-button shrink-0" type="submit">
                    Vérifier
                    <ArrowRight size={17} />
                  </button>
                </div>
              </label>
              <p className="mt-3 text-xs text-muted">
                La référence complète figure sur chaque document généré par ImmoLib.
              </p>
            </form>
          </div>
        </section>

        <section className="mx-auto max-w-4xl px-4 py-20 text-center sm:px-7 sm:py-28">
          <FileCheck2 className="mx-auto text-brand" size={28} />
          <h2 className="mt-6 text-4xl font-semibold tracking-[-0.05em] text-ink sm:text-5xl">
            Commencez par un bien. Gardez une gestion claire en grandissant.
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-base leading-7 text-muted">
            Créez votre espace et posez une base propre pour les prochains
            loyers, documents et échanges avec le locataire.
          </p>
          <Link className="primary-button mt-8 px-6" href="/inscription">
            Ajouter mon premier bien
            <ArrowRight size={17} />
          </Link>
        </section>
      </main>

      <footer className="border-t border-line bg-white">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:px-7 md:grid-cols-[1fr_auto] md:items-end">
          <div>
            <Brand />
            <p className="mt-4 max-w-sm text-sm leading-6 text-muted">
              Gestion locative claire pour les biens, leurs bailleurs et leurs
              locataires.
            </p>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-3 text-sm font-medium text-muted">
            <Link href="/connexion">Connexion</Link>
            <Link href="/inscription">Créer un compte</Link>
            <Link href="/verifier-quittance">Vérifier une quittance</Link>
          </div>
          <p className="border-t border-line pt-5 text-xs text-muted md:col-span-2">
            © 2026 ImmoLib. Tous droits réservés.
          </p>
        </div>
      </footer>
    </div>
  );
}
