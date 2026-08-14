"use client";

import {
  Building2,
  CircleUserRound,
  Coins,
  House,
  RefreshCw,
  Users,
  UsersRound,
} from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import {
  AdminEmpty,
  AdminError,
  AdminLoading,
} from "@/components/admin/admin-states";
import { getAdminDashboard } from "@/lib/admin-api-client";
import {
  getAdminHousesEvolution,
  getAdminRevenueSeries,
  getAdminUsersEvolution,
} from "@/lib/admin-api-client";
import { formatMoney } from "@/lib/format";
import type { AdminDashboardMetrics, AdminSeriesPoint } from "@/types/admin";

const AdminSeriesChart = dynamic(
  () =>
    import("@/components/admin/admin-charts").then(
      (module) => module.AdminSeriesChart,
    ),
  { loading: () => <div aria-label="Chargement du graphique" className="h-60 animate-pulse rounded-[10px] bg-canvas" role="status" />, ssr: false },
);

const AdminPlanSplitChart = dynamic(
  () =>
    import("@/components/admin/admin-charts").then(
      (module) => module.AdminPlanSplitChart,
    ),
  { loading: () => <div aria-label="Chargement du graphique" className="h-60 animate-pulse rounded-[10px] bg-canvas" role="status" />, ssr: false },
);

const USERS_PERIODS = ["7d", "30d", "3m", "12m"] as const;
const REVENUE_PERIODS = ["weekly", "monthly", "yearly"] as const;

function MetricCard({
  label,
  value,
  icon,
  hint,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  hint?: string;
}) {
  return (
    <div className="metric-card">
      <div className="metric-icon">{icon}</div>
      <p className="metric-value">{value}</p>
      <p className="metric-label">{label}</p>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

export function AdminDashboardWorkspace() {
  const [metrics, setMetrics] = useState<AdminDashboardMetrics | null>(null);
  const [usersSeries, setUsersSeries] = useState<AdminSeriesPoint[]>([]);
  const [revenueSeries, setRevenueSeries] = useState<AdminSeriesPoint[]>([]);
  const [housesSeries, setHousesSeries] = useState<AdminSeriesPoint[]>([]);
  const [usersPeriod, setUsersPeriod] = useState<"7d" | "30d" | "3m" | "12m">("30d");
  const [revenuePeriod, setRevenuePeriod] = useState<"weekly" | "monthly" | "yearly">("monthly");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [dashboard, users, revenue, houses] = await Promise.all([
        getAdminDashboard(),
        getAdminUsersEvolution(usersPeriod),
        getAdminRevenueSeries(revenuePeriod),
        getAdminHousesEvolution("30d"),
      ]);
      setMetrics(dashboard);
      setUsersSeries(users);
      setRevenueSeries(revenue);
      setHousesSeries(houses);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Erreur inconnue.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void Promise.resolve().then(loadAll);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadUsersSeries(period: "7d" | "30d" | "3m" | "12m") {
    setUsersPeriod(period);
    try {
      setUsersSeries(await getAdminUsersEvolution(period));
    } catch {
      // le graphique conserve la derniere serie valide
    }
  }

  async function loadRevenueSeries(
    period: "weekly" | "monthly" | "yearly",
  ) {
    setRevenuePeriod(period);
    try {
      setRevenueSeries(await getAdminRevenueSeries(period));
    } catch {
      // le graphique conserve la derniere serie valide
    }
  }

  if (loading && !metrics) return <AdminLoading label="Chargement des statistiques…" />;
  if (error && !metrics) {
    return <AdminError message={error} onRetry={loadAll} />;
  }
  if (!metrics) return <AdminEmpty label="Aucune donnée disponible." />;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="eyebrow">Vue d’ensemble</p>
          <h1 className="page-title">Dashboard ImmoLib</h1>
        </div>
        <button className="secondary-button" onClick={loadAll} type="button">
          <RefreshCw aria-hidden="true" size={16} />
          Actualiser
        </button>
      </div>

      {error ? (
        <AdminError message={error} onRetry={loadAll} />
      ) : null}

      <section aria-labelledby="section-utilisateurs">
        <h2 className="section-kicker" id="section-utilisateurs">
          Utilisateurs
        </h2>
        <div className="mt-3 grid grid-cols-2 gap-4 lg:grid-cols-5">
          <MetricCard icon={<CircleUserRound aria-hidden="true" size={19} />} label="Utilisateurs totaux" value={metrics.users.total} hint={`+${metrics.users.new_7d} cette semaine`} />
          <MetricCard icon={<Users aria-hidden="true" size={19} />} label="Bailleurs" value={metrics.users.landlords} />
          <MetricCard icon={<UsersRound aria-hidden="true" size={19} />} label="Locataires" value={metrics.users.tenants} />
          <MetricCard icon={<Building2 aria-hidden="true" size={19} />} label="Administrateurs" value={metrics.users.admins} />
          <MetricCard icon={<Users aria-hidden="true" size={19} />} label="Nouveaux (7 j)" value={metrics.users.new_7d} />
        </div>
      </section>

      <section aria-labelledby="section-immobilier">
        <h2 className="section-kicker" id="section-immobilier">
          Immobilier
        </h2>
        <div className="mt-3 grid grid-cols-2 gap-4 lg:grid-cols-3">
          <MetricCard icon={<House aria-hidden="true" size={19} />} label="Biens enregistrés" value={metrics.houses.total} />
          <MetricCard icon={<House aria-hidden="true" size={19} />} label="Biens occupés" value={metrics.houses.occupied} />
          <MetricCard icon={<House aria-hidden="true" size={19} />} label="Ajoutées (7 j)" value={metrics.houses.recent_7d} />
        </div>
      </section>

      <section aria-labelledby="section-abonnements">
        <h2 className="section-kicker" id="section-abonnements">
          Abonnements
        </h2>
        <div className="mt-3 grid grid-cols-2 gap-4 lg:grid-cols-5">
          <MetricCard icon={<Coins aria-hidden="true" size={19} />} label="Gratuit" value={metrics.subscriptions.breakdown.free ?? 0} />
          <MetricCard icon={<Coins aria-hidden="true" size={19} />} label="Essentiel" value={metrics.subscriptions.breakdown.essential ?? 0} />
          <MetricCard icon={<Coins aria-hidden="true" size={19} />} label="Pro" value={metrics.subscriptions.breakdown.pro ?? 0} />
          <MetricCard icon={<Coins aria-hidden="true" size={19} />} label="Abonnements actifs" value={metrics.subscriptions.active} />
          <MetricCard icon={<Coins aria-hidden="true" size={19} />} label="Expirés" value={metrics.subscriptions.expired} />
        </div>
      </section>

      <section aria-labelledby="section-revenus">
        <h2 className="section-kicker" id="section-revenus">
          Revenus d’abonnement
        </h2>
        <p className="mt-1 text-xs text-muted">
          Calculés uniquement sur les paiements d’abonnement réellement
          confirmés ({metrics.revenue.currency}).
        </p>
        <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <MetricCard icon={<Coins aria-hidden="true" size={19} />} label="Revenus du mois" value={formatMoney(metrics.revenue.month)} />
          <MetricCard icon={<Coins aria-hidden="true" size={19} />} label="Revenus du jour" value={formatMoney(metrics.revenue.day)} />
          <MetricCard icon={<Coins aria-hidden="true" size={19} />} label="Mois précédent" value={formatMoney(metrics.revenue.previous_month)} />
        </div>
      </section>

      <section aria-labelledby="section-graphiques">
        <h2 className="section-kicker" id="section-graphiques">
          Statistiques
        </h2>
        <div className="mt-3 grid grid-cols-1 gap-4 xl:grid-cols-2">
          <div className="panel">
            <div className="panel-heading">
              <div>
                <h3 className="section-title">Évolution des utilisateurs</h3>
                <p className="mt-1 text-xs text-muted">Nouveaux comptes par jour</p>
              </div>
              <div className="flex rounded-[9px] border border-line p-0.5 text-xs font-semibold">
                {USERS_PERIODS.map((period) => (
                  <button
                    aria-pressed={usersPeriod === period}
                    className={`rounded-[7px] px-2.5 py-1.5 ${usersPeriod === period ? "bg-canvas text-ink" : "text-muted hover:text-ink"}`}
                    key={period}
                    onClick={() => loadUsersSeries(period)}
                    type="button"
                  >
                    {period}
                  </button>
                ))}
              </div>
            </div>
            <div className="px-5 py-5">
              <AdminSeriesChart
                data={usersSeries}
                dataKey="count"
                label="Évolution des utilisateurs"
              />
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <div>
                <h3 className="section-title">Répartition des abonnements</h3>
                <p className="mt-1 text-xs text-muted">Par plan actuel</p>
              </div>
            </div>
            <div className="px-5 py-5">
              <AdminPlanSplitChart breakdown={metrics.subscriptions.breakdown} />
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <div>
                <h3 className="section-title">Revenus d’abonnement</h3>
                <p className="mt-1 text-xs text-muted">Transactions confirmées</p>
              </div>
              <div className="flex rounded-[9px] border border-line p-0.5 text-xs font-semibold">
                {REVENUE_PERIODS.map((period) => (
                  <button
                    aria-pressed={revenuePeriod === period}
                    className={`rounded-[7px] px-2.5 py-1.5 ${revenuePeriod === period ? "bg-canvas text-ink" : "text-muted hover:text-ink"}`}
                    key={period}
                    onClick={() => loadRevenueSeries(period)}
                    type="button"
                  >
                    {period === "weekly" ? "Hebdo" : period === "monthly" ? "Mensuel" : "Annuel"}
                  </button>
                ))}
              </div>
            </div>
            <div className="px-5 py-5">
              <AdminSeriesChart
                data={revenueSeries}
                dataKey="total"
                label="Revenus d'abonnement"
                money
              />
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <div>
                <h3 className="section-title">Biens ajoutés</h3>
                <p className="mt-1 text-xs text-muted">Sur les 30 derniers jours</p>
              </div>
            </div>
            <div className="px-5 py-5">
              <AdminSeriesChart
                data={housesSeries}
                dataKey="count"
                color="#4f5049"
                label="Biens ajoutés"
              />
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
