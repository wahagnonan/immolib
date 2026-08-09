"use client";

import {
  BadgeCheck,
  Building2,
  Check,
  CreditCard,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  cancelSubscription,
  getSubscription,
  listSubscriptionPlans,
  refreshSubscriptionTransaction,
  upgradeSubscription,
} from "@/lib/api-client";
import { formatDate, formatMoney } from "@/lib/format";
import type {
  SubscriptionDetail,
  SubscriptionPlan,
} from "@/types/domain";

const FEATURE_LABELS: Record<string, string[]> = {
  free: [
    "1 maison",
    "Loyers, cautions et avances",
    "Documents vérifiables",
    "Partage manuel",
  ],
  essential: [
    "Jusqu'à 5 maisons",
    "Rappels de paiement mensuels",
    "Copropriétaires",
    "Email et notifications push",
    "Historique complet",
  ],
  pro: [
    "Jusqu'à 15 maisons",
    "Rappels automatisés",
    "Exports et rapports",
    "Statistiques avancées",
    "Assistance prioritaire",
  ],
};

const PLAN_ORDER = ["free", "essential", "pro"];

export function SubscriptionWorkspace() {
  const [detail, setDetail] = useState<SubscriptionDetail | null>(null);
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyPlan, setBusyPlan] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);

    Promise.all([getSubscription(), listSubscriptionPlans()])
      .then(([subscriptionDetail, availablePlans]) => {
        setDetail(subscriptionDetail);
        setPlans(availablePlans);

        if (params.get("cancelled") === "1") {
          setFeedback("Votre abonnement a été annulé. Vous pouvez souscrire à nouveau à tout moment.");
        }

        const transactionId = params.get("transaction");
        if (transactionId && subscriptionDetail.pending_transaction) {
          void refreshSubscriptionTransaction(transactionId)
            .then(() => getSubscription())
            .then((refreshed) => {
              setDetail(refreshed);
              if (refreshed.status === "ACTIVE") {
                setFeedback("Paiement confirmé. Votre abonnement est actif.");
              }
            })
            .catch(() => undefined);
        } else if (params.get("activated") === "1" || params.get("success") === "1") {
          setFeedback("Paiement confirmé. Votre abonnement est actif.");
        }
      })
      .catch((caughtError) =>
        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "Impossible de charger l'abonnement.",
        ),
      )
      .finally(() => setLoading(false));
  }, []);

  const sortedPlans = useMemo(
    () =>
      [...plans].sort(
        (a, b) => PLAN_ORDER.indexOf(a.slug) - PLAN_ORDER.indexOf(b.slug),
      ),
    [plans],
  );

  const currentPlanSlug = detail?.plan.slug ?? "free";
  const remaining = detail?.remaining_houses ?? null;
  const maxHouses = detail?.max_houses ?? null;
  const usagePercent =
    maxHouses && maxHouses > 0
      ? Math.min(100, Math.round(((detail?.house_count ?? 0) / maxHouses) * 100))
      : 0;

  async function handleUpgrade(planSlug: string) {
    setBusyPlan(planSlug);
    setError(null);
    setFeedback(null);
    try {
      const result = await upgradeSubscription(planSlug);
      if (result.redirect_url) {
        window.location.assign(result.redirect_url);
        return;
      }
      setDetail(await getSubscription());
      if (result.activated) {
        setFeedback(
          `Bienvenue sur le plan ${result.transaction.plan_name}. Votre abonnement est actif.`,
        );
      }
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible de souscrire au plan.",
      );
    } finally {
      setBusyPlan(null);
    }
  }

  async function handleRefreshTransaction() {
    const transaction = detail?.pending_transaction;
    if (!transaction) return;
    setRefreshing(true);
    setError(null);
    try {
      const refreshed = await refreshSubscriptionTransaction(transaction.id);
      const updated = await getSubscription();
      setDetail(updated);
      if (refreshed.status === "SUCCESSFUL") {
        setFeedback("Paiement confirmé. Votre abonnement est actif.");
      } else if (refreshed.status === "PENDING") {
        setFeedback(
          "Le paiement est toujours en attente. Réessayez dans quelques instants.",
        );
      }
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible de vérifier le paiement.",
      );
    } finally {
      setRefreshing(false);
    }
  }

  async function handleCancel() {
    if (!window.confirm("Annuler l'abonnement ? Vous reviendrez au plan Gratuit.")) {
      return;
    }
    setBusyPlan("cancel");
    setError(null);
    setFeedback(null);
    try {
      await cancelSubscription();
      setDetail(await getSubscription());
      setFeedback("Abonnement annulé. Vous êtes revenu au plan Gratuit.");
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible d'annuler l'abonnement.",
      );
    } finally {
      setBusyPlan(null);
    }
  }

  if (loading) {
    return (
      <div className="panel px-5 py-16 text-center">
        <p className="font-bold text-ink">Chargement de l’abonnement…</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-col justify-between gap-5 xl:flex-row xl:items-end">
        <div>
          <p className="eyebrow">Compte</p>
          <h1 className="page-title">Abonnement</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted sm:text-base">
            Votre formule dépend du nombre de maisons actives, jamais du montant
            des loyers. Changez de plan à tout moment.
          </p>
        </div>
        {detail && detail.status === "ACTIVE" && detail.plan.slug !== "free" ? (
          <button
            className="secondary-button w-fit"
            disabled={busyPlan === "cancel"}
            onClick={handleCancel}
            type="button"
          >
            {busyPlan === "cancel" ? "Annulation…" : "Annuler l'abonnement"}
          </button>
        ) : null}
      </section>

      {feedback ? (
        <div className="flex items-start gap-3 rounded-[10px] border border-[#dbeadf] bg-[#edf5ef] px-4 py-3 text-sm text-[#275c3b]">
          <BadgeCheck aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
          <span>{feedback}</span>
        </div>
      ) : null}
      {error ? (
        <div className="flex items-start gap-3 rounded-[10px] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
          <span>{error}</span>
        </div>
      ) : null}

      {detail?.status === "EXPIRED" ? (
        <div className="flex items-start gap-3 rounded-[10px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800" role="alert">
          <span>
            Votre abonnement est arrivé à expiration. Vos données sont conservées :
            renouvelez pour continuer à ajouter des maisons.
          </span>
        </div>
      ) : null}

      {detail?.pending_transaction ? (
        <section className="panel flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="grid size-10 shrink-0 place-items-center rounded-[9px] bg-brand-soft text-brand-dark">
              <CreditCard aria-hidden="true" size={20} />
            </span>
            <div>
              <p className="font-bold text-ink">
                Paiement en attente : {detail.pending_transaction.plan_name}
              </p>
              <p className="mt-1 text-sm leading-5 text-muted">
                {formatMoney(detail.pending_transaction.amount)}{" "}
                {detail.pending_transaction.currency} — statut :{" "}
                {detail.pending_transaction.status_label.toLowerCase()}.
                Vérifiez après avoir effectué le paiement sur PayDunya.
              </p>
            </div>
          </div>
          <button
            className="secondary-button w-fit"
            disabled={refreshing}
            onClick={handleRefreshTransaction}
            type="button"
          >
            <RefreshCw aria-hidden="true" className={refreshing ? "animate-spin" : ""} size={16} />
            Vérifier le paiement
          </button>
        </section>
      ) : null}

      <section aria-label="Mon abonnement" className="panel grid gap-6 p-5 sm:p-6 lg:grid-cols-[1fr_1.2fr]">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.1em] text-muted">
            Mon abonnement
          </p>
          <div className="mt-4 flex items-center gap-3">
            <span className="grid size-12 place-items-center rounded-[12px] bg-brand-soft text-brand-dark">
              <ShieldCheck aria-hidden="true" size={24} />
            </span>
            <div>
              <p className="text-xl font-bold tracking-[-0.02em] text-ink">
                {detail?.plan.name}
              </p>
              <p className="text-sm text-muted">
                {formatMoney(detail?.plan.price_monthly ?? 0)}{" "}
                {detail?.plan.currency} / mois
              </p>
            </div>
          </div>
          <p className="mt-4 text-sm leading-6 text-muted">
            {detail?.plan.description ?? "Plan actuel."}
          </p>
          {detail?.expires_at ? (
            <p className="mt-3 text-sm font-semibold text-ink">
              Renouvellement le {formatDate(detail.expires_at)}
            </p>
          ) : (
            <p className="mt-3 text-sm font-semibold text-ink">
              Sans limite de durée
            </p>
          )}
        </div>

        <div>
          <div className="flex items-end justify-between gap-3">
            <p className="text-sm font-bold text-ink">
              {detail?.house_count ?? 0} maison{detail && detail.house_count > 1 ? "s" : ""}
            </p>
            <p className="text-sm text-muted">
              {maxHouses === null
                ? "Sans limite"
                : `${maxHouses} maison${maxHouses > 1 ? "s" : ""} incluse${maxHouses > 1 ? "s" : ""}`}
            </p>
          </div>
          <div
            aria-label={`Utilisation : ${usagePercent} pour cent`}
            className="mt-2 h-2.5 overflow-hidden rounded-full bg-canvas"
            role="progressbar"
            aria-valuenow={usagePercent}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className={`h-full rounded-full transition-all ${
                remaining !== null && remaining <= 0
                  ? "bg-amber-500"
                  : "bg-brand"
              }`}
              style={{ width: `${usagePercent}%` }}
            />
          </div>
          <p className="mt-2 text-xs leading-5 text-muted">
            {remaining !== null && remaining > 0
              ? `${remaining} emplacement${remaining > 1 ? "s" : ""} restant${remaining > 1 ? "s" : ""} pour ajouter une maison.`
              : remaining !== null && remaining <= 0
                ? "Quota atteint : passez au plan supérieur pour ajouter des maisons."
                : "Maisons actives dans le calcul du quota."}
          </p>
          <ul className="mt-4 grid gap-2 sm:grid-cols-2">
            {detail?.features.map((feature) => (
              <li className="flex items-center gap-2 text-sm text-ink" key={feature}>
                <Check aria-hidden="true" className="shrink-0 text-brand" size={15} />
                {FEATURE_LABELS[currentPlanSlug]?.find((label) =>
                  label.toLocaleLowerCase("fr").includes(feature.toLocaleLowerCase("fr")),
                ) ?? feature}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section aria-label="Formules disponibles" className="grid gap-4 md:grid-cols-3">
        {sortedPlans.map((plan) => {
          const isCurrent = plan.slug === currentPlanSlug;
          const isFree = plan.slug === "free";
          const highlighted = plan.slug === "essential";
          return (
            <article
              className={`rounded-[16px] border p-6 ${
                highlighted
                  ? "border-brand bg-white shadow-[0_18px_45px_rgba(18,16,18,0.08)]"
                  : "border-line bg-white"
              }`}
              key={plan.slug}
            >
              <div className="flex items-start justify-between gap-3">
                <p className="font-semibold text-ink">{plan.name}</p>
                {highlighted ? (
                  <span className="rounded-full bg-brand-soft px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.08em] text-brand-dark">
                    Recommandé
                  </span>
                ) : null}
              </div>
              <p className="mt-5 text-2xl font-semibold tracking-[-0.04em] text-ink">
                {formatMoney(plan.price_monthly)}
              </p>
              <p className="mt-1 text-xs text-muted">
                {isFree ? "sans limite de durée" : "par mois"}
              </p>
              {plan.description ? (
                <p className="mt-5 text-sm leading-6 text-muted">{plan.description}</p>
              ) : null}
              <ul className="mt-5 space-y-3 border-t border-line pt-5">
                {(FEATURE_LABELS[plan.slug] ?? plan.features).map((feature) => (
                  <li className="flex gap-2 text-sm text-ink" key={feature}>
                    <Check className="mt-0.5 shrink-0 text-brand" size={15} />
                    {feature}
                  </li>
                ))}
              </ul>
              <button
                className={
                  highlighted
                    ? "primary-button mt-6 w-full"
                    : "secondary-button mt-6 w-full"
                }
                disabled={isCurrent || busyPlan !== null}
                onClick={() => void handleUpgrade(plan.slug)}
                type="button"
              >
                {isCurrent ? (
                  <>
                    <BadgeCheck aria-hidden="true" size={16} />
                    Plan actuel
                  </>
                ) : busyPlan === plan.slug ? (
                  "Souscription…"
                ) : (
                  <>
                    <Sparkles aria-hidden="true" size={16} />
                    {isFree ? "Revenir au plan Gratuit" : `Passer à ${plan.name}`}
                  </>
                )}
              </button>
            </article>
          );
        })}
      </section>

      <p className="flex items-center gap-2 text-xs leading-5 text-muted">
        <Building2 aria-hidden="true" className="shrink-0" size={14} />
        Paiement sécurisé par PayDunya. Aucun prélèvement sur les loyers.
      </p>
    </div>
  );
}
