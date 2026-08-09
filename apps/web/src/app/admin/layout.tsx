import { AdminShell } from "@/components/admin/admin-shell";

export const metadata = {
  title: "Administration — ImmoLib",
  description:
    "Espace d'administration ImmoLib : utilisateurs, abonnements, maisons et supervision.",
};

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AdminShell>{children}</AdminShell>;
}
