"use client";

import { Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AdminPagination } from "@/components/admin/admin-pagination";
import {
  AdminEmpty,
  AdminError,
  AdminLoading,
} from "@/components/admin/admin-states";
import { listAdminNotifications } from "@/lib/admin-api-client";
import { formatDateTime } from "@/lib/format";
import type { AdminNotification } from "@/types/admin";
import type { PaginatedPage } from "@/types/domain";

const PAGE_SIZE = 25;

const STATUS_LABELS: Record<string, string> = {
  QUEUED: "En attente",
  PROCESSING: "En cours",
  SENT: "Envoyé",
  FAILED: "Échec",
};

function StatusPill({ status }: { status: string }) {
  switch (status) {
    case "SENT":
      return <span className="status-pill status-paid">Envoyé</span>;
    case "QUEUED":
      return <span className="status-pill status-partial">En attente</span>;
    case "PROCESSING":
      return <span className="status-pill bg-sky-soft text-sky-dark">En cours</span>;
    case "FAILED":
      return <span className="status-pill bg-red-50 text-red-700">Échec</span>;
    default:
      return (
        <span className="status-pill bg-zinc-100 text-zinc-700">
          {STATUS_LABELS[status] ?? status}
        </span>
      );
  }
}

export function AdminNotificationsWorkspace() {
  const [search, setSearch] = useState("");
  const [channel, setChannel] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PaginatedPage<AdminNotification> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(
        await listAdminNotifications({
          page,
          page_size: PAGE_SIZE,
          search: search || undefined,
          channel: channel || undefined,
          status: status || undefined,
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Erreur inconnue.");
    } finally {
      setLoading(false);
    }
  }, [page, search, channel, status]);

  useEffect(() => {
    void Promise.resolve().then(load);
  }, [load]);

  return (
    <div className="space-y-5">
      <div>
        <p className="eyebrow">Administration</p>
        <h1 className="page-title">Notifications</h1>
        <p className="mt-1 text-sm text-muted">
          Envois de messages (SMS, email, WhatsApp, push) sur la plateforme.
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
              placeholder="Destinataire, type, motif…"
              type="search"
              value={search}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              aria-label="Filtrer par canal"
              className="form-input w-auto"
              onChange={(event) => {
                setChannel(event.target.value);
                setPage(1);
              }}
              value={channel}
            >
              <option value="">Tous les canaux</option>
              <option value="SMS">SMS</option>
              <option value="EMAIL">Email</option>
              <option value="WHATSAPP">WhatsApp</option>
              <option value="PUSH">Push</option>
            </select>
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
              <option value="QUEUED">En attente</option>
              <option value="PROCESSING">En cours</option>
              <option value="SENT">Envoyés</option>
              <option value="FAILED">Échecs</option>
            </select>
          </div>
        </div>

        {loading ? (
          <AdminLoading label="Chargement des notifications…" />
        ) : error ? (
          <div className="p-5">
            <AdminError message={error} onRetry={load} />
          </div>
        ) : !data || data.results.length === 0 ? (
          <div className="p-5">
            <AdminEmpty label="Aucune notification ne correspond à ces filtres." />
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Type</th>
                    <th scope="col">Canal</th>
                    <th scope="col">Destinataire</th>
                    <th scope="col">Statut</th>
                    <th scope="col">Tentatives</th>
                    <th scope="col">Envoyée le</th>
                    <th scope="col">Motif d&apos;échec</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((notification) => (
                    <tr key={notification.id}>
                      <td className="text-xs">
                        <span className="font-semibold text-ink">
                          {notification.kind}
                        </span>
                      </td>
                      <td className="text-xs">{notification.channel}</td>
                      <td className="text-xs">{notification.destination}</td>
                      <td>
                        <StatusPill status={notification.status} />
                      </td>
                      <td className="text-xs">{notification.attempt_count}</td>
                      <td className="whitespace-nowrap text-xs">
                        {notification.sent_at
                          ? formatDateTime(notification.sent_at)
                          : "—"}
                      </td>
                      <td className="max-w-xs text-xs text-muted">
                        {notification.failure_reason || "—"}
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
