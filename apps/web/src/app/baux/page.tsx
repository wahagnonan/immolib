import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { LeaseWorkspace } from "@/components/leases/lease-workspace";

export const metadata: Metadata = { title: "Baux" };

export default function LeasesPage() {
  return (
    <AppShell>
      <LeaseWorkspace />
    </AppShell>
  );
}
