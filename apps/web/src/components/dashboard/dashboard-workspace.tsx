"use client";

import {
  ArrowRight,
  BadgeCheck,
  CalendarClock,
  House,
  LoaderCircle,
  ReceiptText,
  RefreshCw,
  TrendingUp,
  WalletCards,
} from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { Feedback } from "@/components/ui/feedback";
import { getDashboardOverview } from "@/lib/api-client";
import { formatDate, formatMoney, monthLabel } from "@/lib/format";
import type { DashboardOverview, Payment, RentCharge } from "@/types/domain";

const RentCollectionChart = dynamic(
  () =>
    import("@/components/dashboard/rent-collection-chart").then(
      (module) => module.RentCollectionChart,
    ),
  {
    loading: () => (
      <div
        aria-label="Chargement du graphique des encaissements"
        className="h-[308px] animate-pulse rounded-[10px] bg-canvas"
        role="status"
      />
    ),
    ssr: false,
  },
);

const chargeStatusStyle: Record<RentCharge["status"], string> = {
  PAID: "status-paid",
  PARTIALLY_PAID: "status-partial",
  UPCOMING: "status-vacant",
  DUE: "status-partial",
  OVERDUE: "bg-red-50 text-red-700",
  DISPUTED: "bg-red-50 text-red-700",
  CANCELLED: "bg-zinc-100 text-zinc-700",
};

const paymentStatusStyle: Record<Payment["status"], string> = {
  RECORDED_BY_OWNER: "status-partial",
  CONFIRMED_BY_TENANT: "status-paid",
  CONFIRMED_BY_PROVIDER: "status-paid",
  DISPUTED_BY_TENANT: "bg-red-50 text-red-700",
  CANCELLED: "bg-zinc-100 text-zinc-700",
};

export function DashboardWorkspace() {
  const { user } = useAuth();
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getDashboardOverview()
      .then((loadedOverview) => {
        if (!active) return;
        setOverview(loadedOverview);
      })
      .catch((caughtError) => {
        if (active) {
          setError(
            caughtError instanceof Error
              ? caughtError.message
              : "Impossible de charger le tableau de bord.",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const period = overview?.period ?? "";
  const totals = overview?.collection;
  const highlightedCharges = overview?.priority_charges ?? [];
  const recentPayments = overview?.recent_payments ?? [];

  async function refreshDashboard() {
    setLoading(true);
    setError(null);
    try {
      setOverview(await getDashboardOverview());
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible d’actualiser le tableau de bord.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-7">
      <section className="flex flex-col justify-between gap-5 xl:flex-row xl:items-end">
        <div>
          <p className="eyebrow">Vue d’ensemble</p>
          <h1 className="page-title">
            {user?.first_name ? `Bonjour ${user.first_name},` : "Bonjour,"} voici vos
            locations.
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted sm:text-base">
            Suivez les loyers, les échéances et les documents de vos biens en un
            seul endroit.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button className="secondary-button" disabled={loading} onClick={refreshDashboard} type="button">
            <RefreshCw aria-hidden="true" className={loading ? "animate-spin" : ""} size={17} />
            Actualiser
          </button>
          <Link className="primary-button w-fit" href="/maisons">
            <House aria-hidden="true" size={18} />
            Ajouter un bien
          </Link>
        </div>
      </section>

      <Feedback message={error} tone="error" />

      {loading ? (
        <section aria-label="Chargement du tableau de bord" className="grid gap-4 md:grid-cols-3">
          {[0, 1, 2].map((item) => (
            <div className="metric-card animate-pulse" key={item}>
              <div className="size-10 rounded-xl bg-line" />
              <div className="mt-5 h-4 w-28 rounded bg-line" />
              <div className="mt-3 h-8 w-40 rounded bg-line" />
            </div>
          ))}
          <p className="flex items-center gap-2 text-sm font-semibold text-muted md:col-span-3"><LoaderCircle aria-hidden="true" className="animate-spin" size={17} />Calcul de votre synthèse…</p>
        </section>
      ) : overview && totals ? (
        <>
          <section aria-label="Indicateurs du mois" className="grid gap-4 md:grid-cols-3">
            <article className="metric-card">
              <div className="metric-icon"><WalletCards aria-hidden="true" size={19} /></div>
              <p className="metric-label">Loyers encaissés</p>
              <p className="metric-value">{formatMoney(totals.collected)}</p>
              <p className="metric-detail text-muted"><TrendingUp aria-hidden="true" size={15} />{totals.rate}% des {formatMoney(totals.expected)} attendus</p>
            </article>

            <article className="metric-card">
              <div className="metric-icon"><CalendarClock aria-hidden="true" size={19} /></div>
              <p className="metric-label">Reste à encaisser</p>
              <p className="metric-value">{formatMoney(totals.remaining)}</p>
              <p className="metric-detail text-muted">{totals.attention_count ? `${totals.attention_count} échéance(s) demandent votre attention` : "Aucune échéance en difficulté"}</p>
            </article>

            <article className="metric-card">
              <div className="metric-icon"><House aria-hidden="true" size={19} /></div>
              <p className="metric-label">Biens occupés</p>
              <p className="metric-value">{overview.houses.occupied} / {overview.houses.total}</p>
              <p className="metric-detail text-muted">{overview.houses.vacant ? `${overview.houses.vacant} bien(s) disponible(s)` : overview.houses.total ? "Tous les biens sont occupés" : "Ajoutez votre premier bien"}</p>
            </article>
          </section>

          <section aria-label="Votre abonnement" className="panel flex flex-col justify-between gap-4 p-5 sm:flex-row sm:items-center sm:p-6">
            <div className="flex items-start gap-4">
              <span className="grid size-11 shrink-0 place-items-center rounded-[10px] bg-brand-soft text-brand-dark">
                <BadgeCheck aria-hidden="true" size={22} />
              </span>
              <div>
                <p className="font-bold text-ink">
                  Plan {user?.subscription?.plan_name ?? "Gratuit"}
                </p>
                <p className="mt-1 text-sm leading-5 text-muted">
                  {user?.subscription
                    ? `${user.subscription.house_count} bien${user.subscription.house_count > 1 ? "s" : ""} sur ${user.subscription.max_houses ?? "—"} inclus${(user.subscription.max_houses ?? 1) > 1 ? "s" : ""}`
                    : "Abonnement non disponible"}
                </p>
              </div>
            </div>
            <Link className="secondary-button w-fit" href="/abonnement">
              Gérer mon abonnement <ArrowRight aria-hidden="true" size={16} />
            </Link>
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.8fr)]">
            <article className="panel p-5 sm:p-6">
              <p className="section-kicker">Encaissements</p>
              <h2 className="section-title">Attendu et encaissé</h2>
              <div className="mt-5">
                <RentCollectionChart data={overview.monthly_collection} />
              </div>
            </article>

            <aside className="panel p-5 sm:p-6">
              <p className="section-kicker">À faire</p>
              <h2 className="section-title">Actions rapides</h2>
              <div className="mt-5 space-y-2">
                <Link className="action-row" href="/paiements"><span className="action-icon"><WalletCards aria-hidden="true" size={18} /></span><span className="min-w-0 flex-1"><span className="block font-semibold text-ink">Enregistrer un paiement</span><span className="mt-0.5 block text-sm text-muted">Espèces ou virement</span></span><ArrowRight aria-hidden="true" className="text-muted" size={17} /></Link>
                <Link className="action-row" href="/baux"><span className="action-icon"><ReceiptText aria-hidden="true" size={18} /></span><span className="min-w-0 flex-1"><span className="block font-semibold text-ink">Créer un bail</span><span className="mt-0.5 block text-sm text-muted">Associer bien et locataire</span></span><ArrowRight aria-hidden="true" className="text-muted" size={17} /></Link>
                <Link className="action-row" href="/documents"><span className="action-icon"><BadgeCheck aria-hidden="true" size={18} /></span><span className="min-w-0 flex-1"><span className="block font-semibold text-ink">Voir les quittances</span><span className="mt-0.5 block text-sm text-muted">Documents prêts à envoyer</span></span><ArrowRight aria-hidden="true" className="text-muted" size={17} /></Link>
              </div>
            </aside>
          </section>

          <section className="grid gap-5">
            <article className="panel overflow-hidden">
              <div className="panel-heading">
                <div><p className="section-kicker capitalize">{monthLabel(period)}</p><h2 className="section-title">État des échéances</h2></div>
                <Link className="text-link" href="/echeances">Tout voir <ArrowRight aria-hidden="true" size={16} /></Link>
              </div>
              {highlightedCharges.length ? (
                <div className="divide-y divide-line">
                  {highlightedCharges.map((charge) => (
                    <div className="grid gap-3 px-5 py-4 sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-center sm:px-6" key={charge.id}>
                      <div className="min-w-0"><p className="truncate font-semibold text-ink">{charge.tenant_name}</p><p className="mt-0.5 truncate text-sm text-muted">{charge.house_name}</p></div>
                      <div className="sm:text-right"><p className="font-semibold text-ink">{formatMoney(charge.amount_due)}</p><p className="mt-0.5 text-xs text-muted">Solde {formatMoney(charge.balance_due)} · {formatDate(charge.due_date)}</p></div>
                      <span className={`status-pill ${chargeStatusStyle[charge.status]}`}>{charge.status_label}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="px-5 py-14 text-center"><p className="font-bold text-ink">Aucune échéance pour {monthLabel(period)}</p><p className="mt-1 text-sm text-muted">Créez un bail actif, puis générez les échéances du mois.</p><Link className="secondary-button mt-5" href="/echeances">Ouvrir les échéances</Link></div>
              )}
            </article>

          </section>

          <section className="panel overflow-hidden">
            <div className="panel-heading"><div><p className="section-kicker">Historique</p><h2 className="section-title">Derniers paiements</h2></div><Link className="text-link" href="/paiements">Consulter <ArrowRight aria-hidden="true" size={16} /></Link></div>
            {recentPayments.length ? (
              <div className="overflow-x-auto">
                <table className="data-table min-w-[820px]">
                  <thead><tr><th>Locataire</th><th>Bien</th><th>Moyen</th><th>Statut</th><th>Date</th><th className="text-right">Montant</th></tr></thead>
                  <tbody>
                    {recentPayments.map((payment) => {
                      const allocation = payment.allocations[0];
                      return (
                        <tr key={payment.id}>
                          <td className="font-semibold text-ink">{allocation?.tenant_name ?? "Locataire non retrouvé"}</td>
                          <td>{allocation?.house_name ?? "Bien non retrouvé"}</td>
                          <td>{payment.method_label}</td>
                          <td><span className={`status-pill ${paymentStatusStyle[payment.status]}`}>{payment.status_label}</span></td>
                          <td>{formatDate(payment.received_at)}</td>
                          <td className="text-right font-semibold text-ink">{formatMoney(payment.amount)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="px-5 py-14 text-center"><p className="font-bold text-ink">Aucun paiement enregistré</p><p className="mt-1 text-sm text-muted">Les prochains paiements apparaîtront ici.</p></div>
            )}
          </section>
        </>
      ) : (
        <Feedback message="La synthèse du tableau de bord est indisponible." tone="error" />
      )}
    </div>
  );
}
