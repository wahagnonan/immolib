import { AdminShell } from "@/components/admin/admin-shell";

export const metadata = {
  title: "Administration — ImmoLib",
  description:
    "Espace d'administration ImmoLib : utilisateurs, abonnements, biens et supervision.",
};

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AdminShell>{children}</AdminShell>;
}
