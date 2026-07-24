import type { Metadata } from "next";

import { PublicDocumentAccess } from "@/components/documents/public-document-access";

export const metadata: Metadata = {
  title: "Accès sécurisé au document",
  robots: { index: false, follow: false },
};

export default async function PublicDocumentPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <PublicDocumentAccess accessToken={token} />;
}
