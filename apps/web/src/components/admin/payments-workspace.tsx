"use client";

import { Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AdminPagination } from "@/components/admin/admin-pagination";
import {
  AdminEmpty,
  AdminError,
  AdminLoading,
} from "@/components/admin/admin-states";
import { listAdminPayments } from "@/lib/admin-api-client";
import { formatDateTime } from "@/lib/format";
import type { AdminPayment } from "@/types/admin";
import type { PaginatedPage } from "@/types/domain";

const PAGE_SIZE = 25;

const STATUS_LABELS: Record<string, string> = {
  PENDING: "En attente",
  SUCCESSFUL: "Réussi",
  FAILED: "Échoué",
  CANCELLED: "Annulé",
  EXPIRED: "Expiré",
};

function StatusPill({ status }: { status: string }) {
  switch (status) {
    case "SUCCESSFUL":
      return <span className="status-pill status-paid">Réussi</span>;
    case "PENDING":
      return <span className="status-pill status-partial">En attente</span>;
    case "FAILED":
    case "CANCELLED":
    case "EXPIRED":
      return <span className="status-pill bg-red-50 text-red-700">{STATUS_LABELS[status]}</span>;
    default:
      return (
        <span className="status-pill bg-zinc-100 text-zinc-700">
          {STATUS_LABELS[status] ?? status}
        </span>
      );
  }
}

function formatMoney(value: number, currency: string) {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(value));
}

export function AdminPaymentsWorkspace() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [plan, setPlan] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PaginatedPage<AdminPayment> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(
        await listAdminPayments({
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
        <h1 className="page-title">Paiements</h1>
        <p className="mt-1 text-sm text-muted">
          Paiements d&apos;abonnement (transactions), sans aucun détail sensible.
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
              placeholder="Nom, email, téléphone…"
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
              <option value="SUCCESSFUL">Réussis</option>
              <option value="PENDING">En attente</option>
              <option value="FAILED">Échoués</option>
              <option value="CANCELLED">Annulés</option>
              <option value="EXPIRED">Expirés</option>
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
          <AdminLoading label="Chargement des paiements…" />
        ) : error ? (
          <div className="p-5">
            <AdminError message={error} onRetry={load} />
          </div>
        ) : !data || data.results.length === 0 ? (
          <div className="p-5">
            <AdminEmpty label="Aucun paiement ne correspond à ces filtres." />
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Utilisateur</th>
                    <th scope="col">Plan</th>
                    <th scope="col">Montant</th>
                    <th scope="col">Statut</th>
                    <th scope="col">Canal</th>
                    <th scope="col">Créée le</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((payment) => (
                    <tr key={payment.id}>
                      <td>
                        <p className="font-semibold text-ink">
                          {payment.user_full_name || payment.user_phone}
                        </p>
                        <p className="text-xs text-muted">{payment.user_phone}</p>
                      </td>
                      <td className="text-xs">{payment.plan_name}</td>
                      <td className="whitespace-nowrap text-xs">
                        <span className="font-semibold text-ink">
                          {formatMoney(payment.amount, payment.currency)}
                        </span>
                      </td>
                      <td>
                        <StatusPill status={payment.status} />
                      </td>
                      <td className="text-xs">{payment.provider || "—"}</td>
                      <td className="whitespace-nowrap text-xs">
                        {payment.completed_at
                          ? formatDateTime(payment.completed_at)
                          : formatDateTime(payment.created_at)}
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
