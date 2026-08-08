import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { RegisterForm } from "@/components/auth/register-form";

export const metadata: Metadata = { title: "Créer un compte" };

export default function RegisterPage() {
  return (
    <AuthShell eyebrow="Nouveau compte" title="Créez votre compte" description="Votre adresse email devient votre identifiant ImmoLib. Le téléphone sert à la vérification du compte.">
      <RegisterForm />
    </AuthShell>
  );
}
