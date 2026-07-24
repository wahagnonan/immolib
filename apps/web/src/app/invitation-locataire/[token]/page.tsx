import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { TenantInvitationOnboarding } from "@/components/tenants/tenant-invitation-onboarding";

export const metadata: Metadata = { title: "Invitation locataire" };

export default async function TenantInvitationPage({
  params,
  searchParams,
}: {
  params: Promise<{ token: string }>;
  searchParams: Promise<{ terminee?: string }>;
}) {
  const [{ token }, query] = await Promise.all([params, searchParams]);
  return (
    <AuthShell
      audience="tenant"
      description="Vérifiez l’invitation, puis créez ou rattachez votre compte ImmoLib."
      eyebrow="Accès sécurisé"
      title="Rejoindre ma location"
    >
      <TenantInvitationOnboarding
        completed={query.terminee === "1"}
        token={token}
      />
    </AuthShell>
  );
}

