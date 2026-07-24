import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { DocumentWorkspace } from "@/components/documents/document-workspace";

export const metadata: Metadata = { title: "Documents" };

export default function DocumentsPage() {
  return (
    <AppShell>
      <DocumentWorkspace />
    </AppShell>
  );
}
