import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { LoginForm } from "@/components/auth/login-form";

export const metadata: Metadata = { title: "Connexion" };

function safeNextPath(value: string | string[] | undefined) {
  const candidate = Array.isArray(value) ? value[0] : value;
  return candidate?.startsWith("/") && !candidate.startsWith("//")
    ? candidate
    : "/tableau-de-bord";
}

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const params = await searchParams;
  return (
    <AuthShell eyebrow="Ravi de vous revoir" title="Connectez-vous à ImmoLib" description="Retrouvez vos maisons, vos loyers et vos documents avec votre adresse email.">
      <LoginForm nextPath={safeNextPath(params.next)} />
    </AuthShell>
  );
}
