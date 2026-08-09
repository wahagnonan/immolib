"use client";

import { Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AdminPagination } from "@/components/admin/admin-pagination";
import {
  AdminEmpty,
  AdminError,
  AdminLoading,
} from "@/components/admin/admin-states";
import { listAdminAuditLogs } from "@/lib/admin-api-client";
import { formatDateTime } from "@/lib/format";
import type { AdminAuditLog } from "@/types/admin";
import type { PaginatedPage } from "@/types/domain";

const PAGE_SIZE = 50;

function formatMetadata(metadata: Record<string, unknown> | null | undefined) {
  if (!metadata) return "—";
  const text = Object.entries(metadata)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(" · ");
  return text || "—";
}

export function AdminAuditLogsWorkspace() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PaginatedPage<AdminAuditLog> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(
        await listAdminAuditLogs({
          page,
          page_size: PAGE_SIZE,
          search: search || undefined,
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Erreur inconnue.");
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => {
    void Promise.resolve().then(load);
  }, [load]);

  return (
    <div className="space-y-5">
      <div>
        <p className="eyebrow">Administration</p>
        <h1 className="page-title">Journal d&apos;audit</h1>
        <p className="mt-1 text-sm text-muted">
          Historique des actions sensibles effectuées par les administrateurs.
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
              placeholder="Action, admin, type de cible…"
              type="search"
              value={search}
            />
          </div>
          <span className="text-xs text-muted">Sensibles : suspension, paiement, suppression</span>
        </div>

        {loading ? (
          <AdminLoading label="Chargement du journal…" />
        ) : error ? (
          <div className="p-5">
            <AdminError message={error} onRetry={load} />
          </div>
        ) : !data || data.results.length === 0 ? (
          <div className="p-5">
            <AdminEmpty label="Aucune entrée dans le journal." />
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Date</th>
                    <th scope="col">Action</th>
                    <th scope="col">Cible</th>
                    <th scope="col">Administrateur</th>
                    <th scope="col">Détails</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((log) => (
                    <tr key={log.id}>
                      <td className="whitespace-nowrap text-xs">
                        {formatDateTime(log.created_at)}
                      </td>
                      <td className="text-xs">
                        <span className="font-semibold text-ink">
                          {log.action_label || log.action}
                        </span>
                      </td>
                      <td className="text-xs">
                        {log.target_type ? (
                          <>
                            {log.target_type}
                            {log.target_id ? (
                              <span className="text-muted"> #{log.target_id}</span>
                            ) : null}
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="text-xs">
                        {log.admin_name || log.admin_phone || "—"}
                      </td>
                      <td className="max-w-md text-xs text-muted">
                        <span className="line-clamp-2">
                          {formatMetadata(log.metadata)}
                        </span>
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
