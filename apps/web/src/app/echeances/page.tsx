import type { Metadata } from "next";

import { ChargeWorkspace } from "@/components/charges/charge-workspace";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = { title: "Échéances" };

export default function ChargesPage() {
  return (
    <AppShell>
      <ChargeWorkspace />
    </AppShell>
  );
}
