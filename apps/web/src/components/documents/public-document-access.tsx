"use client";

import {
  ArrowLeft,
  CheckCircle2,
  Download,
  Mail,
  MessageCircleMore,
  ShieldCheck,
  Smartphone,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { Brand } from "@/components/brand";
import { DocumentPaper } from "@/components/documents/document-paper";
import { Feedback } from "@/components/ui/feedback";
import {
  downloadPublicDocumentPdf,
  requestDocumentOtp,
  respondToPayment,
  verifyDocumentOtp,
  viewPublicDocument,
} from "@/lib/api-client";
import { rentalDocumentPdfFilename, saveBlob } from "@/lib/download";
import type { DeliveryChannel, RentalDocument } from "@/types/domain";

const channelOptions: Array<{ value: DeliveryChannel; label: string; icon: typeof Smartphone }> = [
  { value: "SMS", label: "SMS", icon: Smartphone },
  { value: "EMAIL", label: "Email", icon: Mail },
  { value: "WHATSAPP", label: "WhatsApp", icon: MessageCircleMore },
];

type Step = "CHANNEL" | "OTP" | "DOCUMENT";

export function PublicDocumentAccess({ accessToken }: { accessToken: string }) {
  const [step, setStep] = useState<Step>("CHANNEL");
  const [channel, setChannel] = useState<DeliveryChannel>("SMS");
  const [challengeId, setChallengeId] = useState("");
  const [maskedDestination, setMaskedDestination] = useState("");
  const [code, setCode] = useState("");
  const [grantToken, setGrantToken] = useState("");
  const [document, setDocument] = useState<RentalDocument | null>(null);
  const [disputing, setDisputing] = useState(false);
  const [reason, setReason] = useState("");
  const [paymentStatus, setPaymentStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function requestOtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await requestDocumentOtp(accessToken, channel);
      setChallengeId(result.challenge_id);
      setMaskedDestination(result.masked_destination);
      setStep("OTP");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Lien invalide ou expiré.");
    } finally {
      setLoading(false);
    }
  }

  async function verifyOtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await verifyDocumentOtp(challengeId, code);
      setGrantToken(result.grant_token);
      setDocument(await viewPublicDocument(result.grant_token));
      setStep("DOCUMENT");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Code invalide ou expiré.");
    } finally {
      setLoading(false);
    }
  }

  async function sendResponse(action: "CONFIRM" | "DISPUTE") {
    if (action === "DISPUTE" && !reason.trim()) {
      setError("Expliquez la raison de la contestation.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await respondToPayment(grantToken, action, reason);
      setPaymentStatus(result.status_label);
      setDisputing(false);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Réponse impossible.");
    } finally {
      setLoading(false);
    }
  }

  async function downloadPdf() {
    if (!document) return;
    setPdfLoading(true);
    setError(null);
    try {
      const pdf = await downloadPublicDocumentPdf(grantToken);
      saveBlob(pdf, rentalDocumentPdfFilename(document));
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Téléchargement impossible.");
    } finally {
      setPdfLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-canvas">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex h-18 max-w-5xl items-center justify-between px-4 sm:px-7">
          <Brand />
          <span className="flex items-center gap-2 text-xs font-bold text-brand">
            <ShieldCheck aria-hidden="true" size={18} /> Accès sécurisé
          </span>
        </div>
      </header>

      <main
        className="mx-auto max-w-5xl px-4 py-8 sm:px-7 sm:py-12"
        id="contenu-principal"
      >
        {step !== "DOCUMENT" ? (
          <section className="mx-auto max-w-xl">
            <div className="text-center">
              <p className="eyebrow">Document ImmoLib</p>
              <h1 className="page-title">Consulter votre justificatif</h1>
              <p className="mt-3 leading-7 text-muted">Pour protéger vos informations, vérifiez votre identité avec un code à six chiffres.</p>
            </div>

            <div className="panel mt-8 p-5 sm:p-7">
              {step === "CHANNEL" ? (
                <form onSubmit={requestOtp}>
                  <h2 className="text-lg font-bold text-ink">1. Choisissez où recevoir le code</h2>
                  <div className="mt-5 grid gap-3 sm:grid-cols-3">
                    {channelOptions.map((option) => { const Icon = option.icon; return <label className={`flex min-h-16 items-center justify-center gap-2 rounded-xl border text-sm font-bold ${channel === option.value ? "border-brand bg-brand-soft text-brand-dark" : "border-line text-ink"}`} key={option.value}><input checked={channel === option.value} className="sr-only" name="channel" onChange={() => setChannel(option.value)} type="radio" /><Icon aria-hidden="true" size={18} />{option.label}</label>; })}
                  </div>
                  <Feedback message={error} tone="error" />
                  <button className="primary-button mt-6 w-full" disabled={loading} type="submit">{loading ? "Envoi…" : "Recevoir mon code"}</button>
                </form>
              ) : (
                <form onSubmit={verifyOtp}>
                  <button className="mb-5 inline-flex items-center gap-2 text-sm font-bold text-brand" onClick={() => setStep("CHANNEL")} type="button"><ArrowLeft aria-hidden="true" size={17} />Changer de canal</button>
                  <h2 className="text-lg font-bold text-ink">2. Saisissez le code reçu</h2>
                  <p className="mt-2 text-sm text-muted">Code envoyé à {maskedDestination}. Il reste valable 10 minutes.</p>
                  <label className="mt-5 block"><span className="form-label">Code à 6 chiffres</span><input autoComplete="one-time-code" autoFocus className="form-input text-center font-mono text-xl tracking-[0.35em]" inputMode="numeric" maxLength={6} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} pattern="\d{6}" placeholder="000000" required value={code} /></label>
                  <Feedback message={error} tone="error" />
                  <button className="primary-button mt-6 w-full" disabled={loading || code.length !== 6} type="submit">{loading ? "Vérification…" : "Voir mon document"}</button>
                </form>
              )}
            </div>
          </section>
        ) : document ? (
          <div>
            <div className="mb-6 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
              <div><p className="eyebrow">Accès vérifié</p><h1 className="text-2xl font-bold text-ink">Votre document</h1></div>
              <div className="flex flex-wrap gap-2">
                <button className="primary-button" disabled={pdfLoading} onClick={downloadPdf} type="button"><Download aria-hidden="true" size={17} />{pdfLoading ? "Préparation…" : "Télécharger le PDF"}</button>
                <Link className="secondary-button w-fit" href="/"><ArrowLeft aria-hidden="true" size={17} />Quitter</Link>
              </div>
            </div>
            <Feedback message={error} tone="error" />
            <DocumentPaper document={document} />
            {document.document_type === "PAYMENT_RECEIPT" ? (
              <section className="mx-auto mt-6 max-w-2xl panel p-5 sm:p-7">
                <h2 className="text-lg font-bold text-ink">Reconnaissez-vous ce paiement ?</h2>
                <p className="mt-1 text-sm leading-6 text-muted">Votre réponse sera ajoutée au journal du paiement et visible par le bailleur.</p>
                {paymentStatus ? (
                  <div className="mt-5 flex items-center gap-3 rounded-xl bg-brand-soft p-4 text-sm font-bold text-brand-dark"><CheckCircle2 aria-hidden="true" size={19} />Réponse enregistrée : {paymentStatus}</div>
                ) : disputing ? (
                  <div className="mt-5">
                    <label><span className="form-label">Pourquoi contestez-vous ? *</span><textarea className="form-input min-h-28 resize-y" onChange={(event) => setReason(event.target.value)} placeholder="Expliquez ce qui ne correspond pas…" value={reason} /></label>
                    <Feedback message={error} tone="error" />
                    <div className="mt-4 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end"><button className="secondary-button" onClick={() => setDisputing(false)} type="button">Retour</button><button className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-red-700 px-4 text-sm font-bold text-white" disabled={loading} onClick={() => sendResponse("DISPUTE")} type="button"><XCircle aria-hidden="true" size={18} />Envoyer la contestation</button></div>
                  </div>
                ) : (
                  <div className="mt-5 grid gap-3 sm:grid-cols-2"><button className="primary-button" disabled={loading} onClick={() => sendResponse("CONFIRM")} type="button"><CheckCircle2 aria-hidden="true" size={18} />Je confirme</button><button className="secondary-button text-red-700" onClick={() => setDisputing(true)} type="button"><XCircle aria-hidden="true" size={18} />Je conteste</button></div>
                )}
              </section>
            ) : null}
          </div>
        ) : null}
      </main>
    </div>
  );
}
