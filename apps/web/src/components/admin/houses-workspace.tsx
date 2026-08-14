"use client";

import { Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AdminPagination } from "@/components/admin/admin-pagination";
import {
  AdminEmpty,
  AdminError,
  AdminLoading,
} from "@/components/admin/admin-states";
import { listAdminHouses } from "@/lib/admin-api-client";
import { formatDate } from "@/lib/format";
import type { AdminHouse } from "@/types/admin";
import type { PaginatedPage } from "@/types/domain";

const PAGE_SIZE = 25;

const STATUS_LABELS: Record<string, string> = {
  AVAILABLE: "Disponible",
  OCCUPIED: "Occupée",
  MAINTENANCE: "Maintenance",
};

export function AdminHousesWorkspace() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [occupancy, setOccupancy] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PaginatedPage<AdminHouse> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(
        await listAdminHouses({
          page,
          page_size: PAGE_SIZE,
          search: search || undefined,
          status: status || undefined,
          occupancy: occupancy || undefined,
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Erreur inconnue.");
    } finally {
      setLoading(false);
    }
  }, [page, search, status, occupancy]);

  useEffect(() => {
    void Promise.resolve().then(load);
  }, [load]);

  return (
    <div className="space-y-5">
      <div>
        <p className="eyebrow">Administration</p>
        <h1 className="page-title">Biens</h1>
        <p className="mt-1 text-sm text-muted">
          Tous les biens enregistrés sur ImmoLib, tous propriétaires confondus.
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
              placeholder="Nom, adresse ou propriétaire…"
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
              <option value="AVAILABLE">Disponibles</option>
              <option value="OCCUPIED">Occupées</option>
              <option value="MAINTENANCE">En maintenance</option>
            </select>
            <select
              aria-label="Filtrer par occupation"
              className="form-input w-auto"
              onChange={(event) => {
                setOccupancy(event.target.value);
                setPage(1);
              }}
              value={occupancy}
            >
              <option value="">Toutes les occupations</option>
              <option value="with_tenant">Avec locataire actif</option>
              <option value="without_tenant">Sans locataire actif</option>
            </select>
          </div>
        </div>

        {loading ? (
          <AdminLoading label="Chargement des biens…" />
        ) : error ? (
          <div className="p-5">
            <AdminError message={error} onRetry={load} />
          </div>
        ) : !data || data.results.length === 0 ? (
          <div className="p-5">
            <AdminEmpty label="Aucun bien ne correspond à ces filtres." />
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Bien</th>
                    <th scope="col">Propriétaire</th>
                    <th scope="col">Type</th>
                    <th scope="col">Locataire actif</th>
                    <th scope="col">Statut</th>
                    <th scope="col">Créée le</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((house) => (
                    <tr key={house.id}>
                      <td>
                        <p className="font-semibold text-ink">{house.name}</p>
                        <p className="text-xs text-muted">
                          {[house.address, house.commune, house.city]
                            .filter(Boolean)
                            .join(", ")}
                        </p>
                      </td>
                      <td className="text-xs">{house.primary_owner_name}</td>
                      <td className="text-xs">{house.property_type}</td>
                      <td className="text-xs">
                        {house.has_active_lease ? (
                          <span className="font-semibold text-ink">
                            {house.current_tenant_name ?? "Oui"}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td>
                        <span className="status-pill bg-brand-soft text-brand">
                          {STATUS_LABELS[house.status] ?? house.status}
                        </span>
                      </td>
                      <td className="whitespace-nowrap text-xs">
                        {formatDate(house.created_at)}
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
