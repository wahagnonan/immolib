import type { Metadata } from "next";

import { TenantPortalShell } from "@/components/tenant-portal/tenant-portal-shell";
import { TenantPortalWorkspace } from "@/components/tenant-portal/tenant-portal-workspace";

export const metadata: Metadata = { title: "Espace locataire" };

export default function TenantPortalPage() {
  return (
    <TenantPortalShell>
      <TenantPortalWorkspace />
    </TenantPortalShell>
  );
}
