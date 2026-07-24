import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { PaymentWorkspace } from "@/components/payments/payment-workspace";

export const metadata: Metadata = { title: "Paiements" };

export default async function PaymentsPage({
  searchParams,
}: {
  searchParams: Promise<{ charge?: string | string[] }>;
}) {
  const { charge } = await searchParams;
  return (
    <AppShell>
      <PaymentWorkspace initialChargeId={typeof charge === "string" ? charge : undefined} />
    </AppShell>
  );
}
