import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { DashboardWorkspace } from "@/components/dashboard/dashboard-workspace";

export const metadata: Metadata = { title: "Tableau de bord" };

export default function DashboardPage() {
  return (
    <AppShell>
      <DashboardWorkspace />
    </AppShell>
  );
}
