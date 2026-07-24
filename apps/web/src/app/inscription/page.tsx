import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { RegisterForm } from "@/components/auth/register-form";

export const metadata: Metadata = { title: "Créer un compte" };

export default function RegisterPage() {
  return (
    <AuthShell eyebrow="Nouveau compte" title="Créez votre compte" description="Votre numéro devient votre identifiant ImmoLib. L’email vérifié est privilégié et le SMS reste le canal de repli.">
      <RegisterForm />
    </AuthShell>
  );
}
