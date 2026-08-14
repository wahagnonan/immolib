"use client";

import {
  BellRing,
  Copy,
  Download,
  Eye,
  FileCheck2,
  Files,
  Mail,
  MessageCircleMore,
  RefreshCw,
  Send,
  Share2,
  ShieldCheck,
  Smartphone,
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { DocumentPaper } from "@/components/documents/document-paper";
import { Feedback } from "@/components/ui/feedback";
import { Modal } from "@/components/ui/modal";
import { ModuleHeader } from "@/components/ui/module-header";
import {
  downloadDocumentPdf,
  listDocumentsPage,
  listNotificationDeliveries,
  prepareManualDocumentShare,
  shareDocument,
} from "@/lib/api-client";
import { rentalDocumentPdfFilename, saveBlob } from "@/lib/download";
import { formatDate, formatDateTime, formatMoney, monthLabel } from "@/lib/format";
import type {
  DirectDeliveryChannel,
  ManualShareChannel,
  ManualShareResult,
  NotificationDelivery,
  NotificationDeliveryKind,
  NotificationDeliveryStatus,
  RentalDocument,
  ShareDocumentResult,
} from "@/types/domain";

const channels: Array<{ value: DirectDeliveryChannel; label: string; icon: typeof Smartphone }> = [
  { value: "SMS", label: "SMS (payant)", icon: Smartphone },
  { value: "EMAIL", label: "Email", icon: Mail },
  { value: "WHATSAPP", label: "WhatsApp", icon: MessageCircleMore },
];

const deliveryStatusStyle: Record<NotificationDeliveryStatus, string> = {
  QUEUED: "status-partial",
  PROCESSING: "status-vacant",
  SENT: "status-paid",
  FAILED: "status-late",
};

const deliveryStatusLabel: Record<NotificationDeliveryStatus, string> = {
  QUEUED: "En attente",
  PROCESSING: "En cours",
  SENT: "Envoyé",
  FAILED: "Échec",
};

const deliveryKindLabel: Record<NotificationDeliveryKind, string> = {
  DOCUMENT_LINK: "Liens de document",
  OTP: "Codes OTP",
  RENT_REMINDER: "Rappels de loyer",
  TENANT_INVITATION: "Invitations locataires",
};

function deliveryActivity(delivery: NotificationDelivery) {
  if (delivery.sent_at) return `Envoyé le ${formatDateTime(delivery.sent_at)}`;
  if (delivery.next_attempt_at) {
    return `Nouvel essai le ${formatDateTime(delivery.next_attempt_at)}`;
  }
  if (delivery.kind === "RENT_REMINDER" && delivery.scheduled_for) {
    return `Planifié le ${formatDate(delivery.scheduled_for)}`;
  }
  if (delivery.last_attempt_at) {
    return `Dernière tentative le ${formatDateTime(delivery.last_attempt_at)}`;
  }
  return `Créé le ${formatDateTime(delivery.created_at)}`;
}

export function DocumentWorkspace() {
  const [documents, setDocuments] = useState<RentalDocument[]>([]);
  const [documentPage, setDocumentPage] = useState(1);
  const [documentCount, setDocumentCount] = useState(0);
  const [deliveries, setDeliveries] = useState<NotificationDelivery[]>([]);
  const [filter, setFilter] = useState<"ALL" | RentalDocument["document_type"]>("ALL");
  const [deliveryFilter, setDeliveryFilter] = useState<
    "ALL" | NotificationDeliveryStatus
  >("ALL");
  const [deliveryKindFilter, setDeliveryKindFilter] = useState<
    "ALL" | NotificationDeliveryKind
  >("ALL");
  const [preview, setPreview] = useState<RentalDocument | null>(null);
  const [sharing, setSharing] = useState<RentalDocument | null>(null);
  const [selectedChannels, setSelectedChannels] = useState<DirectDeliveryChannel[]>(["EMAIL"]);
  const [shareResult, setShareResult] = useState<ShareDocumentResult | null>(null);
  const [manualShareResult, setManualShareResult] = useState<ManualShareResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [downloadingDocumentId, setDownloadingDocumentId] = useState<string | null>(null);
  const [deliveryLoading, setDeliveryLoading] = useState(true);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      listDocumentsPage({
        page: documentPage,
        documentType: filter === "ALL" ? undefined : filter,
      }),
      listNotificationDeliveries(),
    ])
      .then(([loadedDocuments, loadedDeliveries]) => {
        setDocuments(loadedDocuments.results);
        setDocumentCount(loadedDocuments.count);
        setDeliveries(loadedDeliveries);
      })
      .catch((caughtError) =>
        setError(caughtError instanceof Error ? caughtError.message : "Chargement impossible."),
      )
      .finally(() => setDeliveryLoading(false));
  }, [documentPage, filter]);

  const visibleDocuments = documents;
  const kindFilteredDeliveries = deliveries.filter(
    (delivery) =>
      deliveryKindFilter === "ALL" || delivery.kind === deliveryKindFilter,
  );
  const visibleDeliveries = kindFilteredDeliveries.filter(
    (delivery) => deliveryFilter === "ALL" || delivery.status === deliveryFilter,
  );

  const deliveryCounts = kindFilteredDeliveries.reduce<Record<NotificationDeliveryStatus, number>>(
    (counts, delivery) => {
      counts[delivery.status] += 1;
      return counts;
    },
    { QUEUED: 0, PROCESSING: 0, SENT: 0, FAILED: 0 },
  );

  async function refreshDeliveries() {
    setDeliveryLoading(true);
    setError(null);
    try {
      setDeliveries(await listNotificationDeliveries());
      setFeedback("Suivi des envois actualisé.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Actualisation impossible.");
    } finally {
      setDeliveryLoading(false);
    }
  }

  function toggleChannel(channel: DirectDeliveryChannel) {
    setSelectedChannels((current) =>
      current.includes(channel)
        ? current.filter((item) => item !== channel)
        : [...current, channel],
    );
  }

  function openShare(document: RentalDocument) {
    setSharing(document);
    setShareResult(null);
    setManualShareResult(null);
    setSelectedChannels(["EMAIL"]);
    setError(null);
  }

  async function handleManualShare(channel: ManualShareChannel) {
    if (!sharing) return;
    setSaving(true);
    setError(null);
    try {
      const result = await prepareManualDocumentShare(sharing.id, channel);
      setManualShareResult(result);

      if (channel === "COPY") {
        await navigator.clipboard.writeText(result.message);
        setFeedback("Message et lien copiés.");
      } else if (channel === "NATIVE") {
        if (navigator.share) {
          await navigator.share({
            title: result.subject,
            text: result.message,
          });
          setFeedback("Menu de partage ouvert.");
        } else {
          await navigator.clipboard.writeText(result.message);
          setFeedback("Partage natif indisponible : message copié.");
        }
      } else {
        window.location.href = result.action_url;
      }
    } catch (caughtError) {
      if (caughtError instanceof DOMException && caughtError.name === "AbortError") {
        return;
      }
      setError(
        caughtError instanceof Error ? caughtError.message : "Partage impossible.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handlePdfDownload(document: RentalDocument) {
    setDownloadingDocumentId(document.id);
    setError(null);
    try {
      const pdf = await downloadDocumentPdf(document.id);
      saveBlob(pdf, rentalDocumentPdfFilename(document));
      setFeedback("PDF téléchargé.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Téléchargement impossible.");
    } finally {
      setDownloadingDocumentId(null);
    }
  }

  async function handleShare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!sharing) return;
    if (!selectedChannels.length) {
      setError("Sélectionnez au moins un canal d’envoi.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const result = await shareDocument(sharing.id, selectedChannels);
      listNotificationDeliveries()
        .then(setDeliveries)
        .catch(() => setError("Lien créé, mais le suivi n’a pas pu être actualisé."));
      setShareResult(result);
      setFeedback("Lien sécurisé créé et messages placés dans la file d’envoi.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Partage impossible.");
    } finally {
      setSaving(false);
    }
  }

  async function copyLink() {
    if (!shareResult) return;
    await navigator.clipboard.writeText(shareResult.secure_url);
    setFeedback("Lien copié.");
  }

  return (
    <div className="space-y-6">
      <ModuleHeader
        description="Reçus de paiement, quittances de loyer et reçus de caution sont générés automatiquement."
        eyebrow="Justificatifs"
        title="Documents"
      />
      <Feedback message={feedback} />
      <Feedback message={error} tone="error" />

      <section className="flex flex-wrap gap-2" aria-label="Filtrer les documents">
        {(
          [
            "ALL",
            "PAYMENT_RECEIPT",
            "RENT_RECEIPT",
            "DEPOSIT_RECEIPT",
            "DEPOSIT_SETTLEMENT",
          ] as const
        ).map((item) => (
          <button
            className={`min-h-10 rounded-xl px-4 text-sm font-bold ${filter === item ? "bg-brand text-white" : "border border-line bg-white text-muted"}`}
            key={item}
            onClick={() => {
              setFilter(item);
              setDocumentPage(1);
            }}
            type="button"
          >
            {item === "ALL"
              ? "Tous"
              : item === "PAYMENT_RECEIPT"
                ? "Reçus"
                : item === "RENT_RECEIPT"
                  ? "Quittances"
                  : item === "DEPOSIT_RECEIPT"
                    ? "Reçus de caution"
                    : "Clôtures de caution"}
          </button>
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
        {visibleDocuments.map((document) => (
          <article className="panel p-5" key={document.id}>
            <div className="flex items-start justify-between gap-3">
              <span className={`grid size-10 place-items-center rounded-xl ${document.document_type === "RENT_RECEIPT" ? "bg-brand-soft text-brand" : "bg-sky-soft text-sky-dark"}`}>
                {document.document_type === "RENT_RECEIPT" ? (
                  <FileCheck2 aria-hidden="true" size={20} />
                ) : document.document_type === "DEPOSIT_RECEIPT" ||
                  document.document_type === "DEPOSIT_SETTLEMENT" ? (
                  <ShieldCheck aria-hidden="true" size={20} />
                ) : (
                  <Files aria-hidden="true" size={20} />
                )}
              </span>
              <span className={`status-pill ${document.status === "ACTIVE" ? "status-paid" : "bg-red-50 text-red-700"}`}>{document.status_label}</span>
            </div>
            <p className="mt-5 text-xs font-bold uppercase tracking-[0.11em] text-muted">{document.reference}</p>
            <h2 className="mt-2 text-lg font-bold text-ink">{document.document_type_label}</h2>
            <p className="mt-1 text-sm text-muted">{document.tenant_name} · {document.house_name}</p>
            <div className="mt-5 grid grid-cols-2 gap-4 border-y border-line py-4 text-sm">
              <div><p className="text-muted">Période</p><p className="mt-1 font-semibold capitalize text-ink">{document.document_type === "DEPOSIT_RECEIPT" ? "Caution du bail" : document.document_type === "DEPOSIT_SETTLEMENT" ? "Clôture de caution" : monthLabel(document.period)}</p></div>
              <div><p className="text-muted">Montant</p><p className="mt-1 font-semibold text-ink">{formatMoney(document.amount)}</p></div>
            </div>
            <p className="mt-4 text-xs text-muted">Émis le {formatDate(document.issued_at)}</p>
            <div className="mt-5 grid grid-cols-3 gap-2">
              <button className="secondary-button flex-1" onClick={() => setPreview(document)} type="button"><Eye aria-hidden="true" size={17} />Voir</button>
              <button className="secondary-button flex-1" disabled={downloadingDocumentId === document.id} onClick={() => handlePdfDownload(document)} type="button"><Download aria-hidden="true" size={17} />PDF</button>
              <button className="primary-button flex-1" disabled={document.status !== "ACTIVE"} onClick={() => openShare(document)} type="button"><Send aria-hidden="true" size={17} />Envoyer</button>
            </div>
          </article>
        ))}
        {!visibleDocuments.length ? (
          <div className="panel px-5 py-14 text-center lg:col-span-2 2xl:col-span-3">
            <p className="font-bold text-ink">
              {documents.length ? "Aucun document avec ce filtre" : "Aucun document généré"}
            </p>
            <p className="mt-1 text-sm text-muted">
              Les reçus et quittances apparaîtront après l’enregistrement des paiements.
            </p>
          </div>
        ) : null}
      </section>
      {documentCount > 25 ? (
        <nav
          aria-label="Pagination des documents"
          className="flex items-center justify-between gap-3"
        >
          <button
            className="secondary-button"
            disabled={documentPage === 1}
            onClick={() => setDocumentPage((current) => current - 1)}
            type="button"
          >
            Précédent
          </button>
          <span className="text-sm font-semibold text-muted">
            Page {documentPage} sur {Math.ceil(documentCount / 25)}
          </span>
          <button
            className="secondary-button"
            disabled={documentPage >= Math.ceil(documentCount / 25)}
            onClick={() => setDocumentPage((current) => current + 1)}
            type="button"
          >
            Suivant
          </button>
        </nav>
      ) : null}

      <section className="panel overflow-hidden">
        <div className="panel-heading flex-col gap-4 sm:flex-row sm:items-center">
          <div>
            <p className="section-kicker">Notifications</p>
            <h2 className="section-title">Suivi des envois</h2>
            <p className="mt-1 text-sm text-muted">
              Vérifiez les rappels de loyer, les liens et les codes envoyés au locataire.
            </p>
          </div>
          <button
            className="secondary-button shrink-0"
            disabled={deliveryLoading}
            onClick={refreshDeliveries}
            type="button"
          >
            <RefreshCw
              aria-hidden="true"
              className={deliveryLoading ? "animate-spin" : ""}
              size={17}
            />
            Actualiser
          </button>
        </div>

        <div className="flex flex-wrap gap-2 border-t border-line px-5 py-3" aria-label="Filtrer les types de notification">
          <button
            className={`min-h-9 rounded-xl px-3 text-xs font-bold ${deliveryKindFilter === "ALL" ? "bg-brand text-white" : "border border-line bg-white text-muted"}`}
            onClick={() => setDeliveryKindFilter("ALL")}
            type="button"
          >
            Tous les messages
          </button>
          {([
            "RENT_REMINDER",
            "DOCUMENT_LINK",
            "TENANT_INVITATION",
            "OTP",
          ] as const).map((kind) => (
            <button
              className={`min-h-9 rounded-xl px-3 text-xs font-bold ${deliveryKindFilter === kind ? "bg-brand text-white" : "border border-line bg-white text-muted"}`}
              key={kind}
              onClick={() => setDeliveryKindFilter(kind)}
              type="button"
            >
              {deliveryKindLabel[kind]}
            </button>
          ))}
        </div>

        <div className="grid gap-3 border-t border-line bg-canvas/55 p-5 sm:grid-cols-2 xl:grid-cols-4">
          {(["QUEUED", "PROCESSING", "SENT", "FAILED"] as const).map((item) => (
            <button
              className={`rounded-xl border p-4 text-left transition-colors ${deliveryFilter === item ? "border-brand bg-white ring-2 ring-brand/10" : "border-line bg-white hover:border-brand/40"}`}
              key={item}
              onClick={() => setDeliveryFilter(deliveryFilter === item ? "ALL" : item)}
              type="button"
            >
              <span className={`status-pill ${deliveryStatusStyle[item]}`}>
                {deliveryStatusLabel[item]}
              </span>
              <span className="mt-3 block text-2xl font-bold text-ink">
                {deliveryCounts[item]}
              </span>
              <span className="mt-0.5 block text-xs text-muted">
                {deliveryCounts[item] > 1 ? "messages" : "message"}
              </span>
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3">
          <p className="text-sm font-semibold text-ink">
            {deliveryFilter === "ALL"
              ? "Tous les envois"
              : deliveryStatusLabel[deliveryFilter]}
          </p>
          {deliveryFilter !== "ALL" ? (
            <button
              className="text-link"
              onClick={() => setDeliveryFilter("ALL")}
              type="button"
            >
              Effacer le filtre
            </button>
          ) : null}
        </div>

        {visibleDeliveries.length ? (
          <div className="overflow-x-auto border-t border-line">
            <table className="data-table min-w-[980px]">
              <thead>
                <tr>
                  <th>Message</th>
                  <th>Canal et destinataire</th>
                  <th>Statut</th>
                  <th>Tentatives</th>
                  <th>Dernière activité</th>
                </tr>
              </thead>
              <tbody>
                {visibleDeliveries.map((delivery) => (
                  <tr key={delivery.id}>
                    <td>
                      <p className="font-semibold text-ink">{delivery.context_label}</p>
                      <p className="mt-1 text-xs text-muted">{delivery.kind_label}</p>
                      <p className="mt-1 text-xs text-muted">{delivery.tenant_name} · {delivery.house_name}</p>
                    </td>
                    <td>
                      <p className="font-semibold text-ink">{delivery.channel_label}</p>
                      <p className="mt-1 text-xs text-muted">{delivery.masked_destination}</p>
                    </td>
                    <td>
                      <span className={`status-pill ${deliveryStatusStyle[delivery.status]}`}>
                        {deliveryStatusLabel[delivery.status]}
                      </span>
                      {delivery.failure_reason ? (
                        <p className="mt-2 max-w-xs text-xs text-red-700">
                          {delivery.failure_reason}
                        </p>
                      ) : null}
                    </td>
                    <td>
                      {delivery.attempt_count} {delivery.attempt_count > 1 ? "tentatives" : "tentative"}
                    </td>
                    <td>{deliveryActivity(delivery)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="border-t border-line px-5 py-14 text-center">
            <BellRing aria-hidden="true" className="mx-auto text-muted" size={28} />
            <p className="mt-3 font-bold text-ink">
              {kindFilteredDeliveries.length ? "Aucun envoi avec ce statut" : "Aucun envoi pour ce type"}
            </p>
            <p className="mt-1 text-sm text-muted">
              {kindFilteredDeliveries.length
                ? "Choisissez un autre statut ou effacez le filtre."
                : "Les prochains messages créés apparaîtront ici."}
            </p>
          </div>
        )}
      </section>

      <Modal onClose={() => setPreview(null)} open={Boolean(preview)} size="xl" title={preview?.document_type_label ?? "Document"}>
        <div className="bg-canvas p-4 sm:p-7">{preview ? <DocumentPaper document={preview} /> : null}</div>
      </Modal>

      <Modal
        description="Partagez gratuitement depuis votre téléphone, ou placez un email dans la file Amazon SES."
        kicker="Partage multicanal"
        onClose={() => setSharing(null)}
        open={Boolean(sharing)}
        title="Envoyer au locataire"
      >
        <form className="p-5 sm:p-6" onSubmit={handleShare}>
          {!shareResult ? (
            <>
              <section className="rounded-2xl border border-brand/20 bg-brand-soft p-4">
                <p className="text-sm font-bold text-brand-dark">Partager depuis votre appareil</p>
                <p className="mt-1 text-xs leading-5 text-brand-dark/80">
                  Aucun fournisseur SMS n’est facturé. WhatsApp fonctionne même si le locataire n’a pas enregistré votre numéro.
                </p>
                <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <button className="secondary-button" disabled={saving} onClick={() => handleManualShare("WHATSAPP")} type="button"><MessageCircleMore aria-hidden="true" size={17} />WhatsApp</button>
                  <button className="secondary-button" disabled={saving} onClick={() => handleManualShare("EMAIL")} type="button"><Mail aria-hidden="true" size={17} />Email</button>
                  <button className="secondary-button" disabled={saving} onClick={() => handleManualShare("NATIVE")} type="button"><Share2 aria-hidden="true" size={17} />Partager</button>
                  <button className="secondary-button" disabled={saving} onClick={() => handleManualShare("COPY")} type="button"><Copy aria-hidden="true" size={17} />Copier</button>
                </div>
                {manualShareResult ? (
                  <p className="mt-3 text-xs text-brand-dark">
                    Lien prêt jusqu’au {formatDate(manualShareResult.expires_at)}.
                  </p>
                ) : null}
              </section>

              <div className="my-5 flex items-center gap-3 text-xs font-bold uppercase tracking-[0.1em] text-muted"><span className="h-px flex-1 bg-line" />Envoi automatisé ImmoLib<span className="h-px flex-1 bg-line" /></div>
              <fieldset><legend className="form-label">Canaux à placer en file *</legend><div className="grid gap-3 sm:grid-cols-3">
                {channels.map((channel) => { const Icon = channel.icon; const active = selectedChannels.includes(channel.value); return <label className={`flex min-h-14 items-center gap-3 rounded-xl border px-4 text-sm font-bold ${active ? "border-brand bg-brand-soft text-brand-dark" : "border-line text-ink"}`} key={channel.value}><input checked={active} onChange={() => toggleChannel(channel.value)} type="checkbox" /><Icon aria-hidden="true" size={18} />{channel.label}</label>; })}
              </div></fieldset>
              <p className="mt-3 text-xs leading-5 text-muted">Email utilise Amazon SES. WhatsApp automatique exige Meta Cloud API et l’opt-in du destinataire. SMS reste un dernier recours payant.</p>
              <Feedback message={error} tone="error" />
              <div className="mt-7 flex flex-col-reverse gap-3 border-t border-line pt-5 sm:flex-row sm:justify-end"><button className="secondary-button" onClick={() => setSharing(null)} type="button">Annuler</button><button className="primary-button" disabled={saving} type="submit"><Send aria-hidden="true" size={18} />{saving ? "Création…" : "Créer et envoyer le lien"}</button></div>
            </>
          ) : (
            <div>
              <div className="rounded-xl border border-brand/25 bg-brand-soft p-4 text-sm text-brand-dark"><p className="font-bold">Lien sécurisé prêt</p><p className="mt-1">Il expire le {formatDate(shareResult.expires_at)}.</p></div>
              <label className="mt-5 block"><span className="form-label">Lien du document</span><div className="flex gap-2"><input className="form-input" readOnly value={shareResult.secure_url} /><button aria-label="Copier le lien" className="secondary-button shrink-0" onClick={copyLink} title="Copier" type="button"><Copy aria-hidden="true" size={18} /></button></div></label>
              <div className="mt-5 space-y-2">{shareResult.deliveries.map((delivery) => <div className="flex items-center justify-between rounded-xl border border-line px-4 py-3 text-sm" key={delivery.channel}><span className="font-semibold text-ink">{channels.find((item) => item.value === delivery.channel)?.label ?? delivery.channel}</span><span className={`status-pill ${deliveryStatusStyle[delivery.status]}`}>{deliveryStatusLabel[delivery.status]}</span></div>)}</div>
              <a className="primary-button mt-6 w-full" href={shareResult.secure_url} rel="noreferrer" target="_blank"><Eye aria-hidden="true" size={18} />Tester le lien public</a>
            </div>
          )}
        </form>
      </Modal>
    </div>
  );
}
