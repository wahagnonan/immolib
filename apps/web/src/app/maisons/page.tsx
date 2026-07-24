import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { HouseWorkspace } from "@/components/houses/house-workspace";

export const metadata: Metadata = {
  title: "Maisons",
};

export default function HousesPage() {
  return (
    <AppShell>
      <HouseWorkspace />
    </AppShell>
  );
}
