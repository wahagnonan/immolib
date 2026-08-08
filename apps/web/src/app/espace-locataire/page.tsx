import type { Metadata } from "next";

import { PaymentRequestsWorkspace } from "@/components/payments/payment-requests-workspace";
import { TenantPortalShell } from "@/components/tenant-portal/tenant-portal-shell";
import { TenantPortalWorkspace } from "@/components/tenant-portal/tenant-portal-workspace";

export const metadata: Metadata = { title: "Espace locataire" };

export default function TenantPortalPage() {
  return (
    <TenantPortalShell>
      <PaymentRequestsWorkspace mode="tenant" />
      <TenantPortalWorkspace />
    </TenantPortalShell>
  );
}
