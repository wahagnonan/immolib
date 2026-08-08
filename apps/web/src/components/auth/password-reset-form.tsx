"use client";

import { CheckCircle2, Eye, EyeOff, KeyRound, Send } from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { Feedback } from "@/components/ui/feedback";
import { PhoneField } from "@/components/ui/phone-field";
import {
  confirmPasswordReset,
  requestPasswordReset,
} from "@/lib/auth-api-client";

type Step = "PHONE" | "RESET" | "SUCCESS";

export function PasswordResetForm() {
  const [step, setStep] = useState<Step>("PHONE");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [testCode, setTestCode] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function requestCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const result = await requestPasswordReset(phone.trim());
      setNotice(result.detail);
      setTestCode(result.otp_code ?? "");
      setStep("RESET");
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

  async function resetPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (password !== confirmation) {
      setError("Les deux mots de passe ne correspondent pas.");
      return;
    }
    setSaving(true);
    try {
      await confirmPasswordReset({
        phone: phone.trim(),
        code: code.trim(),
        password,
        password_confirmation: confirmation,
      });
      setStep("SUCCESS");
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Réinitialisation impossible.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (step === "SUCCESS") {
    return (
      <div className="text-center">
        <CheckCircle2 aria-hidden="true" className="mx-auto text-brand" size={44} />
        <h2 className="mt-4 text-xl font-bold text-ink">Mot de passe modifié</h2>
        <p className="mt-2 text-sm leading-6 text-muted">
          Vous pouvez maintenant vous connecter avec votre nouveau mot de passe.
        </p>
        <Link className="primary-button mt-6 w-full" href="/connexion">
          Se connecter
        </Link>
      </div>
    );
  }

  if (step === "PHONE") {
    return (
      <form onSubmit={requestCode}>
        <Feedback message={error} tone="error" />
        <label className="mt-4 block">
          <span className="form-label">Numéro de téléphone du compte</span>
          <PhoneField
            disabled={saving}
            onChange={setPhone}
            required
            value={phone}
          />
        </label>
        <button className="primary-button mt-6 w-full" disabled={saving} type="submit">
          <Send aria-hidden="true" size={18} />
          {saving ? "Envoi…" : "Recevoir un code"}
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
    <form onSubmit={resetPassword}>
      <Feedback message={error} tone="error" />
      <Feedback message={notice} tone="success" />
      {testCode ? (
        <p className="mt-4 rounded-[10px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Code de développement exposé par l’API : {testCode}
        </p>
      ) : null}
      <p className="mt-4 text-sm text-muted">
        Réinitialisation pour <strong className="text-ink">{phone}</strong>
      </p>
      <div className="mt-4 space-y-4">
        <label>
          <span className="form-label">Code reçu par SMS</span>
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
        <label>
          <span className="form-label">Nouveau mot de passe</span>
          <span className="relative block">
            <input
              autoComplete="new-password"
              className="form-input pr-12"
              disabled={saving}
              minLength={8}
              onChange={(event) => setPassword(event.target.value)}
              required
              type={showPassword ? "text" : "password"}
              value={password}
            />
            <button
              aria-label={showPassword ? "Masquer les mots de passe" : "Afficher les mots de passe"}
              className="absolute right-1.5 top-1/2 grid size-9 -translate-y-1/2 place-items-center rounded-lg text-muted hover:bg-canvas hover:text-ink"
              onClick={() => setShowPassword((value) => !value)}
              type="button"
            >
              {showPassword ? <EyeOff aria-hidden="true" size={18} /> : <Eye aria-hidden="true" size={18} />}
            </button>
          </span>
        </label>
        <label>
          <span className="form-label">Confirmer le mot de passe</span>
          <input
            autoComplete="new-password"
            className="form-input"
            disabled={saving}
            minLength={8}
            onChange={(event) => setConfirmation(event.target.value)}
            required
            type={showPassword ? "text" : "password"}
            value={confirmation}
          />
        </label>
      </div>
      <button className="primary-button mt-6 w-full" disabled={saving} type="submit">
        <KeyRound aria-hidden="true" size={18} />
        {saving ? "Modification…" : "Modifier mon mot de passe"}
      </button>
      <button
        className="mt-4 w-full text-sm font-bold text-brand hover:text-brand-dark"
        onClick={() => setStep("PHONE")}
        type="button"
      >
        Changer de numéro
      </button>
    </form>
  );
}
