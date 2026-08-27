"use client";

import {
  Check,
  HandCoins,
  Landmark,
  LoaderCircle,
  MoreHorizontal,
  Plus,
  RefreshCw,
  ShieldAlert,
  Smartphone,
  Star,
  Trash2,
  WalletCards,
  X,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { Feedback } from "@/components/ui/feedback";
import { Modal } from "@/components/ui/modal";
import { ModuleHeader } from "@/components/ui/module-header";
import {
  cancelPaymentRequest,
  confirmPaymentRequest,
  createPaymentMethod,
  deletePaymentMethod,
  getPiSpiStatus,
  initiatePayment,
  initiatePiSpiPayment,
  listLandlordPaymentRequests,
  listMyPaymentRequests,
  listPaymentMethods,
  listTenantPortalCharges,
  refusePaymentRequest,
  setDefaultPaymentMethod,
} from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import type {
  PaymentMethodAccount,
  PaymentRequest,
  PaymentRequestOperator,
  PaymentRequestStatus,
  RentCharge,
} from "@/types/domain";

const operatorOptions: Array<{
  value: PaymentRequestOperator;
  label: string;
  icon: typeof Smartphone;
}> = [
  { value: "MTN_MOMO", label: "MTN MoMo", icon: Smartphone },
  { value: "ORANGE_MONEY", label: "Orange Money", icon: Smartphone },
  { value: "MOOV_MONEY", label: "Moov Money", icon: Smartphone },
  { value: "WAVE", label: "Wave", icon: Smartphone },
  { value: "PI_SPI", label: "PI-SPI (BCEAO)", icon: Landmark },
  { value: "BANK_TRANSFER", label: "Virement bancaire", icon: Landmark },
  { value: "CASH", label: "Espèces", icon: HandCoins },
  { value: "OTHER", label: "Autre", icon: MoreHorizontal },
];

const statusStyle: Record<PaymentRequestStatus, string> = {
  PENDING: "status-partial",
  PROCESSING: "status-partial",
  CONFIRMED: "status-paid",
  NOT_RECEIVED: "status-late",
  CANCELLED: "bg-zinc-100 text-zinc-700",
  FAILED: "status-late",
  EXPIRED: "bg-zinc-100 text-zinc-700",
};

function formatMoney(value: string | number) {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "XOF",
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function payable(charge: RentCharge) {
  return (
    Number(charge.balance_due) > 0 &&
    charge.obligation_type === "RENT" &&
    !["CANCELLED", "DISPUTED"].includes(charge.status)
  );
}

export function PaymentRequestsWorkspace({
  mode,
}: {
  mode: "landlord" | "tenant";
}) {
  const isLandlord = mode === "landlord";

  const [requests, setRequests] = useState<PaymentRequest[]>([]);
  const [statusFilter, setStatusFilter] = useState<PaymentRequestStatus | "">("");
  const [charges, setCharges] = useState<RentCharge[]>([]);
  const [methods, setMethods] = useState<PaymentMethodAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [confirmTarget, setConfirmTarget] = useState<PaymentRequest | null>(null);
  const [confirmAmount, setConfirmAmount] = useState("");
  const [confirmNote, setConfirmNote] = useState("");
  const [refuseTarget, setRefuseTarget] = useState<PaymentRequest | null>(null);
  const [refuseReason, setRefuseReason] = useState("");
  const [cancelTarget, setCancelTarget] = useState<PaymentRequest | null>(null);
  const [cancelReason, setCancelReason] = useState("");

  const [methodOpen, setMethodOpen] = useState(false);
  const [methodOperator, setMethodOperator] =
    useState<PaymentRequestOperator>("MTN_MOMO");
  const [methodIdentifier, setMethodIdentifier] = useState("");
  const [methodHolder, setMethodHolder] = useState("");
  const [methodDefault, setMethodDefault] = useState(false);

  const [chargeId, setChargeId] = useState("");
  const [initiateAmount, setInitiateAmount] = useState("");
  const [initiateOperator, setInitiateOperator] =
    useState<PaymentRequestOperator>("MTN_MOMO");

  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      if (isLandlord) {
        const [requestData, methodData] = await Promise.all([
          listLandlordPaymentRequests(
            statusFilter ? (statusFilter as PaymentRequestStatus) : undefined,
          ),
          listPaymentMethods(),
        ]);
        setRequests(requestData);
        setMethods(methodData);
      } else {
        const [requestData, chargeData] = await Promise.all([
          listMyPaymentRequests(),
          listTenantPortalCharges(),
        ]);
        setRequests(requestData);
        setCharges(chargeData.filter(payable));
        setChargeId((current) =>
          current && chargeData.some((charge) => charge.id === current)
            ? current
            : "",
        );
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Le chargement a échoué.");
    } finally {
      setLoading(false);
    }
  }, [isLandlord, statusFilter]);

  useEffect(() => {
    void Promise.resolve().then(load);
  }, [load]);

  async function run(action: () => Promise<unknown>, successMessage: string) {
    setSaving(true);
    setError(null);
    setFeedback(null);
    try {
      await action();
      setFeedback(successMessage);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "L'opération a échoué.");
    } finally {
      setSaving(false);
    }
  }

  function closeConfirmModal() {
    setConfirmTarget(null);
    setConfirmAmount("");
    setConfirmNote("");
  }

  function closeRefuseModal() {
    setRefuseTarget(null);
    setRefuseReason("");
  }

  function closeCancelModal() {
    setCancelTarget(null);
    setCancelReason("");
  }

  async function handleConfirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!confirmTarget) return;
    await run(
      () =>
        confirmPaymentRequest(confirmTarget.id, {
          received_amount: confirmAmount || undefined,
          note: confirmNote,
        }),
      "Paiement confirmé, quittance générée.",
    );
    if (!error) closeConfirmModal();
  }

  async function handleRefuse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!refuseTarget) return;
    await run(
      () => refusePaymentRequest(refuseTarget.id, refuseReason),
      "Demande refusée : fonds non reçus.",
    );
    if (!error) closeRefuseModal();
  }

  async function handleCancel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!cancelTarget) return;
    await run(
      () => cancelPaymentRequest(cancelTarget.id, cancelReason),
      "Demande annulée.",
    );
    if (!error) closeCancelModal();
  }

  async function handleCreateMethod(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(
      () =>
        createPaymentMethod({
          operator: methodOperator,
          account_identifier: methodIdentifier,
          account_holder: methodHolder,
          is_default: methodDefault,
        }),
      "Compte de réception ajouté.",
    );
    if (!error) {
      setMethodOpen(false);
      setMethodIdentifier("");
      setMethodHolder("");
      setMethodDefault(false);
    }
  }

  async function handleInitiate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!chargeId) return;
    await run(
      () =>
        initiatePayment({
          rent_charge_id: chargeId,
          amount: initiateAmount,
          operator: initiateOperator,
        }),
      "Demande de paiement envoyée au bailleur.",
    );
    if (!error) {
      setInitiateAmount("");
      setInitiateOperator("MTN_MOMO");
    }
  }

  return (
    <section className="grid gap-6">
      <ModuleHeader
        eyebrow="Paiements"
        title={
          isLandlord ? "Demandes de paiement" : "Payer un loyer"
        }
        description={
          isLandlord
            ? "Confirmez les paiements initiés par vos locataires et gérez vos comptes de réception."
            : "Initiez une demande de paiement que votre bailleur devra confirmer."
        }
        action={
          isLandlord ? (
            <button
              type="button"
              onClick={() => setMethodOpen(true)}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-emerald-700 px-4 text-sm font-bold text-white disabled:opacity-50"
            >
              <Plus size={16} aria-hidden />
              Ajouter un compte de réception
            </button>
          ) : undefined
        }
      />

      {(feedback || error) && (
        <Feedback
          tone={error ? "error" : "success"}
          message={error ?? feedback ?? ""}
        />
      )}

      {isLandlord && methods.length > 0 && (
        <section className="overflow-hidden rounded-xl border border-line">
          <header className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
            <div className="flex items-center gap-2 text-sm font-bold">
              <WalletCards size={16} aria-hidden />
              Comptes de réception
            </div>
            <button
              type="button"
              onClick={() => void load()}
              className="inline-flex min-h-9 items-center gap-2 rounded-lg px-3 text-sm font-semibold text-zinc-600 hover:bg-zinc-100"
            >
              <RefreshCw size={14} aria-hidden />
              Actualiser
            </button>
          </header>
          <ul className="divide-y divide-line">
            {methods.map((method) => (
              <li
                key={method.id}
                className="flex flex-wrap items-center gap-3 px-5 py-3.5"
              >
                <span className="inline-flex size-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
                  <Smartphone size={16} aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 text-sm font-bold">
                    {method.operator_label}
                    {method.is_default && (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-600">
                        <Star size={12} aria-hidden />
                        Par défaut
                      </span>
                    )}
                  </p>
                  <p className="truncate text-sm text-zinc-500">
                    {method.account_identifier}
                    {method.account_holder ? ` · ${method.account_holder}` : ""}
                  </p>
                </div>
                {!method.is_default && (
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() =>
                      run(
                        () => setDefaultPaymentMethod(method.id),
                        "Compte par défaut mis à jour.",
                      )
                    }
                    className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-sm font-semibold text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                  >
                    <Check size={14} aria-hidden />
                    Définir par défaut
                  </button>
                )}
                <button
                  type="button"
                  disabled={saving}
                  onClick={() =>
                    run(
                      () => deletePaymentMethod(method.id),
                      "Compte de réception supprimé.",
                    )
                  }
                  className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"
                  aria-label={`Supprimer ${method.operator_label}`}
                >
                  <Trash2 size={14} aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!isLandlord && (
        <section className="overflow-hidden rounded-xl border border-line">
          <header className="border-b border-line px-5 py-4 text-sm font-bold">
            Échéances payables
          </header>
          {charges.length === 0 ? (
            <p className="px-5 py-8 text-center text-sm text-zinc-500">
              Aucune échéance de loyer en attente.
            </p>
          ) : (
            <ul className="divide-y divide-line">
              {charges.map((charge) => (
                <li key={charge.id} className="px-5 py-3.5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-bold">
                        {charge.house_name} · {charge.period}
                      </p>
                      <p className="text-sm text-zinc-500">
                        Solde restant : {formatMoney(charge.balance_due)}
                      </p>
                    </div>
                    <span className="status-pill status-partial">
                      {charge.status_label}
                    </span>
                  </div>
                  <form
                    onSubmit={(event) => {
                      setChargeId(charge.id);
                      handleInitiate(event);
                    }}
                    className="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr_auto]"
                  >
                    <input
                      type="number"
                      min="0.01"
                      step="0.01"
                      max={charge.balance_due}
                      required
                      value={initiateAmount}
                      onChange={(event) => setInitiateAmount(event.target.value)}
                      placeholder="Montant (XOF)"
                      className="min-h-11 rounded-xl border border-line px-3.5 text-sm"
                    />
                    <select
                      value={initiateOperator}
                      onChange={(event) =>
                        setInitiateOperator(
                          event.target.value as PaymentRequestOperator,
                        )
                      }
                      className="min-h-11 rounded-xl border border-line px-3.5 text-sm"
                    >
                      {operatorOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <button
                      type="submit"
                      disabled={saving || !initiateAmount}
                      className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-emerald-700 px-4 text-sm font-bold text-white disabled:opacity-50"
                    >
                      {saving ? (
                        <LoaderCircle
                          size={16}
                          className="animate-spin"
                          aria-hidden
                        />
                      ) : (
                        <HandCoins size={16} aria-hidden />
                      )}
                      Demander le paiement
                    </button>
                  </form>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="overflow-hidden rounded-xl border border-line">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
          <div className="flex items-center gap-2 text-sm font-bold">
            {isLandlord ? "Demandes reçues" : "Mes demandes"}
            <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600">
              {requests.length}
            </span>
          </div>
          {isLandlord && (
            <select
              value={statusFilter}
              onChange={(event) =>
                setStatusFilter(event.target.value as PaymentRequestStatus | "")
              }
              className="min-h-9 rounded-lg border border-line px-3 text-sm"
            >
              <option value="">Tous les statuts</option>
              <option value="PENDING">En attente</option>
              <option value="CONFIRMED">Confirmées</option>
              <option value="NOT_RECEIVED">Non reçues</option>
              <option value="CANCELLED">Annulées</option>
            </select>
          )}
        </header>
        {loading ? (
          <p className="flex items-center justify-center gap-2 px-5 py-10 text-sm text-zinc-500">
            <LoaderCircle size={16} className="animate-spin" aria-hidden />
            Chargement…
          </p>
        ) : requests.length === 0 ? (
          <p className="px-5 py-8 text-center text-sm text-zinc-500">
            Aucune demande de paiement.
          </p>
        ) : (
          <ul className="divide-y divide-line">
            {requests.map((request) => (
              <li
                key={request.id}
                className="flex flex-wrap items-center gap-3 px-5 py-3.5"
              >
                <span className="inline-flex size-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
                  <HandCoins size={16} aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 text-sm font-bold">
                    <span className="truncate">{request.reference}</span>
                    <span className={`status-pill ${statusStyle[request.status]}`}>
                      {request.status_label}
                    </span>
                  </p>
                  <p className="truncate text-sm text-zinc-500">
                    {isLandlord ? request.tenant_name : request.house_name} ·{" "}
                    {request.period} · {request.operator_label}
                    {request.payee_phone ? ` · ${request.payee_phone}` : ""}
                  </p>
                  <p className="truncate text-xs text-zinc-400">
                    Créée le {formatDateTime(request.created_at)}
                    {request.processing_note
                      ? ` · ${request.processing_note}`
                      : ""}
                    {request.operator === "PI_SPI" && request.external_transaction_id
                      ? ` · PI-SPI ${request.external_transaction_id.slice(0, 8)}…`
                      : ""}
                    {request.failure_reason ? ` · ${request.failure_reason}` : ""}
                  </p>
                  {request.operator === "PI_SPI" && request.provider_status && (
                    <p className="truncate text-xs text-amber-600">
                      Prestataire: {request.provider_status}
                      {request.expires_at ? ` · expire ${formatDateTime(request.expires_at)}` : ""}
                    </p>
                  )}
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold">
                    {formatMoney(request.amount)}
                  </p>
                  <p className="text-xs text-zinc-400">
                    {request.status === "CONFIRMED" && request.amount_received
                      ? `Reçu : ${formatMoney(request.amount_received)}`
                      : "XOF"}
                  </p>
                </div>
                {isLandlord && request.status === "PENDING" ? (
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setConfirmTarget(request)}
                      className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-emerald-700 px-3 text-sm font-bold text-white disabled:opacity-50"
                    >
                      <Check size={14} aria-hidden />
                      Confirmer
                    </button>
                    <button
                      type="button"
                      onClick={() => setRefuseTarget(request)}
                      className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-sm font-bold text-red-700 hover:bg-red-50"
                    >
                      <ShieldAlert size={14} aria-hidden />
                      Refuser
                    </button>
                  </div>
                ) : null}
                {!isLandlord && request.operator === "PI_SPI" && request.status === "PENDING" ? (
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() =>
                      run(
                        () => initiatePiSpiPayment(request.id),
                        "Paiement PI-SPI initié. En attente de confirmation.",
                      )
                    }
                    className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-emerald-700 px-3 text-sm font-bold text-white disabled:opacity-50"
                  >
                    <Landmark size={14} aria-hidden />
                    Payer via PI-SPI
                  </button>
                ) : null}
                {!isLandlord && request.operator === "PI_SPI" && request.status === "PROCESSING" ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="inline-flex items-center gap-1.5 rounded-lg bg-amber-50 px-3 py-1.5 text-sm font-semibold text-amber-700">
                      <LoaderCircle size={14} className="animate-spin" aria-hidden />
                      En cours PI-SPI
                    </span>
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() =>
                        run(
                          () =>
                            getPiSpiStatus(request.id).then((updated) => {
                              setRequests((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
                            }),
                          "Statut PI-SPI actualisé.",
                        )
                      }
                      className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-sm font-semibold text-zinc-600 hover:bg-zinc-100 disabled:opacity-50"
                    >
                      <RefreshCw size={14} aria-hidden />
                      Actualiser
                    </button>
                    <button
                      type="button"
                      onClick={() => setCancelTarget(request)}
                      className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-sm font-semibold text-zinc-600 hover:bg-zinc-100"
                    >
                      <X size={14} aria-hidden />
                      Annuler
                    </button>
                  </div>
                ) : null}
                {!isLandlord && request.status === "PENDING" && request.operator !== "PI_SPI" ? (
                  <button
                    type="button"
                    onClick={() => setCancelTarget(request)}
                    className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-sm font-semibold text-zinc-600 hover:bg-zinc-100"
                  >
                    <X size={14} aria-hidden />
                    Annuler
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      {isLandlord && confirmTarget && (
        <Modal
          open={Boolean(confirmTarget)}
          title={`Confirmer ${confirmTarget.reference}`}
          onClose={closeConfirmModal}
        >
          <form onSubmit={(event) => void handleConfirm(event)} className="grid gap-4">
            <p className="text-sm text-zinc-600">
              {confirmTarget.tenant_name} a demandé{" "}
              {formatMoney(confirmTarget.amount)} par{" "}
              {confirmTarget.operator_label}. Indiquez le montant reçu si
              différent.
            </p>
            <label className="grid gap-1.5 text-sm">
              <span className="font-semibold">Montant reçu (XOF)</span>
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={confirmAmount}
                onChange={(event) => setConfirmAmount(event.target.value)}
                placeholder={confirmTarget.amount}
                className="min-h-11 rounded-xl border border-line px-3.5 text-sm"
              />
            </label>
            <label className="grid gap-1.5 text-sm">
              <span className="font-semibold">Note</span>
              <textarea
                value={confirmNote}
                onChange={(event) => setConfirmNote(event.target.value)}
                rows={2}
                className="rounded-xl border border-line px-3.5 py-2.5 text-sm"
              />
            </label>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-emerald-700 px-4 text-sm font-bold text-white disabled:opacity-50"
            >
              {saving && <LoaderCircle size={16} className="animate-spin" aria-hidden />}
              Confirmer la réception
            </button>
          </form>
        </Modal>
      )}

      {isLandlord && refuseTarget && (
        <Modal
          open={Boolean(refuseTarget)}
          title={`Refuser ${refuseTarget.reference}`}
          onClose={closeRefuseModal}
        >
          <form onSubmit={(event) => void handleRefuse(event)} className="grid gap-4">
            <p className="text-sm text-zinc-600">
              Signalez au locataire que les fonds n&apos;ont pas été reçus.
            </p>
            <label className="grid gap-1.5 text-sm">
              <span className="font-semibold">Motif *</span>
              <textarea
                required
                minLength={3}
                value={refuseReason}
                onChange={(event) => setRefuseReason(event.target.value)}
                rows={3}
                className="rounded-xl border border-line px-3.5 py-2.5 text-sm"
              />
            </label>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-red-700 px-4 text-sm font-bold text-white disabled:opacity-50"
            >
              {saving && <LoaderCircle size={16} className="animate-spin" aria-hidden />}
              Refuser la demande
            </button>
          </form>
        </Modal>
      )}

      {!isLandlord && cancelTarget && (
        <Modal
          open={Boolean(cancelTarget)}
          title={`Annuler ${cancelTarget.reference}`}
          onClose={closeCancelModal}
        >
          <form onSubmit={(event) => void handleCancel(event)} className="grid gap-4">
            <p className="text-sm text-zinc-600">
              La demande sera annulée tant qu&apos;elle est en attente.
            </p>
            <label className="grid gap-1.5 text-sm">
              <span className="font-semibold">Motif (facultatif)</span>
              <textarea
                value={cancelReason}
                onChange={(event) => setCancelReason(event.target.value)}
                rows={2}
                className="rounded-xl border border-line px-3.5 py-2.5 text-sm"
              />
            </label>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-zinc-800 px-4 text-sm font-bold text-white disabled:opacity-50"
            >
              {saving && <LoaderCircle size={16} className="animate-spin" aria-hidden />}
              Annuler la demande
            </button>
          </form>
        </Modal>
      )}

      {isLandlord && methodOpen && (
        <Modal
          open={methodOpen}
          title="Ajouter un compte de réception"
          onClose={() => setMethodOpen(false)}
        >
          <form
            onSubmit={(event) => void handleCreateMethod(event)}
            className="grid gap-4"
          >
            <label className="grid gap-1.5 text-sm">
              <span className="font-semibold">Opérateur *</span>
              <select
                value={methodOperator}
                onChange={(event) =>
                  setMethodOperator(event.target.value as PaymentRequestOperator)
                }
                className="min-h-11 rounded-xl border border-line px-3.5 text-sm"
              >
                {operatorOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="grid gap-1.5 text-sm">
              <span className="font-semibold">Identifiant du compte *</span>
              <input
                required
                value={methodIdentifier}
                onChange={(event) => setMethodIdentifier(event.target.value)}
                placeholder="+225 07 00 00 00 00"
                className="min-h-11 rounded-xl border border-line px-3.5 text-sm"
              />
            </label>
            <label className="grid gap-1.5 text-sm">
              <span className="font-semibold">Titulaire</span>
              <input
                value={methodHolder}
                onChange={(event) => setMethodHolder(event.target.value)}
                className="min-h-11 rounded-xl border border-line px-3.5 text-sm"
              />
            </label>
            <label className="flex items-center gap-2 text-sm font-semibold">
              <input
                type="checkbox"
                checked={methodDefault}
                onChange={(event) => setMethodDefault(event.target.checked)}
                className="size-4"
              />
              Définir comme compte par défaut
            </label>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-emerald-700 px-4 text-sm font-bold text-white disabled:opacity-50"
            >
              {saving && <LoaderCircle size={16} className="animate-spin" aria-hidden />}
              Enregistrer
            </button>
          </form>
        </Modal>
      )}
    </section>
  );
}
