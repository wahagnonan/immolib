"use client";

import { CalendarPlus2, HandCoins, ReceiptText, RotateCw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Feedback } from "@/components/ui/feedback";
import { ModuleHeader } from "@/components/ui/module-header";
import {
  generateRentCharges,
  listRentCharges,
} from "@/lib/api-client";
import { formatDate, formatMoney, monthLabel } from "@/lib/format";
import type { RentCharge } from "@/types/domain";

const statusStyle: Record<RentCharge["status"], string> = {
  PAID: "status-paid",
  PARTIALLY_PAID: "status-partial",
  UPCOMING: "status-vacant",
  DUE: "status-partial",
  OVERDUE: "bg-red-50 text-red-700",
  DISPUTED: "bg-red-50 text-red-700",
  CANCELLED: "bg-zinc-100 text-zinc-700",
};

function currentPeriod() {
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
}

export function ChargeWorkspace() {
  const [charges, setCharges] = useState<RentCharge[]>([]);
  const [period, setPeriod] = useState(currentPeriod);
  const [status, setStatus] = useState<"ALL" | RentCharge["status"]>("ALL");
  const [generating, setGenerating] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listRentCharges({ period })
      .then(setCharges)
      .catch((caughtError) =>
        setError(caughtError instanceof Error ? caughtError.message : "Chargement impossible."),
      );
  }, [period]);

  const periodCharges = charges.filter((charge) => charge.period === period);
  const visibleCharges = periodCharges.filter(
    (charge) => status === "ALL" || charge.status === status,
  );
  const totals = periodCharges.reduce(
    (accumulator, charge) => ({
      due: accumulator.due + Number(charge.amount_due),
      paid: accumulator.paid + Number(charge.amount_paid),
      balance: accumulator.balance + Number(charge.balance_due),
    }),
    { due: 0, paid: 0, balance: 0 },
  );

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    setFeedback(null);
    try {
      const result = await generateRentCharges(period);
      setCharges(result.charges);
      setFeedback(`${result.created} créée(s), ${result.existing} déjà existante(s).`);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Génération impossible.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="space-y-6">
      <ModuleHeader
        action={
          <button className="primary-button w-fit" disabled={generating} onClick={handleGenerate} type="button">
            {generating ? <RotateCw aria-hidden="true" className="animate-spin" size={18} /> : <CalendarPlus2 aria-hidden="true" size={18} />}
            {generating ? "Génération…" : "Générer ce mois"}
          </button>
        }
        description="Chaque échéance correspond au loyer d'un mois pour un bail donné. La génération est idempotente : relancez-la sans crainte de doublon."
        eyebrow="Facturation mensuelle"
        title="Échéances"
      />
      <Feedback message={feedback} />
      <Feedback message={error} tone="error" />

      <section className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <label>
          <span className="form-label">Mois suivi</span>
          <input
            className="form-input min-w-48"
            onChange={(event) => setPeriod(event.target.value)}
            type="month"
            value={period}
          />
        </label>
        <label>
          <span className="form-label">Statut</span>
          <select
            className="form-input min-w-48"
            onChange={(event) => setStatus(event.target.value as "ALL" | RentCharge["status"])}
            value={status}
          >
            <option value="ALL">Tous les statuts</option>
            <option value="PAID">Payées</option>
            <option value="PARTIALLY_PAID">Partielles</option>
            <option value="DUE">À payer</option>
            <option value="UPCOMING">À venir</option>
            <option value="OVERDUE">En retard</option>
            <option value="DISPUTED">Contestées</option>
          </select>
        </label>
      </section>

      <section className="grid gap-3 sm:grid-cols-3">
        <div className="panel p-4">
          <p className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Attendu</p>
          <p className="mt-1 text-2xl font-bold text-ink">{formatMoney(totals.due)}</p>
        </div>
        <div className="panel p-4">
          <p className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Encaissé</p>
          <p className="mt-1 text-2xl font-semibold text-ink">{formatMoney(totals.paid)}</p>
        </div>
        <div className="panel p-4">
          <p className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Solde</p>
          <p className="mt-1 text-2xl font-semibold text-ink">{formatMoney(totals.balance)}</p>
        </div>
      </section>

      <section className="panel overflow-hidden">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">Période</p>
            <h2 className="section-title capitalize">{monthLabel(period)}</h2>
          </div>
          <span className="text-sm font-semibold text-muted">{visibleCharges.length} échéance(s)</span>
        </div>
        {visibleCharges.length ? (
          <div className="overflow-x-auto">
            <table className="data-table min-w-[880px]">
              <thead>
                <tr>
                  <th>Maison et locataire</th>
                  <th>Échéance</th>
                  <th>Progression</th>
                  <th>Statut</th>
                  <th className="text-right">Solde</th>
                  <th><span className="sr-only">Action</span></th>
                </tr>
              </thead>
              <tbody>
                {visibleCharges.map((charge) => {
                  const progress = Math.min(100, Math.round((Number(charge.amount_paid) / Number(charge.amount_due)) * 100));
                  return (
                    <tr key={charge.id}>
                      <td>
                        <p className="font-bold text-ink">{charge.house_name}</p>
                        <p className="mt-1 text-xs">{charge.tenant_name}</p>
                      </td>
                      <td>
                        <p className="font-semibold text-ink">{formatMoney(charge.amount_due)}</p>
                        <p className="mt-1 text-xs">Avant le {formatDate(charge.due_date)}</p>
                      </td>
                      <td className="min-w-44">
                        <div className="h-2 overflow-hidden rounded-full bg-line">
                          <div className="h-full rounded-full bg-brand" style={{ width: `${progress}%` }} />
                        </div>
                        <p className="mt-1.5 text-xs">{formatMoney(charge.amount_paid)} encaissés</p>
                      </td>
                      <td><span className={`status-pill ${statusStyle[charge.status]}`}>{charge.status_label}</span></td>
                      <td className="text-right font-bold text-ink">{formatMoney(charge.balance_due)}</td>
                      <td>
                        {Number(charge.balance_due) > 0 && charge.status !== "CANCELLED" ? (
                          <Link className="text-link whitespace-nowrap" href={`/paiements?charge=${charge.id}`}>
                            <HandCoins aria-hidden="true" size={16} /> Enregistrer
                          </Link>
                        ) : (
                          <ReceiptText aria-label="Échéance soldée" className="text-brand" size={18} />
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="px-5 py-16 text-center">
            <p className="font-bold text-ink">Aucune échéance pour ce mois</p>
            <p className="mt-1 text-sm text-muted">Utilisez « Générer ce mois » pour préparer les loyers.</p>
          </div>
        )}
      </section>
    </div>
  );
}
