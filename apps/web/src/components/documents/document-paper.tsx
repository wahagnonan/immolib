import { BadgeCheck } from "lucide-react";

import { BrandMark } from "@/components/brand";
import { formatDate, formatMoney, monthLabel } from "@/lib/format";
import type { RentalDocument } from "@/types/domain";

export function DocumentPaper({ document }: { document: RentalDocument }) {
  return (
    <article className="document-paper mx-auto max-w-2xl border border-line bg-white p-6 shadow-[0_12px_40px_rgba(22,45,34,0.08)] sm:p-10">
      <header className="flex items-start justify-between gap-5 border-b-2 border-ink pb-6">
        <div className="flex items-center gap-3">
          <BrandMark className="size-10" />
          <div>
            <p className="text-lg font-bold tracking-[-0.04em] text-ink">ImmoLib</p>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">Document locatif</p>
          </div>
        </div>
        <span className={`status-pill ${document.status === "ACTIVE" ? "status-paid" : "bg-red-50 text-red-700"}`}>
          {document.status_label}
        </span>
      </header>

      <div className="py-8 text-center">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand">{document.reference}</p>
        <h2 className="mt-3 text-2xl font-bold tracking-[-0.04em] text-ink sm:text-3xl">{document.document_type_label}</h2>
        <p className="mt-2 capitalize text-muted">
          {document.document_type === "DEPOSIT_RECEIPT"
            ? "Caution du bail"
            : document.document_type === "DEPOSIT_SETTLEMENT"
              ? "Clôture de caution"
              : monthLabel(document.period)}
        </p>
      </div>

      <dl className="grid gap-x-8 gap-y-5 border-y border-line py-6 sm:grid-cols-2">
        <div><dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Bailleur</dt><dd className="mt-1 font-semibold text-ink">{document.owner_name}</dd></div>
        <div><dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Locataire</dt><dd className="mt-1 font-semibold text-ink">{document.tenant_name}</dd></div>
        <div><dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Bien</dt><dd className="mt-1 font-semibold text-ink">{document.house_name}</dd><dd className="mt-0.5 text-sm text-muted">{document.house_address}</dd></div>
        <div><dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Période</dt><dd className="mt-1 font-semibold text-ink">Du {formatDate(document.period_start)} au {formatDate(document.period_end)}</dd></div>
        <div><dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Moyen de paiement</dt><dd className="mt-1 font-semibold text-ink">{document.payment_method || "—"}</dd></div>
        <div><dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Émis le</dt><dd className="mt-1 font-semibold text-ink">{formatDate(document.issued_at)}</dd></div>
      </dl>

      <div className="mt-7 flex items-center justify-between gap-5 rounded-xl bg-canvas p-5">
        <span className="font-semibold text-muted">Montant documenté</span>
        <span className="text-2xl font-bold tracking-[-0.04em] text-ink">{formatMoney(document.amount)}</span>
      </div>

      {document.breakdown?.length > 1 ? (
        <div className="mt-5 overflow-hidden rounded-xl border border-line">
          <div className="grid grid-cols-[1fr_auto] gap-4 bg-canvas px-4 py-2 text-xs font-bold uppercase tracking-[0.08em] text-muted">
            <span>Affectation</span>
            <span>Montant</span>
          </div>
          {document.breakdown.map((item) => (
            <div
              className="grid grid-cols-[1fr_auto] gap-4 border-t border-line px-4 py-3 text-sm"
              key={item.obligation_id}
            >
              <span className="font-medium text-ink">{item.label}</span>
              <span className="font-semibold text-ink">
                {formatMoney(item.amount)}
              </span>
            </div>
          ))}
        </div>
      ) : null}

      <footer className="mt-8 flex items-start gap-3 text-xs leading-5 text-muted">
        <BadgeCheck aria-hidden="true" className="mt-0.5 shrink-0 text-brand" size={18} />
        <p>Ce document est un instantané vérifiable généré par ImmoLib. Sa référence et son statut permettent de contrôler sa validité.</p>
      </footer>
    </article>
  );
}
