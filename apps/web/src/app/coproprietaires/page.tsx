import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { CoOwnerWorkspace } from "@/components/coowners/coowner-workspace";

export const metadata: Metadata = { title: "Copropriétaires" };

export default function CoOwnersPage() {
  return (
    <AppShell>
      <CoOwnerWorkspace />
    </AppShell>
  );
}
