"use client";

import {
  Check,
  CreditCard,
  ExternalLink,
  House,
  LoaderCircle,
  ShieldCheck,
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { Feedback } from "@/components/ui/feedback";
import { ModuleHeader } from "@/components/ui/module-header";
import { formatDate, formatMoney } from "@/lib/format";

interface Plan {
  id: string;
  name: string;
  slug: string;
  description: string;
  price: number;
  currency: string;
  interval: string;
  max_houses: number;
  features: string[];
  is_highlighted: boolean;
}

interface Subscription {
  id: string;
  plan: Plan;
  status: string;
  max_houses: number;
  current_period_start: string;
  current_period_end: string;
}

export function SubscriptionWorkspace() {
  const { user } = useAuth();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchPlans(), fetchSubscription()])
      .then(([plansData, subData]) => {
        setPlans(plansData);
        setSubscription(subData);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function fetchPlans(): Promise<Plan[]> {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "/backend"}/api/v1/subscriptions/plans/`, {
      credentials: "include",
    });
    if (!res.ok) throw new Error("Erreur lors du chargement des plans");
    return res.json();
  }

  async function fetchSubscription(): Promise<Subscription> {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "/backend"}/api/v1/subscriptions/current/`, {
      credentials: "include",
    });
    if (!res.ok) throw new Error("Erreur lors du chargement de l'abonnement");
    return res.json();
  }

  async function handleSubscribe(planId: string) {
    setPaying(true);
    setError(null);
    setFeedback(null);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "/backend"}/api/v1/subscriptions/pay/`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({ plan_id: planId }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Erreur lors de la création du paiement");
      }

      const data = await res.json();

      // Rediriger vers PayDunya
      if (data.payment_url) {
        window.location.href = data.payment_url;
      }
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Paiement impossible");
    } finally {
      setPaying(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-5">
        <div className="h-28 animate-pulse rounded-2xl bg-white" />
        <div className="grid gap-4 md:grid-cols-3">
          {[0, 1, 2].map((item) => (
            <div className="metric-card h-40 animate-pulse" key={item} />
          ))}
        </div>
      </div>
    );
  }

  const currentPlan = subscription?.plan;
  const isActive = subscription?.status === "ACTIVE";

  return (
    <div className="space-y-7">
      <ModuleHeader
        description="Gérez votre abonnement et le nombre de maisons que vous pouvez suivre."
        eyebrow="Abonnement"
        title="Mon plan"
      />
      <Feedback message={feedback} />
      <Feedback message={error} tone="error" />

      {/* Plan actuel */}
      {subscription && (
        <section className="rounded-[14px] border border-brand bg-white p-6">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <div>
              <div className="flex items-center gap-3">
                <span className="grid size-10 place-items-center rounded-xl bg-brand text-white">
                  <ShieldCheck size={19} />
                </span>
                <div>
                  <p className="font-bold text-ink">{currentPlan?.name}</p>
                  <p className="text-sm text-muted">
                    {currentPlan?.price === 0
                      ? "Plan gratuit"
                      : `${formatMoney(currentPlan?.price || 0, currentPlan?.currency || "XOF")}/${currentPlan?.interval === "YEARLY" ? "an" : "mois"}`}
                  </p>
                </div>
              </div>
              <div className="mt-4 flex items-center gap-4 text-sm text-muted">
                <span className="flex items-center gap-1.5">
                  <House size={15} />
                  {subscription.max_houses} maison{subscription.max_houses > 1 ? "s" : ""} max
                </span>
                <span>•</span>
                <span>Expire le {formatDate(subscription.current_period_end)}</span>
              </div>
            </div>
            <span className={`status-pill ${isActive ? "status-paid" : "status-partial"}`}>
              {isActive ? "Actif" : subscription.status}
            </span>
          </div>
        </section>
      )}

      {/* Plans disponibles */}
      <section>
        <p className="mb-4 text-sm font-semibold text-ink">Changer de plan</p>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {plans.map((plan) => {
            const isCurrent = currentPlan?.id === plan.id;
            return (
              <article
                className={`rounded-[16px] border p-6 ${
                  plan.is_highlighted
                    ? "border-brand bg-white shadow-[0_18px_45px_rgba(18,16,18,0.08)]"
                    : "border-line bg-white"
                } ${isCurrent ? "ring-2 ring-brand/30" : ""}`}
                key={plan.id}
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="font-semibold text-ink">{plan.name}</p>
                  {plan.is_highlighted ? (
                    <span className="rounded-full bg-brand-soft px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.08em] text-brand-dark">
                      Recommandé
                    </span>
                  ) : null}
                  {isCurrent ? (
                    <span className="rounded-full bg-green-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.08em] text-green-700">
                      Actuel
                    </span>
                  ) : null}
                </div>
                <p className="mt-5 text-2xl font-semibold tracking-[-0.04em] text-ink">
                  {plan.price === 0 ? "Gratuit" : formatMoney(plan.price, plan.currency)}
                </p>
                <p className="mt-1 text-xs text-muted">
                  {plan.price === 0 ? "pour toujours" : `par ${plan.interval === "YEARLY" ? "an" : "mois"}`}
                </p>
                <p className="mt-5 text-sm font-semibold text-ink">
                  {plan.max_houses} maison{plan.max_houses > 1 ? "s" : ""}
                </p>
                <ul className="mt-5 space-y-3 border-t border-line pt-5">
                  {plan.features.map((feature) => (
                    <li className="flex gap-2 text-sm text-ink" key={feature}>
                      <Check className="mt-0.5 shrink-0 text-brand" size={15} />
                      {feature}
                    </li>
                  ))}
                </ul>
                {isCurrent ? (
                  <button
                    className="secondary-button mt-6 w-full"
                    disabled
                    type="button"
                  >
                    Plan actuel
                  </button>
                ) : plan.price === 0 ? (
                  <button
                    className="secondary-button mt-6 w-full"
                    disabled
                    type="button"
                  >
                    Gratuit
                  </button>
                ) : (
                  <button
                    className={plan.is_highlighted ? "primary-button mt-6 w-full" : "secondary-button mt-6 w-full"}
                    disabled={paying}
                    onClick={() => handleSubscribe(plan.id)}
                    type="button"
                  >
                    {paying ? (
                      <LoaderCircle aria-hidden="true" className="animate-spin" size={18} />
                    ) : (
                      <CreditCard aria-hidden="true" size={18} />
                    )}
                    {paying ? "Redirection…" : "Souscrire"}
                  </button>
                )}
              </article>
            );
          })}
        </div>
      </section>

      {/* Info sécurité */}
      <section className="rounded-[14px] border border-line bg-canvas p-5 text-sm text-muted">
        <p className="flex items-center gap-2 font-bold text-ink">
          <ShieldCheck size={18} />
          Paiement sécurisé par PayDunya
        </p>
        <p className="mt-2">
          Les paiements sont traités par PayDunya via Mobile Money, carte bancaire
          ou autres moyens disponibles. ImmoLib ne stocke aucune information
          de paiement.
        </p>
      </section>
    </div>
  );
}

function getCookie(name: string): string {
  const cookies = document.cookie.split(";");
  for (const cookie of cookies) {
    const [key, value] = cookie.trim().split("=");
    if (key === name) return value;
  }
  return "";
}
