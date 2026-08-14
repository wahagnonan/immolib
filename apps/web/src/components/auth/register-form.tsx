"use client";

import { Eye, EyeOff, UserRoundPlus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { PhoneVerificationForm } from "@/components/auth/phone-verification-form";
import { Feedback } from "@/components/ui/feedback";
import type { RegisterPayload, RegistrationResult } from "@/types/auth";

const EMPTY_FORM: RegisterPayload = {
  phone: "",
  email: "",
  first_name: "",
  last_name: "",
  password: "",
  password_confirmation: "",
};

export function RegisterForm({
  initialValues,
  tenantInvitationToken,
  nextPath = "/tableau-de-bord",
}: {
  initialValues?: Partial<RegisterPayload>;
  tenantInvitationToken?: string;
  nextPath?: string;
}) {
  const router = useRouter();
  const { user, loading, register } = useAuth();
  const [form, setForm] = useState<RegisterPayload>({
    ...EMPTY_FORM,
    ...initialValues,
    tenant_invitation_token: tenantInvitationToken,
  });
  const [registration, setRegistration] = useState<RegistrationResult | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && user) router.replace(nextPath);
  }, [loading, nextPath, router, user]);

  function updateField(field: keyof RegisterPayload, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (form.password !== form.password_confirmation) {
      setError("Les deux mots de passe ne correspondent pas.");
      return;
    }
    setSaving(true);
    try {
      const result = await register({
        ...form,
        phone: form.phone.trim(),
        email: form.email?.trim(),
        first_name: form.first_name?.trim(),
        last_name: form.last_name?.trim(),
        tenant_invitation_token: tenantInvitationToken,
      });
      if (result.verification_required) {
        setRegistration(result);
      } else {
        router.replace(nextPath);
        router.refresh();
      }
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Inscription impossible.");
    } finally {
      setSaving(false);
    }
  }

  if (registration) {
    return (
      <div>
        <h2 className="text-lg font-bold text-ink">
          Vérifiez votre {registration.verification_channel === "EMAIL" ? "email" : "téléphone"}
        </h2>
        <p className="mt-2 text-sm leading-6 text-muted">
          Votre compte est créé. La session s’ouvrira après la validation du code reçu par{" "}
          {registration.verification_channel === "EMAIL" ? "email" : "SMS"}.
        </p>
        <div className="mt-5">
          <PhoneVerificationForm
            channel={registration.verification_channel}
            codeAlreadySent
            initialOtpCode={registration.otp_code}
            initialPhone={registration.user.phone}
            maskedDestination={registration.masked_destination}
            nextPath={nextPath}
          />
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="space-y-4">
        <Feedback message={error} tone="error" />
        <div className="grid gap-4 sm:grid-cols-2">
          <label><span className="form-label">Prénom *</span><input autoComplete="given-name" className="form-input" disabled={saving} onChange={(event) => updateField("first_name", event.target.value)} required value={form.first_name} /></label>
          <label><span className="form-label">Nom *</span><input autoComplete="family-name" className="form-input" disabled={saving} onChange={(event) => updateField("last_name", event.target.value)} required value={form.last_name} /></label>
        </div>
        <label><span className="form-label">Numéro de téléphone *</span><input autoComplete="tel" className="form-input" disabled={saving} onChange={(event) => updateField("phone", event.target.value)} placeholder="+225 07 00 00 00 00" readOnly={Boolean(tenantInvitationToken)} required type="tel" value={form.phone} /></label>
        <label><span className="form-label">Email (recommandé)</span><input autoComplete="email" className="form-input" disabled={saving} onChange={(event) => updateField("email", event.target.value)} placeholder="nom@exemple.com" readOnly={Boolean(tenantInvitationToken)} type="email" value={form.email} /><span className="mt-1.5 block text-xs leading-5 text-muted">{tenantInvitationToken ? "Ces coordonnées proviennent de l’invitation du bailleur." : "L’email permet d’activer gratuitement le compte. Sans email, le code est envoyé par SMS."}</span></label>
        <label>
          <span className="form-label">Mot de passe *</span>
          <span className="relative block"><input autoComplete="new-password" className="form-input pr-12" disabled={saving} minLength={8} onChange={(event) => updateField("password", event.target.value)} required type={showPassword ? "text" : "password"} value={form.password} /><button aria-label={showPassword ? "Masquer les mots de passe" : "Afficher les mots de passe"} className="absolute right-1.5 top-1/2 grid size-9 -translate-y-1/2 place-items-center rounded-lg text-muted hover:bg-canvas hover:text-ink" onClick={() => setShowPassword((current) => !current)} type="button">{showPassword ? <EyeOff aria-hidden="true" size={18} /> : <Eye aria-hidden="true" size={18} />}</button></span>
          <span className="mt-1.5 block text-xs leading-5 text-muted">Au moins 8 caractères. Utilisez une phrase difficile à deviner.</span>
        </label>
        <label><span className="form-label">Confirmer le mot de passe *</span><input autoComplete="new-password" className="form-input" disabled={saving} minLength={8} onChange={(event) => updateField("password_confirmation", event.target.value)} required type={showPassword ? "text" : "password"} value={form.password_confirmation} /></label>
      </div>

      <div className="mt-5 rounded-[10px] border border-line bg-canvas px-4 py-3 text-xs leading-5 text-muted">{tenantInvitationToken ? "Votre fiche locataire sera rattachée uniquement après la vérification du contact indiqué dans l’invitation." : "Une invitation de copropriétaire liée à ce numéro sera acceptée après la vérification du téléphone."}</div>
      <button className="primary-button mt-6 w-full" disabled={saving || loading} type="submit"><UserRoundPlus aria-hidden="true" size={18} />{saving ? "Création…" : "Créer mon compte"}</button>
      <p className="mt-6 text-center text-sm text-muted">Vous avez déjà un compte ? <Link className="font-bold text-brand hover:text-brand-dark" href="/connexion">Se connecter</Link></p>
    </form>
  );
}
