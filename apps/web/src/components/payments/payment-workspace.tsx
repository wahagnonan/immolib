"use client";

import {
  Ban,
  Banknote,
  CalendarRange,
  HandCoins,
  Landmark,
  MoreHorizontal,
  RotateCcw,
  ShieldCheck,
  Smartphone,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { Feedback } from "@/components/ui/feedback";
import { Modal } from "@/components/ui/modal";
import { ModuleHeader } from "@/components/ui/module-header";
import {
  cancelPayment,
  listHouses,
  listLeaseObligations,
  listLeases,
  listPaymentsPage,
  listSecurityDeposits,
  preparePaymentObligations,
  recordPayment,
  settleSecurityDeposit,
} from "@/lib/api-client";
import { formatDate, formatMoney, monthLabel } from "@/lib/format";
import type {
  House,
  Lease,
  Payment,
  PaymentMethod,
  RentCharge,
  SecurityDeposit,
  SecurityDepositMovementType,
} from "@/types/domain";

const methodOptions: Array<{
  value: PaymentMethod;
  label: string;
  icon: typeof Banknote;
}> = [
  { value: "CASH", label: "Espèces", icon: Banknote },
  { value: "BANK_TRANSFER", label: "Virement bancaire", icon: Landmark },
  {
    value: "EXTERNAL_MOBILE_MONEY",
    label: "Mobile Money hors ImmoLib",
    icon: Smartphone,
  },
  { value: "OTHER", label: "Autre", icon: MoreHorizontal },
];

const statusStyle: Record<Payment["status"], string> = {
  RECORDED_BY_OWNER: "status-partial",
  CONFIRMED_BY_TENANT: "status-paid",
  CONFIRMED_BY_PROVIDER: "status-paid",
  DISPUTED_BY_TENANT: "bg-red-50 text-red-700",
  CANCELLED: "bg-zinc-100 text-zinc-700",
};

type AllocationDraft = {
  obligation: RentCharge;
  amount: string;
};

type PaymentDraft = {
  lease_id: string;
  period_start: string;
  period_end: string;
  include_rent: boolean;
  include_security_deposit: boolean;
  method: PaymentMethod;
  received_at: string;
  external_reference: string;
  note: string;
};

function currentMonth() {
  return new Date().toISOString().slice(0, 7);
}

function defaultForm(): PaymentDraft {
  const month = currentMonth();
  return {
    lease_id: "",
    period_start: month,
    period_end: month,
    include_rent: true,
    include_security_deposit: false,
    method: "CASH",
    received_at: new Date().toISOString().slice(0, 16),
    external_reference: "",
    note: "",
  };
}

function payable(obligation: RentCharge) {
  return (
    Number(obligation.balance_due) > 0 &&
    !["CANCELLED", "DISPUTED"].includes(obligation.status)
  );
}

export function PaymentWorkspace({
  initialChargeId,
}: {
  initialChargeId?: string;
}) {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [paymentPage, setPaymentPage] = useState(1);
  const [paymentCount, setPaymentCount] = useState(0);
  const [obligations, setObligations] = useState<RentCharge[]>([]);
  const [leases, setLeases] = useState<Lease[]>([]);
  const [houses, setHouses] = useState<House[]>([]);
  const [deposits, setDeposits] = useState<SecurityDeposit[]>([]);
  const [form, setForm] = useState<PaymentDraft>(defaultForm);
  const [allocations, setAllocations] = useState<AllocationDraft[]>([]);
  const [open, setOpen] = useState(Boolean(initialChargeId));
  const [preparing, setPreparing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selectedPayment, setSelectedPayment] = useState<Payment | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [settlingDeposit, setSettlingDeposit] =
    useState<SecurityDeposit | null>(null);
  const [settlementType, setSettlementType] =
    useState<SecurityDepositMovementType>("REFUND");
  const [settlementAmount, setSettlementAmount] = useState("");
  const [settlementReason, setSettlementReason] = useState("");
  const [settlementTarget, setSettlementTarget] = useState("");
  const [agreementConfirmed, setAgreementConfirmed] = useState(false);
  const [agreementReference, setAgreementReference] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh(targetPage = paymentPage) {
    const [paymentData, obligationData, leaseData, houseData, depositData] =
      await Promise.all([
        listPaymentsPage({ page: targetPage }),
        listLeaseObligations(),
        listLeases(),
        listHouses(),
        listSecurityDeposits(),
      ]);
    setPayments(paymentData.results);
    setPaymentCount(paymentData.count);
    setObligations(obligationData);
    setLeases(leaseData.filter((lease) => lease.status === "ACTIVE"));
    setHouses(houseData);
    setDeposits(depositData);

    if (initialChargeId) {
      const initial = obligationData.find((item) => item.id === initialChargeId);
      if (initial && payable(initial)) {
        setForm((current) => ({
          ...current,
          lease_id: initial.lease_id,
          period_start: initial.period,
          period_end: initial.period,
        }));
        setAllocations([
          { obligation: initial, amount: initial.balance_due },
        ]);
      }
    }
  }

  useEffect(() => {
    let active = true;
    Promise.all([
      listPaymentsPage({ page: paymentPage }),
      listLeaseObligations(),
      listLeases(),
      listHouses(),
      listSecurityDeposits(),
    ])
      .then(([paymentData, obligationData, leaseData, houseData, depositData]) => {
        if (!active) return;
        setPayments(paymentData.results);
        setPaymentCount(paymentData.count);
        setObligations(obligationData);
        setLeases(leaseData.filter((lease) => lease.status === "ACTIVE"));
        setHouses(houseData);
        setDeposits(depositData);

        if (initialChargeId) {
          const initial = obligationData.find(
            (item) => item.id === initialChargeId,
          );
          if (initial && payable(initial)) {
            setForm((current) => ({
              ...current,
              lease_id: initial.lease_id,
              period_start: initial.period,
              period_end: initial.period,
            }));
            setAllocations([
              { obligation: initial, amount: initial.balance_due },
            ]);
          }
        }
      })
      .catch((caughtError) => {
        if (!active) return;
        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "Chargement impossible.",
        );
      });
    return () => {
      active = false;
    };
  }, [initialChargeId, paymentPage]);

  const housesById = useMemo(
    () => new Map(houses.map((house) => [house.id, house])),
    [houses],
  );
  const obligationsById = useMemo(
    () => new Map(obligations.map((item) => [item.id, item])),
    [obligations],
  );
  const activePayments = payments.filter(
    (payment) => payment.status !== "CANCELLED" && payment.is_cash_movement,
  );
  const total = activePayments.reduce(
    (sum, payment) => sum + Number(payment.amount),
    0,
  );
  const confirmed = activePayments.filter((payment) =>
    ["CONFIRMED_BY_TENANT", "CONFIRMED_BY_PROVIDER"].includes(payment.status),
  ).length;
  const disputed = activePayments.filter(
    (payment) => payment.status === "DISPUTED_BY_TENANT",
  ).length;
  const allocationTotal = allocations.reduce(
    (sum, item) => sum + Number(item.amount || 0),
    0,
  );
  const selectedLease = leases.find((lease) => lease.id === form.lease_id);
  const settlementTargets = obligations.filter(
    (obligation) =>
      obligation.obligation_type === "RENT" &&
      obligation.lease_id === settlingDeposit?.lease_id &&
      payable(obligation),
  );

  function updateForm<K extends keyof PaymentDraft>(
    field: K,
    value: PaymentDraft[K],
  ) {
    setForm((current) => ({ ...current, [field]: value }));
    if (
      [
        "lease_id",
        "period_start",
        "period_end",
        "include_rent",
        "include_security_deposit",
      ].includes(field)
    ) {
      setAllocations([]);
    }
  }

  function openForm() {
    setForm(defaultForm());
    setAllocations([]);
    setError(null);
    setOpen(true);
  }

  async function handlePrepare() {
    if (!form.lease_id) {
      setError("Sélectionnez un bail actif.");
      return;
    }
    const hasRentPeriod = Boolean(
      form.include_rent && form.period_start && form.period_end,
    );
    if (!hasRentPeriod && !form.include_security_deposit) {
      setError("Sélectionnez la caution ou une période de loyer.");
      return;
    }
    setPreparing(true);
    setError(null);
    try {
      const result = await preparePaymentObligations({
        lease_id: form.lease_id,
        period_start: hasRentPeriod ? form.period_start : undefined,
        period_end: hasRentPeriod ? form.period_end : undefined,
        include_security_deposit: form.include_security_deposit,
      });
      const drafts = result.obligations
        .filter(payable)
        .map((obligation) => ({
          obligation,
          amount: obligation.balance_due,
        }));
      setAllocations(drafts);
      if (!drafts.length) {
        setError("Les obligations sélectionnées sont déjà entièrement réglées.");
      }
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Préparation impossible.",
      );
    } finally {
      setPreparing(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!allocations.length) {
      setError("Préparez d’abord la répartition du paiement.");
      return;
    }
    if (
      allocations.some(
        (item) =>
          Number(item.amount) <= 0 ||
          Number(item.amount) > Number(item.obligation.balance_due),
      )
    ) {
      setError("Vérifiez les montants affectés à chaque obligation.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await recordPayment({
        amount: allocationTotal.toFixed(2),
        allocations: allocations.map((item) => ({
          obligation_id: item.obligation.id,
          amount: Number(item.amount).toFixed(2),
        })),
        method: form.method,
        received_at: form.received_at,
        external_reference: form.external_reference,
        note: form.note,
        idempotency_key: crypto.randomUUID(),
      });
      setPaymentPage(1);
      await refresh(1);
      setOpen(false);
      setFeedback(
        "Paiement enregistré. Le reçu global et les documents des obligations soldées ont été générés.",
      );
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Enregistrement impossible.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleCancel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPayment) return;
    setSaving(true);
    setError(null);
    try {
      await cancelPayment(selectedPayment.id, cancelReason);
      await refresh();
      setSelectedPayment(null);
      setCancelReason("");
      setFeedback(
        "Paiement annulé. Les soldes et les documents concernés ont été recalculés.",
      );
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Annulation impossible.",
      );
    } finally {
      setSaving(false);
    }
  }

  function openSettlement(deposit: SecurityDeposit) {
    setSettlingDeposit(deposit);
    setSettlementType("REFUND");
    setSettlementAmount(deposit.held_balance);
    setSettlementReason("");
    setSettlementTarget("");
    setAgreementConfirmed(false);
    setAgreementReference("");
    setError(null);
  }

  async function handleSettlement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!settlingDeposit) return;
    setSaving(true);
    setError(null);
    try {
      await settleSecurityDeposit(settlingDeposit.id, {
        movement_type: settlementType,
        amount: settlementAmount,
        reason: settlementReason,
        target_rent_charge_id:
          settlementType === "APPLY_TO_RENT" ? settlementTarget : null,
        agreement_confirmed:
          settlementType === "APPLY_TO_RENT" && agreementConfirmed,
        agreement_reference:
          settlementType === "APPLY_TO_RENT" ? agreementReference : "",
        idempotency_key: crypto.randomUUID(),
      });
      await refresh();
      setSettlingDeposit(null);
      setFeedback(
        "Mouvement de caution enregistré. Le relevé vérifiable est disponible dans les documents.",
      );
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Clôture de caution impossible.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <ModuleHeader
        action={
          <button
            className="primary-button w-fit"
            onClick={openForm}
            type="button"
          >
            <HandCoins aria-hidden="true" size={18} />
            Enregistrer un paiement
          </button>
        }
        description="Répartissez une opération entre la caution et autant de mois de loyer que nécessaire. Aucun solde n’est conservé dans un portefeuille ImmoLib."
        eyebrow="Encaissements"
        title="Paiements"
      />
      <Feedback message={feedback} />
      <Feedback message={error} tone="error" />

      <section className="grid gap-3 sm:grid-cols-3">
        <div className="panel p-4">
          <p className="text-xs font-bold uppercase tracking-[0.1em] text-muted">
            Encaissé
          </p>
          <p className="mt-1 text-2xl font-semibold text-ink">
            {formatMoney(total)}
          </p>
        </div>
        <div className="panel p-4">
          <p className="text-xs font-bold uppercase tracking-[0.1em] text-muted">
            Confirmés
          </p>
          <p className="mt-1 text-2xl font-bold text-ink">{confirmed}</p>
        </div>
        <div className="panel p-4">
          <p className="text-xs font-bold uppercase tracking-[0.1em] text-muted">
            Contestés
          </p>
          <p className="mt-1 text-2xl font-bold text-red-700">{disputed}</p>
        </div>
      </section>

      <section className="panel overflow-hidden">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">Sans portefeuille ImmoLib</p>
            <h2 className="section-title">Cautions détenues</h2>
            <p className="mt-1 text-sm text-muted">
              Tracez un remboursement, une retenue justifiée ou une affectation
              au loyer. Les fonds restent hors ImmoLib.
            </p>
          </div>
          <span className="text-sm font-semibold text-muted">
            {deposits.filter((item) => Number(item.held_balance) > 0).length} à
            clôturer
          </span>
        </div>
        <div className="divide-y divide-line">
          {deposits.map((deposit) => (
            <div
              className="grid gap-4 px-5 py-4 sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-center sm:px-6"
              key={deposit.id}
            >
              <div>
                <p className="font-bold text-ink">{deposit.house_name}</p>
                <p className="mt-1 text-sm text-muted">{deposit.tenant_name}</p>
              </div>
              <div className="sm:text-right">
                <p className="font-bold text-ink">
                  {formatMoney(deposit.held_balance)} détenus
                </p>
                <p className="mt-1 text-xs text-muted">
                  {deposit.deposit_state_label} ·{" "}
                  {formatMoney(deposit.amount_released)} déjà libérés
                </p>
              </div>
              {Number(deposit.held_balance) > 0 ? (
                <button
                  className="secondary-button"
                  onClick={() => openSettlement(deposit)}
                  type="button"
                >
                  <RotateCcw aria-hidden="true" size={17} />
                  Clôturer
                </button>
              ) : (
                <span className="status-pill status-paid">Clôturée</span>
              )}
            </div>
          ))}
          {!deposits.length ? (
            <p className="px-5 py-10 text-center text-sm text-muted">
              Aucune caution encaissée pour le moment.
            </p>
          ) : null}
        </div>
      </section>

      <section className="panel overflow-hidden">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">Journal</p>
            <h2 className="section-title">Historique des paiements</h2>
          </div>
          <span className="text-sm font-semibold text-muted">
            {paymentCount} opération(s)
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="data-table min-w-[1020px]">
            <thead>
              <tr>
                <th>Bien et locataire</th>
                <th>Affectations</th>
                <th>Moyen</th>
                <th>Reçu le</th>
                <th>Statut</th>
                <th className="text-right">Montant</th>
                <th>
                  <span className="sr-only">Action</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {!payments.length ? (
                <tr>
                  <td className="py-12 text-center text-muted" colSpan={7}>
                    Aucun paiement enregistré pour le moment.
                  </td>
                </tr>
              ) : null}
              {payments.map((payment) => {
                const first = payment.allocations[0];
                const obligation = first
                  ? obligationsById.get(first.obligation_id)
                  : undefined;
                return (
                  <tr key={payment.id}>
                    <td>
                      <p className="font-bold text-ink">
                        {obligation?.house_name ?? "Bien"}
                      </p>
                      <p className="mt-1 text-xs">
                        {obligation?.tenant_name ?? "Locataire"}
                      </p>
                    </td>
                    <td>
                      <p className="font-semibold text-ink">
                        {payment.allocations.length} affectation(s)
                      </p>
                      <p className="mt-1 max-w-64 truncate text-xs">
                        {payment.allocations
                          .map((item) => item.obligation_label)
                          .join(", ")}
                      </p>
                    </td>
                    <td>{payment.method_label}</td>
                    <td>{formatDate(payment.received_at)}</td>
                    <td>
                      <span
                        className={`status-pill ${statusStyle[payment.status]}`}
                      >
                        {payment.status_label}
                      </span>
                    </td>
                    <td className="text-right font-bold text-ink">
                      {formatMoney(payment.amount)}
                    </td>
                    <td>
                      {payment.is_cash_movement && !["CANCELLED", "CONFIRMED_BY_PROVIDER"].includes(
                        payment.status,
                      ) ? (
                        <button
                          className="text-link text-red-700"
                          onClick={() => {
                            setSelectedPayment(payment);
                            setError(null);
                          }}
                          type="button"
                        >
                          <Ban aria-hidden="true" size={16} /> Annuler
                        </button>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {paymentCount > 25 ? (
          <div className="flex items-center justify-between gap-3 border-t border-line px-5 py-4">
            <button
              className="secondary-button"
              disabled={paymentPage === 1}
              onClick={() => setPaymentPage((current) => current - 1)}
              type="button"
            >
              Précédent
            </button>
            <span className="text-sm font-semibold text-muted">
              Page {paymentPage} sur {Math.ceil(paymentCount / 25)}
            </span>
            <button
              className="secondary-button"
              disabled={paymentPage >= Math.ceil(paymentCount / 25)}
              onClick={() => setPaymentPage((current) => current + 1)}
              type="button"
            >
              Suivant
            </button>
          </div>
        ) : null}
      </section>

      <Modal
        description="Cette opération est ajoutée au journal de la caution. Elle ne transfère aucun fonds dans ImmoLib."
        kicker="Cycle de vie de la caution"
        onClose={() => setSettlingDeposit(null)}
        open={Boolean(settlingDeposit)}
        title="Clôturer la caution"
      >
        <form className="p-5 sm:p-6" onSubmit={handleSettlement}>
          <div className="grid gap-5">
            <label>
              <span className="form-label">Décision *</span>
              <select
                className="form-input"
                onChange={(event) =>
                  setSettlementType(
                    event.target.value as SecurityDepositMovementType,
                  )
                }
                value={settlementType}
              >
                <option value="REFUND">Remboursement au locataire</option>
                <option value="RETENTION">Retenue justifiée</option>
                <option value="APPLY_TO_RENT">Affectation à un loyer</option>
              </select>
            </label>
            <label>
              <span className="form-label">Montant *</span>
              <input
                className="form-input"
                max={settlingDeposit?.held_balance}
                min="1"
                onChange={(event) => setSettlementAmount(event.target.value)}
                required
                type="number"
                value={settlementAmount}
              />
              <span className="mt-1 block text-xs text-muted">
                Disponible : {formatMoney(settlingDeposit?.held_balance ?? 0)}
              </span>
            </label>
            {settlementType === "APPLY_TO_RENT" ? (
              <>
                <label>
                  <span className="form-label">Loyer concerné *</span>
                  <select
                    className="form-input"
                    onChange={(event) => setSettlementTarget(event.target.value)}
                    required
                    value={settlementTarget}
                  >
                    <option value="">Sélectionner une échéance</option>
                    {settlementTargets.map((target) => (
                      <option key={target.id} value={target.id}>
                        {monthLabel(target.period)} — solde{" "}
                        {formatMoney(target.balance_due)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span className="form-label">Référence de l’accord *</span>
                  <input
                    className="form-input"
                    maxLength={160}
                    onChange={(event) =>
                      setAgreementReference(event.target.value)
                    }
                    placeholder="Ex. avenant signé du 24/07/2026"
                    required
                    value={agreementReference}
                  />
                </label>
                <label className="flex items-start gap-3 rounded-xl border border-line p-4">
                  <input
                    checked={agreementConfirmed}
                    className="mt-1"
                    onChange={(event) =>
                      setAgreementConfirmed(event.target.checked)
                    }
                    required
                    type="checkbox"
                  />
                  <span className="text-sm text-ink">
                    Je confirme disposer de l’accord explicite du locataire pour
                    affecter cette caution au loyer.
                  </span>
                </label>
              </>
            ) : null}
            <label>
              <span className="form-label">
                Motif {settlementType === "RETENTION" ? "*" : ""}
              </span>
              <textarea
                className="form-input min-h-24 resize-y"
                onChange={(event) => setSettlementReason(event.target.value)}
                placeholder="Précisez la décision et les éléments utiles"
                required={settlementType === "RETENTION"}
                value={settlementReason}
              />
            </label>
          </div>
          <Feedback message={error} tone="error" />
          <div className="mt-7 flex flex-col-reverse gap-3 border-t border-line pt-5 sm:flex-row sm:justify-end">
            <button
              className="secondary-button"
              onClick={() => setSettlingDeposit(null)}
              type="button"
            >
              Retour
            </button>
            <button className="primary-button" disabled={saving} type="submit">
              <ShieldCheck aria-hidden="true" size={18} />
              Enregistrer le mouvement
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        description="Choisissez d’abord ce que le locataire règle, puis vérifiez la répartition avant l’enregistrement."
        kicker="Paiement hors ligne"
        onClose={() => setOpen(false)}
        open={open}
        size="xl"
        title="Enregistrer un paiement"
      >
        <form className="p-5 sm:p-6" onSubmit={handleSubmit}>
          <div className="grid gap-5 sm:grid-cols-2">
            <label className="sm:col-span-2">
              <span className="form-label">Bail actif *</span>
              <select
                className="form-input"
                onChange={(event) => updateForm("lease_id", event.target.value)}
                required
                value={form.lease_id}
              >
                <option value="">Sélectionner un bien et un locataire</option>
                {leases.map((lease) => (
                  <option key={lease.id} value={lease.id}>
                    {housesById.get(lease.house_id)?.name ?? "Bien"} —{" "}
                    {lease.tenant.full_name}
                  </option>
                ))}
              </select>
            </label>

            <label className="sm:col-span-2">
              <span className="form-label">Éléments à régler</span>
              <span className="flex min-h-11 items-center gap-3 rounded-[10px] border border-line px-3.5">
                <input
                  checked={form.include_rent}
                  onChange={(event) =>
                    updateForm("include_rent", event.target.checked)
                  }
                  type="checkbox"
                />
                <span className="text-sm font-semibold text-ink">
                  Inclure les loyers
                </span>
              </span>
            </label>

            <label>
              <span className="form-label">Premier mois</span>
              <input
                className="form-input"
                disabled={!form.include_rent}
                min={selectedLease?.start_date.slice(0, 7)}
                onChange={(event) =>
                  updateForm("period_start", event.target.value)
                }
                type="month"
                value={form.period_start}
              />
            </label>
            <label>
              <span className="form-label">Dernier mois</span>
              <input
                className="form-input"
                disabled={!form.include_rent}
                min={form.period_start || selectedLease?.start_date.slice(0, 7)}
                onChange={(event) =>
                  updateForm("period_end", event.target.value)
                }
                type="month"
                value={form.period_end}
              />
            </label>

            {selectedLease && Number(selectedLease.security_deposit) > 0 ? (
              <label className="sm:col-span-2 flex min-h-12 items-center gap-3 rounded-xl border border-line px-4">
                <input
                  checked={form.include_security_deposit}
                  onChange={(event) =>
                    updateForm(
                      "include_security_deposit",
                      event.target.checked,
                    )
                  }
                  type="checkbox"
                />
                <ShieldCheck aria-hidden="true" className="text-brand" size={19} />
                <span>
                  <span className="block text-sm font-semibold text-ink">
                    Inclure la caution
                  </span>
                  <span className="block text-xs text-muted">
                    Montant prévu :{" "}
                    {formatMoney(selectedLease.security_deposit)}
                  </span>
                </span>
              </label>
            ) : null}

            <div className="sm:col-span-2">
              <button
                className="secondary-button w-full"
                disabled={preparing || !form.lease_id}
                onClick={handlePrepare}
                type="button"
              >
                <CalendarRange aria-hidden="true" size={18} />
                {preparing
                  ? "Préparation…"
                  : "Préparer la répartition"}
              </button>
            </div>

            {allocations.length ? (
              <section className="sm:col-span-2 overflow-hidden rounded-xl border border-line">
                <div className="flex items-center justify-between bg-canvas px-4 py-3">
                  <div>
                    <p className="text-sm font-semibold text-ink">
                      Répartition
                    </p>
                    <p className="text-xs text-muted">
                      La caution reste séparée des loyers.
                    </p>
                  </div>
                  <p className="text-sm font-bold text-ink">
                    {formatMoney(allocationTotal)}
                  </p>
                </div>
                <div className="divide-y divide-line">
                  {allocations.map((item, index) => (
                    <div
                      className="grid gap-3 px-4 py-3 sm:grid-cols-[1fr_150px] sm:items-center"
                      key={item.obligation.id}
                    >
                      <div>
                        <p className="text-sm font-semibold text-ink">
                          {item.obligation.obligation_type ===
                          "SECURITY_DEPOSIT"
                            ? "Caution"
                            : monthLabel(item.obligation.period)}
                        </p>
                        <p className="text-xs text-muted">
                          Solde :{" "}
                          {formatMoney(item.obligation.balance_due)}
                        </p>
                      </div>
                      <label>
                        <span className="sr-only">
                          Montant pour {item.obligation.obligation_label}
                        </span>
                        <input
                          className="form-input text-right"
                          max={item.obligation.balance_due}
                          min="1"
                          onChange={(event) =>
                            setAllocations((current) =>
                              current.map((draft, draftIndex) =>
                                draftIndex === index
                                  ? { ...draft, amount: event.target.value }
                                  : draft,
                              ),
                            )
                          }
                          required
                          type="number"
                          value={item.amount}
                        />
                      </label>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}

            <label>
              <span className="form-label">Date de réception *</span>
              <input
                className="form-input"
                onChange={(event) =>
                  updateForm("received_at", event.target.value)
                }
                required
                type="datetime-local"
                value={form.received_at}
              />
            </label>
            <div />

            <fieldset className="sm:col-span-2">
              <legend className="form-label">Moyen *</legend>
              <div className="grid gap-3 sm:grid-cols-2">
                {methodOptions.map((option) => {
                  const Icon = option.icon;
                  return (
                    <label
                      className={`flex min-h-12 items-center gap-3 rounded-xl border px-4 text-sm font-semibold ${
                        form.method === option.value
                          ? "border-brand bg-brand-soft text-brand-dark"
                          : "border-line text-ink"
                      }`}
                      key={option.value}
                    >
                      <input
                        checked={form.method === option.value}
                        name="method"
                        onChange={() => updateForm("method", option.value)}
                        type="radio"
                      />
                      <Icon aria-hidden="true" size={18} />
                      {option.label}
                    </label>
                  );
                })}
              </div>
            </fieldset>
            <label className="sm:col-span-2">
              <span className="form-label">Référence externe</span>
              <input
                className="form-input"
                maxLength={120}
                onChange={(event) =>
                  updateForm("external_reference", event.target.value)
                }
                placeholder="Numéro de transaction ou référence bancaire"
                value={form.external_reference}
              />
            </label>
            <label className="sm:col-span-2">
              <span className="form-label">Note</span>
              <textarea
                className="form-input min-h-24 resize-y"
                onChange={(event) => updateForm("note", event.target.value)}
                placeholder="Information utile sur ce paiement"
                value={form.note}
              />
            </label>
          </div>
          <Feedback message={error} tone="error" />
          <div className="mt-7 flex flex-col-reverse gap-3 border-t border-line pt-5 sm:flex-row sm:justify-end">
            <button
              className="secondary-button"
              onClick={() => setOpen(false)}
              type="button"
            >
              Annuler
            </button>
            <button
              className="primary-button"
              disabled={saving || !allocations.length || allocationTotal <= 0}
              type="submit"
            >
              <HandCoins aria-hidden="true" size={18} />
              {saving
                ? "Enregistrement…"
                : `Enregistrer ${formatMoney(allocationTotal)}`}
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        description="Cette action reste tracée et invalide les documents qui ne sont plus justifiés."
        kicker="Correction"
        onClose={() => setSelectedPayment(null)}
        open={Boolean(selectedPayment)}
        title="Annuler le paiement"
      >
        <form className="p-5 sm:p-6" onSubmit={handleCancel}>
          <label>
            <span className="form-label">Motif de l’annulation *</span>
            <textarea
              className="form-input min-h-28 resize-y"
              minLength={3}
              onChange={(event) => setCancelReason(event.target.value)}
              placeholder="Ex. erreur de saisie du montant"
              required
              value={cancelReason}
            />
          </label>
          <Feedback message={error} tone="error" />
          <div className="mt-7 flex flex-col-reverse gap-3 border-t border-line pt-5 sm:flex-row sm:justify-end">
            <button
              className="secondary-button"
              onClick={() => setSelectedPayment(null)}
              type="button"
            >
              Retour
            </button>
            <button
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-red-700 px-4 text-sm font-bold text-white disabled:opacity-50"
              disabled={saving}
              type="submit"
            >
              <Ban aria-hidden="true" size={18} />
              Confirmer l’annulation
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
