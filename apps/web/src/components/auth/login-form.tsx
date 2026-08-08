"use client";

import { Eye, EyeOff, LogIn, Mail } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { Feedback } from "@/components/ui/feedback";
import type { CurrentUser, LoginPayload } from "@/types/auth";

const EMPTY_FORM: LoginPayload = { email: "", password: "" };

export function LoginForm({
  nextPath = "/tableau-de-bord",
}: {
  nextPath?: string;
}) {
  const router = useRouter();
  const { user, loading, sessionError, login } = useAuth();
  const [form, setForm] = useState<LoginPayload>(EMPTY_FORM);
  const [showPassword, setShowPassword] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const destinationFor = useCallback(
    (currentUser: CurrentUser) => {
      if (
        nextPath === "/tableau-de-bord" &&
        currentUser.has_tenant_access &&
        !currentUser.has_owner_access
      ) {
        return "/espace-locataire";
      }
      return nextPath;
    },
    [nextPath],
  );

  useEffect(() => {
    if (!loading && user) router.replace(destinationFor(user));
  }, [destinationFor, loading, router, user]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const authenticatedUser = await login({
        email: form.email.trim(),
        password: form.password,
      });
      router.replace(destinationFor(authenticatedUser));
      router.refresh();
    } catch (caughtError) {
      setError(
        caughtError instanceof Error ? caughtError.message : "Connexion impossible.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="space-y-4">
        <Feedback message={error ?? sessionError} tone="error" />

        <label>
          <span className="form-label">Adresse email</span>
          <span className="relative block">
            <Mail aria-hidden="true" className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted" size={18} />
            <input autoComplete="email" className="form-input pl-10" disabled={saving} onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))} placeholder="nom@exemple.com" required type="email" value={form.email} />
          </span>
        </label>

        <label>
          <span className="flex items-center justify-between gap-3">
            <span className="form-label">Mot de passe</span>
            <Link className="text-xs font-bold text-brand hover:text-brand-dark" href="/mot-de-passe-oublie">Mot de passe oublié ?</Link>
          </span>
          <span className="relative block">
            <input autoComplete="current-password" className="form-input pr-12" disabled={saving} onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))} required type={showPassword ? "text" : "password"} value={form.password} />
            <button aria-label={showPassword ? "Masquer le mot de passe" : "Afficher le mot de passe"} className="absolute right-1.5 top-1/2 grid size-9 -translate-y-1/2 place-items-center rounded-lg text-muted hover:bg-canvas hover:text-ink" onClick={() => setShowPassword((current) => !current)} type="button">{showPassword ? <EyeOff aria-hidden="true" size={18} /> : <Eye aria-hidden="true" size={18} />}</button>
          </span>
        </label>
      </div>

      <button className="primary-button mt-6 w-full" disabled={saving || loading} type="submit"><LogIn aria-hidden="true" size={18} />{saving ? "Connexion…" : "Se connecter"}</button>
      <p className="mt-4 text-center text-sm text-muted">Compte sans contact validé ? <Link className="font-bold text-brand hover:text-brand-dark" href="/verification-telephone">Vérifier mon téléphone</Link></p>
      <p className="mt-6 text-center text-sm text-muted">Vous n’avez pas encore de compte ? <Link className="font-bold text-brand hover:text-brand-dark" href="/inscription">Créer mon compte</Link></p>
    </form>
  );
}
