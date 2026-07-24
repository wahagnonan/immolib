import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { TenantWorkspace } from "@/components/tenants/tenant-workspace";

export const metadata: Metadata = { title: "Locataires" };

export default function TenantsPage() {
  return (
    <AppShell>
      <TenantWorkspace />
    </AppShell>
  );
}
