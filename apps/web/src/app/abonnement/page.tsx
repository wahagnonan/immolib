import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { SubscriptionWorkspace } from "@/components/subscription/subscription-workspace";

export const metadata: Metadata = {
  title: "Abonnement",
};

export default function SubscriptionPage() {
  return (
    <AppShell>
      <SubscriptionWorkspace />
    </AppShell>
  );
}
