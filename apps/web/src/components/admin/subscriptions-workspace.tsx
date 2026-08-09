"use client";

import { Search, Settings2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AdminPagination } from "@/components/admin/admin-pagination";
import {
  AdminEmpty,
  AdminError,
  AdminLoading,
} from "@/components/admin/admin-states";
import { Feedback } from "@/components/ui/feedback";
import { Modal } from "@/components/ui/modal";
import {
  adminSubscriptionAction,
  listAdminSubscriptions,
} from "@/lib/admin-api-client";
import { formatDate } from "@/lib/format";
import type {
  AdminSubscription,
  AdminSubscriptionAction,
} from "@/types/admin";
import type { PaginatedPage } from "@/types/domain";

const PAGE_SIZE = 25;

const STATUS_LABELS: Record<string, string> = {
  TRIALING: "Essai",
  ACTIVE: "Active",
  PAST_DUE: "Impayée",
  CANCELLED: "Annulée",
  EXPIRED: "Expirée",
};

const PLAN_OPTIONS = [
  { value: "free", label: "Gratuit" },
  { value: "essential", label: "Essentiel" },
  { value: "pro", label: "Pro" },
];

function StatusPill({ status }: { status: string }) {
  switch (status) {
    case "ACTIVE":
      return <span className="status-pill status-paid">Active</span>;
    case "TRIALING":
      return <span className="status-pill bg-sky-soft text-sky-dark">Essai</span>;
    case "PAST_DUE":
      return <span className="status-pill bg-red-50 text-red-700">Impayée</span>;
    default:
      return (
        <span className="status-pill bg-zinc-100 text-zinc-700">
          {STATUS_LABELS[status] ?? status}
        </span>
      );
  }
}

export function AdminSubscriptionsWorkspace() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [plan, setPlan] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PaginatedPage<AdminSubscription> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [target, setTarget] = useState<AdminSubscription | null>(null);
  const [actionType, setActionType] = useState<"change_plan" | "extend" | "activate" | "cancel">("change_plan");
  const [planSlug, setPlanSlug] = useState("essential");
  const [days, setDays] = useState("30");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(
        await listAdminSubscriptions({
          page,
          page_size: PAGE_SIZE,
          search: search || undefined,
          status: status || undefined,
          plan: plan || undefined,
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Erreur inconnue.");
    } finally {
      setLoading(false);
    }
  }, [page, search, status, plan]);

  useEffect(() => {
    void Promise.resolve().then(load);
  }, [load]);

  function openActions(subscription: AdminSubscription) {
    setTarget(subscription);
    setActionType("change_plan");
    setPlanSlug(subscription.plan_slug === "pro" ? "pro" : "essential");
    setDays("30");
    setActionError(null);
    setActionMessage(null);
  }

  async function confirmAction() {
    if (!target) return;
    setBusy(true);
    setActionError(null);
    setActionMessage(null);
    try {
      let payload: AdminSubscriptionAction;
      switch (actionType) {
        case "change_plan":
          payload = { action: "change_plan", plan_slug: planSlug };
          break;
        case "extend": {
          const parsedDays = Number(days);
          if (!Number.isInteger(parsedDays) || parsedDays < 1) {
            throw new Error("Le nombre de jours doit être un entier positif.");
          }
          payload = { action: "extend", days: parsedDays };
          break;
        }
        case "activate": {
          const parsedDays = days ? Number(days) : undefined;
          if (days && (!Number.isInteger(parsedDays) || parsedDays! < 1)) {
            throw new Error("Le nombre de jours doit être un entier positif.");
          }
          payload = { action: "activate", plan_slug: planSlug, days: parsedDays };
          break;
        }
        case "cancel":
          payload = { action: "cancel" };
          break;
      }
      await adminSubscriptionAction(target.id, payload);
      setActionMessage("Action enregistrée avec succès.");
      setTarget(null);
      await load();    } catch (caught) {
      setActionError(
        caught instanceof Error ? caught.message : "Action impossible.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <p className="eyebrow">Administration</p>
        <h1 className="page-title">Abonnements</h1>
        <p className="mt-1 text-sm text-muted">
          Toutes les souscriptions aux plans, par utilisateur. Actions sensibles
          enregistrées dans le journal d&apos;audit.
        </p>
      </div>

      <Feedback message={actionMessage} />

      <div className="panel">
        <div className="panel-heading">
          <div className="relative w-full max-w-xs">
            <Search
              aria-hidden="true"
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted"
              size={16}
            />
            <input
              className="form-input pl-9"
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              placeholder="Nom, email ou téléphone…"
              type="search"
              value={search}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              aria-label="Filtrer par statut"
              className="form-input w-auto"
              onChange={(event) => {
                setStatus(event.target.value);
                setPage(1);
              }}
              value={status}
            >
              <option value="">Tous les statuts</option>
              <option value="TRIALING">Essai</option>
              <option value="ACTIVE">Actives</option>
              <option value="PAST_DUE">Impayées</option>
              <option value="CANCELLED">Annulées</option>
              <option value="EXPIRED">Expirées</option>
            </select>
            <select
              aria-label="Filtrer par plan"
              className="form-input w-auto"
              onChange={(event) => {
                setPlan(event.target.value);
                setPage(1);
              }}
              value={plan}
            >
              <option value="">Tous les plans</option>
              <option value="free">Gratuit</option>
              <option value="essential">Essentiel</option>
              <option value="pro">Pro</option>
            </select>
          </div>
        </div>

        {loading ? (
          <AdminLoading label="Chargement des abonnements…" />
        ) : error ? (
          <div className="p-5">
            <AdminError message={error} onRetry={load} />
          </div>
        ) : !data || data.results.length === 0 ? (
          <div className="p-5">
            <AdminEmpty label="Aucun abonnement ne correspond à ces filtres." />
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Utilisateur</th>
                    <th scope="col">Plan</th>
                    <th scope="col">Prix / mois</th>
                    <th scope="col">Maisons</th>
                    <th scope="col">Statut</th>
                    <th scope="col">Début</th>
                    <th scope="col">Expiration</th>
                    <th scope="col">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((sub) => (
                    <tr key={sub.id}>
                      <td>
                        <p className="font-semibold text-ink">
                          {sub.user_full_name || sub.user_phone}
                        </p>
                        <p className="text-xs text-muted">{sub.user_email}</p>
                      </td>
                      <td className="text-xs">
                        <span className="font-semibold text-ink">{sub.plan_name}</span>
                      </td>
                      <td className="whitespace-nowrap text-xs">
                        {sub.price_monthly
                          ? `${sub.price_monthly.toLocaleString("fr-FR")} ${sub.currency}`
                          : "—"}
                      </td>
                      <td className="text-xs">
                        {sub.houses_count}/{sub.max_houses}
                      </td>
                      <td>
                        <StatusPill status={sub.status} />
                      </td>
                      <td className="whitespace-nowrap text-xs">
                        {sub.started_at ? formatDate(sub.started_at) : "—"}
                      </td>
                      <td className="whitespace-nowrap text-xs">
                        {sub.expires_at ? formatDate(sub.expires_at) : "—"}
                      </td>
                      <td>
                        <button
                          aria-label={`Gérer l'abonnement de ${sub.user_full_name || sub.user_phone}`}
                          className="action-icon"
                          onClick={() => openActions(sub)}
                          title="Gérer l'abonnement"
                          type="button"
                        >
                          <Settings2 aria-hidden="true" size={17} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <AdminPagination
              count={data.count}
              onChange={setPage}
              page={page}
              pageSize={PAGE_SIZE}
            />
          </>
        )}
      </div>

      <Modal
        description="Toute action est enregistrée dans le journal d'audit."
        onClose={() => setTarget(null)}
        open={target !== null}
        title={
          target
            ? `Gérer l'abonnement de ${target.user_full_name || target.user_phone}`
            : "Gérer l'abonnement"
        }
      >
        <div className="space-y-4 px-5 py-5 sm:px-6">
          <div>
            <label className="form-label" htmlFor="action-type">
              Action
            </label>
            <select
              className="form-input"
              id="action-type"
              onChange={(event) =>
                setActionType(
                  event.target.value as "change_plan" | "extend" | "activate" | "cancel",
                )
              }
              value={actionType}
            >
              <option value="change_plan">Changer de plan</option>
              <option value="extend">Prolonger l&apos;abonnement</option>
              <option value="activate">Activer manuellement</option>
              <option value="cancel">Annuler l&apos;abonnement</option>
            </select>
          </div>

          {actionType === "change_plan" || actionType === "activate" ? (
            <div>
              <label className="form-label" htmlFor="action-plan">
                Plan
              </label>
              <select
                className="form-input"
                id="action-plan"
                onChange={(event) => setPlanSlug(event.target.value)}
                value={planSlug}
              >
                {PLAN_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          {actionType === "extend" || actionType === "activate" ? (
            <div>
              <label className="form-label" htmlFor="action-days">
                Durée (jours)
              </label>
              <input
                className="form-input"
                id="action-days"
                inputMode="numeric"
                min={1}
                onChange={(event) => setDays(event.target.value)}
                type="number"
                value={days}
              />
              {actionType === "activate" ? (
                <p className="mt-1 text-xs text-muted">
                  Laissez vide pour la durée restante par défaut.
                </p>
              ) : null}
            </div>
          ) : null}

          {actionType === "cancel" ? (
            <p className="rounded-[10px] bg-amber-50 p-3 text-sm leading-5 text-[#7c5a15]">
              L&apos;abonnement sera annulé : l&apos;utilisateur perdra l&apos;accès
              aux fonctionnalités payantes à la fin de la période en cours.
            </p>
          ) : null}

          {actionError ? (
            <p className="rounded-[10px] bg-red-50 p-3 text-sm text-red-800" role="alert">
              {actionError}
            </p>
          ) : null}

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button
              className="secondary-button"
              disabled={busy}
              onClick={() => setTarget(null)}
              type="button"
            >
              Annuler
            </button>
            <button
              className="primary-button"
              disabled={busy}
              onClick={() => void confirmAction()}
              type="button"
            >
              {busy ? "Enregistrement…" : "Enregistrer"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
