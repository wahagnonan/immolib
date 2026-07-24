import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { PhoneVerificationForm } from "@/components/auth/phone-verification-form";

export const metadata: Metadata = { title: "Vérifier mon téléphone" };

export default async function PhoneVerificationPage({
  searchParams,
}: {
  searchParams: Promise<{ phone?: string | string[] }>;
}) {
  const params = await searchParams;
  const phone = Array.isArray(params.phone) ? params.phone[0] : params.phone;
  return (
    <AuthShell
      eyebrow="Sécurité du compte"
      title="Vérifiez votre téléphone"
      description="Demandez un code à six chiffres, puis saisissez-le pour activer votre accès ImmoLib."
    >
      <PhoneVerificationForm initialPhone={phone ?? ""} />
    </AuthShell>
  );
}
