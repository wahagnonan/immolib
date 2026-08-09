"use client";

import {
  ChevronDown,
  CircleUserRound,
  LayoutDashboard,
  LoaderCircle,
  LogOut,
  ShieldX,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import {
  AdminDesktopNavigation,
  AdminMobileNavigation,
} from "@/components/admin/admin-navigation";
import { Brand } from "@/components/brand";

function ForbiddenScreen() {
  return (
    <div className="grid min-h-screen place-items-center bg-canvas px-5">
      <div className="max-w-md text-center">
        <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-brand-soft text-brand">
          <ShieldX aria-hidden="true" size={28} />
        </div>
        <h1 className="mt-5 text-xl font-bold text-ink">Accès réservé</h1>
        <p className="mt-2 text-sm leading-6 text-muted">
          Cet espace est réservé aux administrateurs ImmoLib. Vous êtes
          redirigé vers votre tableau de bord habituel.
        </p>
        <Link
          className="primary-button mt-6 inline-flex"
          href="/tableau-de-bord"
        >
          Retour à mon espace
        </Link>
      </div>
    </div>
  );
}

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, sessionError, logout } = useAuth();
  const [accountOpen, setAccountOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      router.replace(`/connexion?next=${encodeURIComponent(pathname)}`);
    }
  }, [loading, pathname, router, user]);

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await logout();
      setAccountOpen(false);
      router.replace("/connexion");
      router.refresh();
    } catch {
      setLoggingOut(false);
    }
  }

  if (loading || !user) {
    return (
      <div className="grid min-h-screen place-items-center bg-canvas px-5">
        <div className="text-center">
          <div className="inline-flex rounded-2xl bg-white p-4 shadow-lg">
            <Brand />
          </div>
          <p className="mt-6 flex items-center justify-center gap-2 text-sm font-semibold text-muted">
            <LoaderCircle aria-hidden="true" className="animate-spin" size={18} />
            {loading ? "Vérification de votre session…" : "Redirection vers la connexion…"}
          </p>
          {sessionError ? (
            <p className="mt-2 max-w-sm text-sm text-red-700">{sessionError}</p>
          ) : null}
        </div>
      </div>
    );
  }

  // La vraie protection est cote backend ; ici on evite simplement d'afficher
  // l'espace admin a un utilisateur sans le role systeme ADMIN.
  if (user.role !== "ADMIN") {
    return <ForbiddenScreen />;
  }

  const accountName = user?.full_name || user?.phone || "Administrateur";

  return (
    <div className="min-h-screen bg-canvas">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 border-r border-line bg-white px-3 py-5 lg:flex lg:flex-col">
        <div className="px-3">
          <Brand href="/admin" />
        </div>
        <p className="mb-3 mt-9 px-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">
          Administration ImmoLib
        </p>
        <div className="flex-1">
          <AdminDesktopNavigation />
        </div>
        <div className="border-t border-line pt-4">
          <Link
            className="flex min-h-11 items-center gap-3 rounded-[10px] px-3.5 text-sm font-semibold text-muted hover:bg-canvas hover:text-ink"
            href={user.has_owner_access ? "/tableau-de-bord" : "/connexion"}
          >
            <LayoutDashboard aria-hidden="true" size={19} />
            Espace utilisateur
          </Link>
        </div>
      </aside>

      <div className="lg:pl-60">
        <header className="sticky top-0 z-10 border-b border-line bg-white/95 backdrop-blur">
          <div className="flex h-[68px] items-center justify-between px-4 sm:px-7 lg:px-8">
            <div className="lg:hidden">
              <Brand href="/admin" />
            </div>
            <div className="hidden lg:block">
              <p className="text-sm font-semibold text-ink">ImmoLib Admin</p>
              <p className="text-xs text-muted">Supervision de la plateforme</p>
            </div>
            <div className="relative">
              <button
                aria-expanded={accountOpen}
                aria-haspopup="menu"
                aria-label="Ouvrir le menu du compte"
                className="flex min-h-11 items-center gap-2 rounded-[10px] border border-line px-2.5 text-left hover:bg-canvas sm:pr-3"
                onClick={() => setAccountOpen((current) => !current)}
                type="button"
              >
                <CircleUserRound aria-hidden="true" className="text-ink" size={23} />
                <span className="hidden max-w-44 sm:block">
                  <span className="block truncate text-xs font-bold text-ink">
                    {accountName}
                  </span>
                  <span className="block truncate text-[11px] text-muted">
                    {user.phone}
                  </span>
                </span>
                <ChevronDown
                  aria-hidden="true"
                  className={`hidden text-muted transition-transform sm:block ${
                    accountOpen ? "rotate-180" : ""
                  }`}
                  size={15}
                />
              </button>
              {accountOpen ? (
                <div
                  className="absolute right-0 top-[calc(100%+0.5rem)] z-30 w-72 rounded-[12px] border border-line bg-white p-2 shadow-[0_16px_36px_rgba(18,16,18,0.12)]"
                  role="menu"
                >
                  <div className="border-b border-line px-3 py-3">
                    <p className="truncate text-sm font-bold text-ink">{accountName}</p>
                    <p className="mt-0.5 truncate text-xs text-muted">{user.phone}</p>
                  </div>
                  {user.has_owner_access ? (
                    <Link
                      className="mt-1 flex min-h-10 w-full items-center gap-2 rounded-[9px] px-3 text-sm font-semibold text-ink hover:bg-canvas"
                      href="/tableau-de-bord"
                      onClick={() => setAccountOpen(false)}
                      role="menuitem"
                    >
                      <LayoutDashboard aria-hidden="true" size={17} />
                      Passer à l’espace bailleur
                    </Link>
                  ) : null}
                  <button
                    className="mt-1 flex min-h-10 w-full items-center gap-2 rounded-xl px-3 text-sm font-bold text-red-700 hover:bg-red-50 disabled:opacity-55"
                    disabled={loggingOut}
                    onClick={handleLogout}
                    role="menuitem"
                    type="button"
                  >
                    <LogOut aria-hidden="true" size={17} />
                    {loggingOut ? "Déconnexion…" : "Se déconnecter"}
                  </button>
                </div>
              ) : null}
            </div>
          </div>
          <AdminMobileNavigation />
        </header>

        <main
          className="mx-auto w-full max-w-[1380px] px-4 py-7 sm:px-7 sm:py-9 lg:px-8"
          id="contenu-principal"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
