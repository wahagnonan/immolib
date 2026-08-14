"use client";

import { Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AdminPagination } from "@/components/admin/admin-pagination";
import {
  AdminEmpty,
  AdminError,
  AdminLoading,
} from "@/components/admin/admin-states";
import { listAdminTenants } from "@/lib/admin-api-client";
import { formatDate } from "@/lib/format";
import type { AdminTenant } from "@/types/admin";
import type { PaginatedPage } from "@/types/domain";

const PAGE_SIZE = 25;

const STATUS_LABELS: Record<string, string> = {
  UNREGISTERED: "Sans compte",
  INVITED: "Invité",
  ACTIVE: "Actif",
  BLOCKED: "Bloqué",
};

function StatusPill({ status }: { status: string }) {
  switch (status) {
    case "ACTIVE":
      return <span className="status-pill status-paid">Actif</span>;
    case "INVITED":
      return <span className="status-pill bg-sky-soft text-sky-dark">Invité</span>;
    case "BLOCKED":
      return <span className="status-pill bg-red-50 text-red-700">Bloqué</span>;
    default:
      return (
        <span className="status-pill bg-zinc-100 text-zinc-700">
          {STATUS_LABELS[status] ?? status}
        </span>
      );
  }
}

export function AdminTenantsWorkspace() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PaginatedPage<AdminTenant> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(
        await listAdminTenants({
          page,
          page_size: PAGE_SIZE,
          search: search || undefined,
          status: status || undefined,
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Erreur inconnue.");
    } finally {
      setLoading(false);
    }
  }, [page, search, status]);

  useEffect(() => {
    void Promise.resolve().then(load);
  }, [load]);

  return (
    <div className="space-y-5">
      <div>
        <p className="eyebrow">Administration</p>
        <h1 className="page-title">Locataires</h1>
        <p className="mt-1 text-sm text-muted">
          Fiches locataires enregistrées, une fiche par bien, tous bailleurs
          confondus.
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
              placeholder="Nom, téléphone, bien…"
              type="search"
              value={search}
            />
          </div>
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
            <option value="ACTIVE">Actifs</option>
            <option value="INVITED">Invités</option>
            <option value="UNREGISTERED">Sans compte</option>
            <option value="BLOCKED">Bloqués</option>
          </select>
        </div>

        {loading ? (
          <AdminLoading label="Chargement des locataires…" />
        ) : error ? (
          <div className="p-5">
            <AdminError message={error} onRetry={load} />
          </div>
        ) : !data || data.results.length === 0 ? (
          <div className="p-5">
            <AdminEmpty label="Aucun locataire ne correspond à ces filtres." />
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Locataire</th>
                    <th scope="col">Bien</th>
                    <th scope="col">Compte lié</th>
                    <th scope="col">Statut</th>
                    <th scope="col">Créée le</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((tenant) => (
                    <tr key={tenant.id}>
                      <td>
                        <p className="font-semibold text-ink">
                          {tenant.full_name || "—"}
                        </p>
                        <p className="text-xs text-muted">{tenant.phone}</p>
                      </td>
                      <td className="text-xs">{tenant.property_name}</td>
                      <td className="text-xs">
                        {tenant.linked_user_id ? (
                          <span className="font-semibold text-ink">
                            {tenant.linked_user_phone}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td>
                        <StatusPill status={tenant.status} />
                      </td>
                      <td className="whitespace-nowrap text-xs">
                        {formatDate(tenant.created_at)}
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
