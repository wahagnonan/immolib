"use client";

import { Ban, CheckCircle2, Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AdminConfirmModal } from "@/components/admin/admin-confirm-modal";
import { AdminPagination } from "@/components/admin/admin-pagination";
import {
  AdminEmpty,
  AdminError,
  AdminLoading,
} from "@/components/admin/admin-states";
import {
  listAdminLandlords,
  updateAdminUserStatus,
} from "@/lib/admin-api-client";
import { formatDate } from "@/lib/format";
import type { AdminUserSummary } from "@/types/admin";
import type { PaginatedPage } from "@/types/domain";

const PAGE_SIZE = 25;

export function AdminLandlordsWorkspace() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [plan, setPlan] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PaginatedPage<AdminUserSummary> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [suspendTarget, setSuspendTarget] = useState<AdminUserSummary | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(
        await listAdminLandlords({
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

  async function confirmSuspend() {
    if (!suspendTarget) return;
    setActionBusy(true);
    setActionError(null);
    try {
      await updateAdminUserStatus(suspendTarget.id, !suspendTarget.is_active);
      setSuspendTarget(null);
      await load();
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "Action impossible.");
    } finally {
      setActionBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <p className="eyebrow">Administration</p>
        <h1 className="page-title">Bailleurs</h1>
        <p className="mt-1 text-sm text-muted">
          Comptes détenant au moins une maison, avec leur utilisation.
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
              <option value="active">Actifs</option>
              <option value="suspended">Suspendus</option>
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
          <AdminLoading label="Chargement des bailleurs…" />
        ) : error ? (
          <div className="p-5">
            <AdminError message={error} onRetry={load} />
          </div>
        ) : !data || data.results.length === 0 ? (
          <div className="p-5">
            <AdminEmpty label="Aucun bailleur ne correspond à ces filtres." />
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Bailleur</th>
                    <th scope="col">Inscription</th>
                    <th scope="col">Maisons</th>
                    <th scope="col">Locataires</th>
                    <th scope="col">Plan</th>
                    <th scope="col">Statut</th>
                    <th scope="col">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((landlord) => (
                    <tr key={landlord.id}>
                      <td>
                        <p className="font-semibold text-ink">
                          {landlord.full_name || "—"}
                        </p>
                        <p className="text-xs text-muted">
                          {landlord.email || landlord.phone}
                        </p>
                      </td>
                      <td className="whitespace-nowrap text-xs">
                        {formatDate(landlord.date_joined)}
                      </td>
                      <td className="text-xs">{landlord.houses_count}</td>
                      <td className="text-xs">{landlord.tenants_count}</td>
                      <td className="text-xs">
                        <span className="font-semibold text-ink">
                          {landlord.plan_name ?? "—"}
                        </span>
                      </td>
                      <td>
                        {landlord.is_active ? (
                          <span className="status-pill status-paid">Actif</span>
                        ) : (
                          <span className="status-pill bg-zinc-100 text-zinc-700">
                            Suspendu
                          </span>
                        )}
                      </td>
                      <td>
                        {landlord.is_active ? (
                          <button
                            aria-label={`Suspendre ${landlord.full_name || landlord.phone}`}
                            className="action-icon text-red-700 hover:bg-red-50"
                            onClick={() => setSuspendTarget(landlord)}
                            title="Suspendre"
                            type="button"
                          >
                            <Ban aria-hidden="true" size={17} />
                          </button>
                        ) : (
                          <button
                            aria-label={`Réactiver ${landlord.full_name || landlord.phone}`}
                            className="action-icon text-[#275c3b] hover:bg-[#edf5ef]"
                            onClick={() => setSuspendTarget(landlord)}
                            title="Réactiver"
                            type="button"
                          >
                            <CheckCircle2 aria-hidden="true" size={17} />
                          </button>
                        )}
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

      <AdminConfirmModal
        busy={actionBusy}
        confirmLabel={suspendTarget?.is_active ? "Suspendre" : "Réactiver"}
        description={
          suspendTarget?.is_active
            ? `Êtes-vous sûr de vouloir suspendre ${suspendTarget.full_name || suspendTarget.phone} ? Cette action empêchera l'utilisateur de se connecter à ImmoLib.`
            : `Réactiver le compte de ${suspendTarget?.full_name || suspendTarget?.phone} ? Il pourra de nouveau se connecter.`
        }
        error={actionError}
        onClose={() => {
          setSuspendTarget(null);
          setActionError(null);
        }}
        onConfirm={confirmSuspend}
        open={suspendTarget !== null}
        title={suspendTarget?.is_active ? "Suspendre le bailleur" : "Réactiver le bailleur"}
      />
    </div>
  );
}
