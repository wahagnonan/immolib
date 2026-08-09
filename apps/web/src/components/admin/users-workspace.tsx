"use client";

import { Ban, CheckCircle2, Eye, Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AdminConfirmModal } from "@/components/admin/admin-confirm-modal";
import { AdminPagination } from "@/components/admin/admin-pagination";
import {
  AdminEmpty,
  AdminError,
  AdminLoading,
} from "@/components/admin/admin-states";
import { Modal } from "@/components/ui/modal";
import {
  getAdminUser,
  listAdminUsers,
  updateAdminUserStatus,
} from "@/lib/admin-api-client";
import { formatDate, formatDateTime } from "@/lib/format";
import type { AdminUserDetail, AdminUserSummary } from "@/types/admin";
import type { PaginatedPage } from "@/types/domain";

const PAGE_SIZE = 25;

const PLAN_LABELS: Record<string, string> = {
  free: "Gratuit",
  essential: "Essentiel",
  pro: "Pro",
};

function StatusPill({ active }: { active: boolean }) {
  return active ? (
    <span className="status-pill status-paid">Actif</span>
  ) : (
    <span className="status-pill bg-zinc-100 text-zinc-700">Suspendu</span>
  );
}

export function AdminUsersWorkspace() {
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [profile, setProfile] = useState("");
  const [plan, setPlan] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PaginatedPage<AdminUserSummary> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [detail, setDetail] = useState<AdminUserDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [suspendTarget, setSuspendTarget] = useState<AdminUserSummary | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(
        await listAdminUsers({
          page,
          page_size: PAGE_SIZE,
          search: search || undefined,
          role: role || undefined,
          status: status || undefined,
          profile: profile || undefined,
          plan: plan || undefined,
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Erreur inconnue.");
    } finally {
      setLoading(false);
    }
  }, [page, search, role, status, profile, plan]);

  useEffect(() => {
    void Promise.resolve().then(load);
  }, [load]);

  async function openDetail(user: AdminUserSummary) {
    setDetailLoading(true);
    setDetail(null);
    try {
      setDetail(await getAdminUser(user.id));
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "Erreur inconnue.");
    } finally {
      setDetailLoading(false);
    }
  }

  async function confirmSuspend() {
    if (!suspendTarget) return;
    setActionBusy(true);
    setActionError(null);
    try {
      await updateAdminUserStatus(suspendTarget.id, !suspendTarget.is_active);
      setSuspendTarget(null);
      await load();
    } catch (caught) {
      setActionError(
        caught instanceof Error ? caught.message : "Action impossible.",
      );
    } finally {
      setActionBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <p className="eyebrow">Administration</p>
        <h1 className="page-title">Utilisateurs</h1>
        <p className="mt-1 text-sm text-muted">
          Rechercher, consulter, suspendre ou réactiver un compte.
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
              aria-label="Filtrer par rôle"
              className="form-input w-auto"
              onChange={(event) => {
                setRole(event.target.value);
                setPage(1);
              }}
              value={role}
            >
              <option value="">Tous les rôles</option>
              <option value="USER">Utilisateurs</option>
              <option value="ADMIN">Administrateurs</option>
            </select>
            <select
              aria-label="Filtrer par profil"
              className="form-input w-auto"
              onChange={(event) => {
                setProfile(event.target.value);
                setPage(1);
              }}
              value={profile}
            >
              <option value="">Tous les profils</option>
              <option value="landlord">Bailleurs</option>
              <option value="tenant">Locataires</option>
              <option value="both">Bailleur et locataire</option>
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
          <AdminLoading label="Chargement des utilisateurs…" />
        ) : error ? (
          <div className="p-5">
            <AdminError message={error} onRetry={load} />
          </div>
        ) : !data || data.results.length === 0 ? (
          <div className="p-5">
            <AdminEmpty label="Aucun utilisateur ne correspond à ces filtres." />
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Utilisateur</th>
                    <th scope="col">Inscription</th>
                    <th scope="col">Rôle</th>
                    <th scope="col">Plan</th>
                    <th scope="col">Maisons</th>
                    <th scope="col">Statut</th>
                    <th scope="col">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((user) => (
                    <tr key={user.id}>
                      <td>
                        <p className="font-semibold text-ink">
                          {user.full_name || "—"}
                        </p>
                        <p className="text-xs text-muted">
                          {user.email || user.phone}
                        </p>
                      </td>
                      <td className="whitespace-nowrap text-xs">
                        {formatDate(user.date_joined)}
                      </td>
                      <td>
                        {user.role === "ADMIN" ? (
                          <span className="status-pill bg-brand-soft text-brand">
                            Admin
                          </span>
                        ) : (
                          <span className="status-pill bg-sky-soft text-sky-dark">
                            Utilisateur
                          </span>
                        )}
                      </td>
                      <td className="text-xs">
                        {user.plan_name ? (
                          <>
                            <span className="font-semibold text-ink">
                              {PLAN_LABELS[user.plan_slug ?? ""] ?? user.plan_name}
                            </span>
                            {user.subscription_status === "CANCELLED" ? (
                              <span className="ml-1 text-muted">(annulé)</span>
                            ) : null}
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="text-xs">{user.houses_count}</td>
                      <td>
                        <StatusPill active={user.is_active} />
                      </td>
                      <td>
                        <div className="flex items-center gap-1">
                          <button
                            aria-label={`Consulter ${user.full_name || user.phone}`}
                            className="action-icon"
                            onClick={() => openDetail(user)}
                            title="Consulter"
                            type="button"
                          >
                            <Eye aria-hidden="true" size={17} />
                          </button>
                          {user.is_active ? (
                            <button
                              aria-label={`Suspendre ${user.full_name || user.phone}`}
                              className="action-icon text-red-700 hover:bg-red-50"
                              onClick={() => setSuspendTarget(user)}
                              title="Suspendre"
                              type="button"
                            >
                              <Ban aria-hidden="true" size={17} />
                            </button>
                          ) : (
                            <button
                              aria-label={`Réactiver ${user.full_name || user.phone}`}
                              className="action-icon text-[#275c3b] hover:bg-[#edf5ef]"
                              onClick={() => setSuspendTarget(user)}
                              title="Réactiver"
                              type="button"
                            >
                              <CheckCircle2 aria-hidden="true" size={17} />
                            </button>
                          )}
                        </div>
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
        description="Informations complètes du compte, telles que vues par l'administration."
        onClose={() => setDetail(null)}
        open={detail !== null || detailLoading}
        size="lg"
        title="Fiche utilisateur"
      >
        {detailLoading || !detail ? (
          <div className="p-6">
            <AdminLoading label="Chargement de la fiche…" />
          </div>
        ) : (
          <dl className="grid grid-cols-1 gap-x-6 gap-y-4 px-5 py-5 text-sm sm:grid-cols-2 sm:px-6">
            <div>
              <dt className="text-xs font-semibold text-muted">Nom</dt>
              <dd className="mt-0.5 font-semibold text-ink">
                {detail.full_name || "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-muted">Email</dt>
              <dd className="mt-0.5 text-ink">{detail.email || "—"}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-muted">Téléphone</dt>
              <dd className="mt-0.5 text-ink">{detail.phone}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-muted">Date d&apos;inscription</dt>
              <dd className="mt-0.5 text-ink">{formatDateTime(detail.date_joined)}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-muted">Rôle</dt>
              <dd className="mt-0.5 text-ink">
                {detail.role === "ADMIN" ? "Administrateur" : "Utilisateur"}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-muted">Statut</dt>
              <dd className="mt-0.5">
                <StatusPill active={detail.is_active} />
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-muted">Plan</dt>
              <dd className="mt-0.5 text-ink">
                {detail.plan_name
                  ? `${PLAN_LABELS[detail.plan_slug ?? ""] ?? detail.plan_name} (${
                      detail.subscription_status ?? "—"
                    })`
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-muted">Dernière activité</dt>
              <dd className="mt-0.5 text-ink">
                {detail.last_login ? formatDateTime(detail.last_login) : "Jamais"}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-muted">Nombre de maisons</dt>
              <dd className="mt-0.5 text-ink">{detail.houses_count}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-muted">Profils locataires</dt>
              <dd className="mt-0.5 text-ink">{detail.tenants_count}</dd>
            </div>
          </dl>
        )}
      </Modal>

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
        title={suspendTarget?.is_active ? "Suspendre l'utilisateur" : "Réactiver l'utilisateur"}
      />
    </div>
  );
}
