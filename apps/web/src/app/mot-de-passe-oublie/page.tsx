import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { PasswordResetForm } from "@/components/auth/password-reset-form";

export const metadata: Metadata = { title: "Mot de passe oublié" };

export default function PasswordResetPage() {
  return (
    <AuthShell
      eyebrow="Récupération du compte"
      title="Choisissez un nouveau mot de passe"
      description="Nous envoyons un code au numéro vérifié du compte. La réponse reste identique même si le numéro est inconnu."
    >
      <PasswordResetForm />
    </AuthShell>
  );
}
