"use client";

import { RotateCcw, Send, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { Feedback } from "@/components/ui/feedback";
import { PhoneField } from "@/components/ui/phone-field";
import {
  requestEmailVerification,
  requestPhoneVerification,
} from "@/lib/auth-api-client";

export function PhoneVerificationForm({
  initialPhone = "",
  codeAlreadySent = false,
  initialOtpCode,
  channel = "SMS",
  maskedDestination,
  nextPath = "/tableau-de-bord",
}: {
  initialPhone?: string;
  codeAlreadySent?: boolean;
  initialOtpCode?: string;
  channel?: "EMAIL" | "SMS";
  maskedDestination?: string;
  nextPath?: string;
}) {
  const router = useRouter();
  const { user, loading, verifyEmail, verifyPhone } = useAuth();
  const [phone, setPhone] = useState(initialPhone);
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(codeAlreadySent);
  const [testCode, setTestCode] = useState(initialOtpCode ?? "");
  const [cooldown, setCooldown] = useState(codeAlreadySent ? 60 : 0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(
    codeAlreadySent
      ? `Un code à 6 chiffres a été envoyé par ${channel === "EMAIL" ? "email" : "SMS"}.`
      : null,
  );

  useEffect(() => {
    if (!loading && user) router.replace(nextPath);
  }, [loading, nextPath, router, user]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setInterval(
      () => setCooldown((value) => Math.max(0, value - 1)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [cooldown]);

  async function sendCode() {
    if (!phone.trim() || cooldown > 0) return;
    setSaving(true);
    setError(null);
    try {
      const result =
        channel === "EMAIL"
          ? await requestEmailVerification(phone.trim())
          : await requestPhoneVerification(phone.trim());
      setCodeSent(true);
      setNotice(result.detail);
      setTestCode(result.otp_code ?? "");
      setCooldown(60);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible de demander le code.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await sendCode();
  }

  async function handleVerification(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = { phone: phone.trim(), code: code.trim() };
      if (channel === "EMAIL") {
        await verifyEmail(payload);
      } else {
        await verifyPhone(payload);
      }
      router.replace(nextPath);
      router.refresh();
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Code invalide ou expiré.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (!codeSent) {
    return (
      <form onSubmit={handleRequest}>
        <Feedback message={error} tone="error" />
        <label className="mt-4 block">
          <span className="form-label">Numéro de téléphone</span>
          <PhoneField
            disabled={saving}
            onChange={setPhone}
            required
            value={phone}
          />
        </label>
        <button className="primary-button mt-6 w-full" disabled={saving} type="submit">
          <Send aria-hidden="true" size={18} />
          {saving ? "Envoi…" : "Recevoir mon code"}
        </button>
        <p className="mt-6 text-center text-sm text-muted">
          <Link className="font-bold text-brand hover:text-brand-dark" href="/connexion">
            Retour à la connexion
          </Link>
        </p>
      </form>
    );
  }

  return (
    <form onSubmit={handleVerification}>
      <Feedback message={error} tone="error" />
      <Feedback message={notice} tone="success" />
      {testCode ? (
        <p className="mt-4 rounded-[10px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Code de développement exposé par l’API : {testCode}
        </p>
      ) : null}
      <p className="mt-4 text-sm leading-6 text-muted">
        {channel === "EMAIL" ? "Email destinataire" : "Numéro concerné"} :{" "}
        <strong className="text-ink">
          {channel === "EMAIL" && maskedDestination
            ? maskedDestination
            : phone}
        </strong>
      </p>
      <label className="mt-4 block">
        <span className="form-label">
          Code reçu par {channel === "EMAIL" ? "email" : "SMS"}
        </span>
        <input
          autoComplete="one-time-code"
          className="form-input text-center text-lg tracking-[0.35em]"
          disabled={saving}
          inputMode="numeric"
          maxLength={6}
          onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
          pattern="\d{6}"
          placeholder="000000"
          required
          value={code}
        />
      </label>
      <button className="primary-button mt-6 w-full" disabled={saving} type="submit">
        <ShieldCheck aria-hidden="true" size={18} />
        {saving ? "Vérification…" : "Vérifier et me connecter"}
      </button>
      <button
        className="secondary-button mt-3 w-full"
        disabled={saving || cooldown > 0}
        onClick={sendCode}
        type="button"
      >
        <RotateCcw aria-hidden="true" size={17} />
        {cooldown > 0 ? `Renvoyer dans ${cooldown} s` : "Renvoyer le code"}
      </button>
      <p className="mt-5 text-center text-xs leading-5 text-muted">
        Le code expire après 10 minutes et devient inutilisable après cinq erreurs.
      </p>
    </form>
  );
}
