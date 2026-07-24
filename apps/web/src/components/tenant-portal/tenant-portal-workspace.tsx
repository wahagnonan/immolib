"use client";

import {
  AlertTriangle,
  BadgeCheck,
  CalendarClock,
  Check,
  Download,
  Eye,
  FileCheck2,
  HandCoins,
  House,
  LoaderCircle,
  MapPin,
  MessageSquareWarning,
  RefreshCw,
  ShieldCheck,
  WalletCards,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { DocumentPaper } from "@/components/documents/document-paper";
import { TenantIncidentPanel } from "@/components/tenant-portal/tenant-incident-panel";
import { Feedback } from "@/components/ui/feedback";
import { Modal } from "@/components/ui/modal";
import {
  confirmTenantPortalPayment,
  disputeTenantPortalPayment,
  downloadTenantPortalDocumentPdf,
  getTenantPortalOverview,
  listTenantPortalCharges,
  listTenantPortalDocuments,
  listTenantPortalLeases,
  listTenantPortalPayments,
} from "@/lib/api-client";
import { rentalDocumentPdfFilename, saveBlob } from "@/lib/download";
import { formatDate, formatDateTime, monthLabel } from "@/lib/format";
import type {
  Payment,
  RentalDocument,
  RentCharge,
  TenantPortalLease,
  TenantPortalOverview,
} from "@/types/domain";

const EMPTY_OVERVIEW: TenantPortalOverview = {
  has_profile: false,
  profiles: [],
  active_leases: [],
  next_charge: null,
  balances: [],
  overdue_charge_count: 0,
  payment_to_review_count: 0,
  document_count: 0,
};

const chargeStatusStyle: Record<RentCharge["status"], string> = {
  PAID: "status-paid",
  PARTIALLY_PAID: "status-partial",
  UPCOMING: "status-vacant",
  DUE: "status-partial",
  OVERDUE: "status-late",
  DISPUTED: "status-late",
  CANCELLED: "bg-zinc-100 text-zinc-700",
};

const paymentStatusStyle: Record<Payment["status"], string> = {
  RECORDED_BY_OWNER: "status-partial",
  CONFIRMED_BY_TENANT: "status-paid",
  CONFIRMED_BY_PROVIDER: "status-paid",
  DISPUTED_BY_TENANT: "status-late",
  CANCELLED: "bg-zinc-100 text-zinc-700",
};

function formatCurrency(value: string | number, currency = "XOF") {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function updatePaymentList(payments: Payment[], updated: Payment) {
  return payments.map((payment) =>
    payment.id === updated.id ? updated : payment,
  );
}

export function TenantPortalWorkspace() {
  const { user } = useAuth();
  const [overview, setOverview] = useState<TenantPortalOverview>(EMPTY_OVERVIEW);
  const [leases, setLeases] = useState<TenantPortalLease[]>([]);
  const [charges, setCharges] = useState<RentCharge[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [documents, setDocuments] = useState<RentalDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingPaymentId, setSavingPaymentId] = useState<string | null>(null);
  const [downloadingDocumentId, setDownloadingDocumentId] = useState<
    string | null
  >(null);
  const [disputing, setDisputing] = useState<Payment | null>(null);
  const [disputeReason, setDisputeReason] = useState("");
  const [preview, setPreview] = useState<RentalDocument | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadPortal = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [overviewData, leaseData, chargeData, paymentData, documentData] =
        await Promise.all([
          getTenantPortalOverview(),
          listTenantPortalLeases(),
          listTenantPortalCharges(),
          listTenantPortalPayments(),
          listTenantPortalDocuments(),
        ]);
      setOverview(overviewData);
      setLeases(leaseData);
      setCharges(chargeData);
      setPayments(paymentData);
      setDocuments(documentData);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible de charger votre espace locataire.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([
      getTenantPortalOverview(),
      listTenantPortalLeases(),
      listTenantPortalCharges(),
      listTenantPortalPayments(),
      listTenantPortalDocuments(),
    ])
      .then(
        ([overviewData, leaseData, chargeData, paymentData, documentData]) => {
          if (!active) return;
          setOverview(overviewData);
          setLeases(leaseData);
          setCharges(chargeData);
          setPayments(paymentData);
          setDocuments(documentData);
        },
      )
      .catch((caughtError) => {
        if (!active) return;
        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "Impossible de charger votre espace locataire.",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const chargesById = useMemo(
    () => new Map(charges.map((charge) => [charge.id, charge])),
    [charges],
  );
  const profile = overview.profiles[0];
  const displayName =
    profile?.full_name || user?.full_name || user?.phone || "locataire";
  const firstName = displayName.trim().split(/\s+/)[0];

  async function handleConfirm(payment: Payment) {
    setSavingPaymentId(payment.id);
    setError(null);
    setFeedback(null);
    try {
      const updated = await confirmTenantPortalPayment(payment.id);
      setPayments((current) => updatePaymentList(current, updated));
      if (payment.status === "RECORDED_BY_OWNER") {
        setOverview((current) => ({
          ...current,
          payment_to_review_count: Math.max(
            0,
            current.payment_to_review_count - 1,
          ),
        }));
      }
      setFeedback("Paiement confirmé. Votre réponse est maintenant tracée.");
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Confirmation impossible.",
      );
    } finally {
      setSavingPaymentId(null);
    }
  }

  async function handleDispute(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!disputing) return;
    setSavingPaymentId(disputing.id);
    setError(null);
    setFeedback(null);
    try {
      const updated = await disputeTenantPortalPayment(
        disputing.id,
        disputeReason.trim(),
      );
      setPayments((current) => updatePaymentList(current, updated));
      setOverview((current) => ({
        ...current,
        payment_to_review_count:
          disputing.status === "RECORDED_BY_OWNER"
            ? Math.max(0, current.payment_to_review_count - 1)
            : current.payment_to_review_count,
      }));
      setDisputing(null);
      setDisputeReason("");
      setFeedback(
        "Contestation enregistrée. Le bailleur verra votre motif dans l’historique.",
      );
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Contestation impossible.",
      );
    } finally {
      setSavingPaymentId(null);
    }
  }

  async function handlePdfDownload(document: RentalDocument) {
    setDownloadingDocumentId(document.id);
    setError(null);
    try {
      const pdf = await downloadTenantPortalDocumentPdf(document.id);
      saveBlob(pdf, rentalDocumentPdfFilename(document));
      setFeedback("Document PDF téléchargé.");
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Téléchargement impossible.",
      );
    } finally {
      setDownloadingDocumentId(null);
    }
  }

  if (loading) {
    return (
      <div className="space-y-5">
        <div className="h-28 animate-pulse rounded-2xl bg-white" />
        <div className="grid gap-4 md:grid-cols-3">
          {[0, 1, 2].map((item) => (
            <div className="metric-card h-40 animate-pulse" key={item} />
          ))}
        </div>
        <p className="flex items-center gap-2 text-sm font-semibold text-muted">
          <LoaderCircle aria-hidden="true" className="animate-spin" size={18} />
          Chargement de votre dossier locatif…
        </p>
      </div>
    );
  }

  if (!overview.has_profile) {
    return (
      <section className="panel mx-auto max-w-2xl p-7 text-center sm:p-10">
        <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-sky-soft text-sky-dark">
          <ShieldCheck aria-hidden="true" size={28} />
        </span>
        <h1 className="mt-5 text-2xl font-bold text-ink">
          Aucune location rattachée
        </h1>
        <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-muted">
          Ouvrez le lien d’invitation transmis par votre bailleur. Après la
          vérification de votre email ou téléphone, votre location apparaîtra ici.
        </p>
        <Feedback message={error} tone="error" />
      </section>
    );
  }

  const balanceSummary = overview.balances.length
    ? overview.balances
        .map((balance) => formatCurrency(balance.amount, balance.currency))
        .join(" · ")
    : formatCurrency(0);

  return (
    <div className="space-y-7">
      <section
        className="scroll-mt-28 flex flex-col justify-between gap-5 xl:flex-row xl:items-end"
        id="apercu"
      >
        <div>
          <p className="eyebrow">Mon dossier locatif</p>
          <h1 className="page-title">Bonjour {firstName},</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted sm:text-base">
            Retrouvez ce que vous devez payer, ce qui a été déclaré et toutes vos
            preuves sans demander un renvoi au bailleur.
          </p>
        </div>
        <button
          className="secondary-button w-fit"
          disabled={loading}
          onClick={() => void loadPortal()}
          type="button"
        >
          <RefreshCw aria-hidden="true" size={17} />
          Actualiser
        </button>
      </section>

      <Feedback message={feedback} />
      <Feedback message={error} tone="error" />

      <section aria-label="Synthèse locataire" className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="metric-card">
          <div className="metric-icon">
            <WalletCards aria-hidden="true" size={21} />
          </div>
          <p className="metric-label">Solde restant</p>
          <p className="metric-value">{balanceSummary}</p>
          <p className="metric-detail text-muted">
            {overview.overdue_charge_count
              ? `${overview.overdue_charge_count} échéance(s) en retard`
              : "Aucun retard déclaré"}
          </p>
        </article>

        <article className="metric-card">
          <div className="metric-icon">
            <CalendarClock aria-hidden="true" size={21} />
          </div>
          <p className="metric-label">Prochaine échéance</p>
          <p className="metric-value">
            {overview.next_charge
              ? formatCurrency(
                  overview.next_charge.balance_due,
                  overview.next_charge.currency,
                )
              : "À jour"}
          </p>
          <p className="metric-detail text-muted">
            {overview.next_charge
              ? `${monthLabel(overview.next_charge.period)} · ${formatDate(overview.next_charge.due_date)}`
              : "Aucun solde en attente"}
          </p>
        </article>

        <article className="metric-card">
          <div className="metric-icon">
            <HandCoins aria-hidden="true" size={21} />
          </div>
          <p className="metric-label">Paiements à vérifier</p>
          <p className="metric-value">{overview.payment_to_review_count}</p>
          <p className="metric-detail text-muted">
            <BadgeCheck aria-hidden="true" size={15} />
            Confirmez ou contestez
          </p>
        </article>

        <article className="metric-card">
          <div className="metric-icon">
            <FileCheck2 aria-hidden="true" size={21} />
          </div>
          <p className="metric-label">Documents actifs</p>
          <p className="metric-value">{overview.document_count}</p>
          <p className="metric-detail text-muted">
            Reçus et quittances disponibles
          </p>
        </article>
      </section>

      <section className="scroll-mt-28" id="location">
        <div className="mb-4">
          <p className="section-kicker">Contrat et maison</p>
          <h2 className="section-title">Ma location</h2>
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          {leases.map((lease) => (
            <article className="panel p-5 sm:p-6" key={lease.id}>
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                <div>
                  <p className="flex items-center gap-2 text-lg font-bold text-ink">
                    <House aria-hidden="true" className="text-brand" size={20} />
                    {lease.house.name}
                  </p>
                  <p className="mt-2 flex items-start gap-2 text-sm text-muted">
                    <MapPin aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
                    {lease.house.address}, {lease.house.commune || lease.house.city}
                  </p>
                </div>
                <span className="status-pill status-paid">{lease.status_label}</span>
              </div>
              <dl className="mt-6 grid gap-4 border-t border-line pt-5 sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Loyer mensuel</dt>
                  <dd className="mt-1 font-bold text-ink">{formatCurrency(lease.monthly_rent, lease.currency)}</dd>
                </div>
                <div>
                  <dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Charges</dt>
                  <dd className="mt-1 font-bold text-ink">{formatCurrency(lease.monthly_charges, lease.currency)}</dd>
                </div>
                <div>
                  <dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Échéance</dt>
                  <dd className="mt-1 font-bold text-ink">Le {lease.due_day} de chaque mois</dd>
                </div>
                <div>
                  <dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Période du bail</dt>
                  <dd className="mt-1 font-bold text-ink">
                    {formatDate(lease.start_date)} — {lease.end_date ? formatDate(lease.end_date) : "sans date de fin"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Caution</dt>
                  <dd className="mt-1 font-bold text-ink">{formatCurrency(lease.security_deposit, lease.currency)}</dd>
                </div>
                <div>
                  <dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Moyens prévus</dt>
                  <dd className="mt-1 font-bold text-ink">
                    {[lease.accepts_cash ? "Espèces" : "", lease.accepts_mobile_money ? "Mobile Money" : ""].filter(Boolean).join(" · ") || "À préciser"}
                  </dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      </section>

      <section className="panel scroll-mt-28 overflow-hidden" id="echeances">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">Calendrier</p>
            <h2 className="section-title">Mes échéances</h2>
          </div>
        </div>
        {charges.length ? (
          <div className="overflow-x-auto">
            <table className="data-table min-w-[780px]">
              <thead>
                <tr>
                  <th>Période</th>
                  <th>Maison</th>
                  <th>Échéance</th>
                  <th>Statut</th>
                  <th className="text-right">Payé</th>
                  <th className="text-right">Reste</th>
                </tr>
              </thead>
              <tbody>
                {charges.map((charge) => (
                  <tr key={charge.id}>
                    <td className="font-semibold capitalize text-ink">{monthLabel(charge.period)}</td>
                    <td>{charge.house_name}</td>
                    <td>{formatDate(charge.due_date)}</td>
                    <td><span className={`status-pill ${chargeStatusStyle[charge.status]}`}>{charge.status_label}</span></td>
                    <td className="text-right">{formatCurrency(charge.amount_paid, charge.currency)}</td>
                    <td className="text-right font-bold text-ink">{formatCurrency(charge.balance_due, charge.currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="px-6 py-12 text-center text-sm text-muted">Aucune échéance disponible.</p>
        )}
      </section>

      <section className="panel scroll-mt-28 overflow-hidden" id="paiements">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">Traçabilité</p>
            <h2 className="section-title">Mes paiements</h2>
            <p className="mt-1 text-sm text-muted">
              Une confirmation atteste que vous reconnaissez la déclaration du bailleur.
            </p>
          </div>
        </div>
        {payments.length ? (
          <div className="divide-y divide-line">
            {payments.map((payment) => {
              const charge = payment.allocations
                .map((allocation) => chargesById.get(allocation.rent_charge_id))
                .find(Boolean);
              const canConfirm =
                payment.status === "RECORDED_BY_OWNER" ||
                payment.status === "DISPUTED_BY_TENANT";
              const canDispute =
                payment.status !== "CANCELLED" &&
                payment.status !== "CONFIRMED_BY_PROVIDER" &&
                payment.status !== "DISPUTED_BY_TENANT";
              return (
                <article className="grid gap-4 px-5 py-5 sm:px-6 xl:grid-cols-[minmax(0,1fr)_auto_auto] xl:items-center" key={payment.id}>
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-bold text-ink">{formatCurrency(payment.amount, payment.currency)}</p>
                      <span className={`status-pill ${paymentStatusStyle[payment.status]}`}>{payment.status_label}</span>
                    </div>
                    <p className="mt-2 text-sm text-muted">
                      {payment.method_label} · {charge?.house_name ?? "Maison"} · {payment.allocations[0] ? monthLabel(payment.allocations[0].period) : "Période non précisée"}
                    </p>
                    <p className="mt-1 text-xs text-muted">
                      Déclaré le {formatDateTime(payment.received_at)}
                      {payment.external_reference ? ` · Réf. ${payment.external_reference}` : ""}
                    </p>
                    {payment.note ? <p className="mt-2 text-sm italic text-muted">« {payment.note} »</p> : null}
                  </div>
                  <div className="text-sm xl:text-right">
                    <p className="text-muted">Dernière mise à jour</p>
                    <p className="mt-1 font-semibold text-ink">{formatDateTime(payment.updated_at)}</p>
                  </div>
                  <div className="flex flex-wrap gap-2 xl:justify-end">
                    {canConfirm ? (
                      <button
                        className="primary-button"
                        disabled={savingPaymentId === payment.id}
                        onClick={() => void handleConfirm(payment)}
                        type="button"
                      >
                        <Check aria-hidden="true" size={17} />
                        Confirmer
                      </button>
                    ) : null}
                    {canDispute ? (
                      <button
                        className="secondary-button"
                        disabled={savingPaymentId === payment.id}
                        onClick={() => {
                          setDisputing(payment);
                          setDisputeReason("");
                        }}
                        type="button"
                      >
                        <MessageSquareWarning aria-hidden="true" size={17} />
                        Contester
                      </button>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <p className="px-6 py-12 text-center text-sm text-muted">Aucun paiement déclaré.</p>
        )}
      </section>

      <section className="scroll-mt-28" id="documents">
        <div className="mb-4">
          <p className="section-kicker">Preuves</p>
          <h2 className="section-title">Mes reçus et quittances</h2>
        </div>
        {documents.length ? (
          <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
            {documents.map((document) => (
              <article className="panel p-5" key={document.id}>
                <div className="flex items-start justify-between gap-3">
                  <span className="grid size-10 place-items-center rounded-xl bg-brand-soft text-brand">
                    <FileCheck2 aria-hidden="true" size={20} />
                  </span>
                  <span className={`status-pill ${document.status === "ACTIVE" ? "status-paid" : "status-late"}`}>
                    {document.status_label}
                  </span>
                </div>
                <p className="mt-5 text-xs font-bold uppercase tracking-[0.1em] text-muted">{document.reference}</p>
                <h3 className="mt-2 text-lg font-bold text-ink">{document.document_type_label}</h3>
                <p className="mt-1 text-sm capitalize text-muted">{document.house_name} · {monthLabel(document.period)}</p>
                <p className="mt-5 text-xl font-bold text-ink">{formatCurrency(document.amount, document.currency)}</p>
                <p className="mt-1 text-xs text-muted">Émis le {formatDate(document.issued_at)}</p>
                <div className="mt-5 grid grid-cols-2 gap-2">
                  <button className="secondary-button" onClick={() => setPreview(document)} type="button">
                    <Eye aria-hidden="true" size={17} />
                    Voir
                  </button>
                  <button
                    className="primary-button"
                    disabled={downloadingDocumentId === document.id}
                    onClick={() => void handlePdfDownload(document)}
                    type="button"
                  >
                    <Download aria-hidden="true" size={17} />
                    PDF
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="panel p-8 text-center text-sm text-muted">
            Les reçus apparaîtront après un paiement et la quittance après le règlement complet de l’échéance.
          </div>
        )}
      </section>

      <TenantIncidentPanel leases={leases} />

      <section className="rounded-[14px] border border-line bg-white p-5 text-sm leading-6 text-muted">
        <p className="flex items-center gap-2 font-bold">
          <AlertTriangle aria-hidden="true" size={18} />
          À propos des paiements
        </p>
        <p className="mt-2">
          ImmoLib ne conserve pas votre loyer dans un portefeuille. Les
          paiements Mobile Money reçus par webhook signé sont confirmés
          automatiquement ; les paiements déclarés hors fournisseur restent
          soumis à votre confirmation.
        </p>
      </section>

      <Modal
        description="Expliquez précisément ce qui ne correspond pas. Le motif sera conservé dans l’historique du paiement."
        kicker="Réponse locataire"
        onClose={() => {
          setDisputing(null);
          setDisputeReason("");
        }}
        open={Boolean(disputing)}
        title="Contester ce paiement"
      >
        <form className="p-5 sm:p-6" onSubmit={handleDispute}>
          {disputing ? (
            <div className="rounded-xl border border-line bg-canvas p-4 text-sm">
              <p className="font-bold text-ink">{formatCurrency(disputing.amount, disputing.currency)}</p>
              <p className="mt-1 text-muted">{disputing.method_label} · {formatDateTime(disputing.received_at)}</p>
            </div>
          ) : null}
          <label className="mt-5 block">
            <span className="form-label">Motif de la contestation *</span>
            <textarea
              className="form-input min-h-28 resize-y"
              maxLength={2000}
              minLength={3}
              onChange={(event) => setDisputeReason(event.target.value)}
              placeholder="Exemple : je ne reconnais pas ce montant ou cette date."
              required
              value={disputeReason}
            />
          </label>
          <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button className="secondary-button" onClick={() => setDisputing(null)} type="button">Annuler</button>
            <button className="primary-button" disabled={!disputeReason.trim() || Boolean(savingPaymentId)} type="submit">
              <MessageSquareWarning aria-hidden="true" size={17} />
              Enregistrer la contestation
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        kicker="Aperçu du document"
        onClose={() => setPreview(null)}
        open={Boolean(preview)}
        size="xl"
        title={preview?.document_type_label ?? "Document"}
      >
        <div className="bg-canvas p-4 sm:p-7">
          {preview ? <DocumentPaper document={preview} /> : null}
        </div>
      </Modal>
    </div>
  );
}
