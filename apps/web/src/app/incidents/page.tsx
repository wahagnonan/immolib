import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { MaintenanceWorkspace } from "@/components/maintenance/maintenance-workspace";

export const metadata: Metadata = { title: "Incidents et maintenance" };

export default function MaintenancePage() {
  return (
    <AppShell>
      <MaintenanceWorkspace />
    </AppShell>
  );
}
