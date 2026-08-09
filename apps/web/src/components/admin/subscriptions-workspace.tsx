"use client";

import { Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AdminPagination } from "@/components/admin/admin-pagination";
import {
  AdminEmpty,
  AdminError,
  AdminLoading,
} from "@/components/admin/admin-states";
import { listAdminSubscriptions } from "@/lib/admin-api-client";
import { formatDate } from "@/lib/format";
import type { AdminSubscription } from "@/types/admin";
import type { PaginatedPage } from "@/types/domain";

const PAGE_SIZE = 25;

const STATUS_LABELS: Record<string, string> = {
  TRIALING: "Essai",
  ACTIVE: "Active",
  PAST_DUE: "Impayée",
  CANCELLED: "Annulée",
  EXPIRED: "Expirée",
};

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

  return (
    <div className="space-y-5">
      <div>
        <p className="eyebrow">Administration</p>
        <h1 className="page-title">Abonnements</h1>
        <p className="mt-1 text-sm text-muted">
          Toutes les souscriptions aux plans, par utilisateur.
        </p>
      </div>

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
    </div>
  );
}
