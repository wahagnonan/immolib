"use client";

import {
  Bell,
  CalendarClock,
  ChevronDown,
  CircleUserRound,
  FileCheck2,
  Gauge,
  HandCoins,
  House,
  LoaderCircle,
  LogOut,
  Menu,
  PanelsTopLeft,
  Wrench,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { Brand } from "@/components/brand";

const tenantNavigation = [
  { href: "/espace-locataire#apercu", label: "Vue d’ensemble", icon: Gauge },
  { href: "/espace-locataire#location", label: "Ma location", icon: House },
  { href: "/espace-locataire#echeances", label: "Échéances", icon: CalendarClock },
  { href: "/espace-locataire#paiements", label: "Paiements", icon: HandCoins },
  { href: "/espace-locataire#documents", label: "Documents", icon: FileCheck2 },
  { href: "/espace-locataire#incidents", label: "Incidents", icon: Wrench },
];

function TenantNavigation({ mobile = false }: { mobile?: boolean }) {
  return (
    <nav
      aria-label="Navigation de l’espace locataire"
      className={mobile ? "grid grid-cols-2 gap-1 p-3 sm:grid-cols-3 sm:px-6" : "space-y-1"}
    >
      {tenantNavigation.map((item) => {
        const Icon = item.icon;
        return (
          <Link
            className={
              mobile
                ? "flex min-h-11 items-center gap-2 rounded-[9px] px-3 text-xs font-semibold text-muted hover:bg-canvas hover:text-ink"
                : "flex min-h-11 items-center gap-3 rounded-[10px] px-3.5 py-2.5 text-sm font-semibold text-muted transition-colors hover:bg-canvas hover:text-ink"
            }
            href={item.href}
            key={item.href}
          >
            <Icon aria-hidden="true" size={mobile ? 16 : 19} />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

export function TenantPortalShell({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, sessionError, logout } = useAuth();
  const [accountOpen, setAccountOpen] = useState(false);
  const [navigationOpen, setNavigationOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.replace(`/connexion?next=${encodeURIComponent(pathname)}`);
    }
  }, [loading, pathname, router, user]);

  async function handleLogout() {
    setLoggingOut(true);
    setLogoutError(null);
    try {
      await logout();
      router.replace("/connexion");
      router.refresh();
    } catch (caughtError) {
      setLogoutError(
        caughtError instanceof Error
          ? caughtError.message
          : "Déconnexion impossible.",
      );
    } finally {
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
            {loading
              ? "Vérification de votre session…"
              : "Redirection vers la connexion…"}
          </p>
          {sessionError ? (
            <p className="mt-2 max-w-sm text-sm text-red-700">{sessionError}</p>
          ) : null}
        </div>
      </div>
    );
  }

  const accountName = user?.full_name || user?.phone || "Compte locataire";

  return (
    <div className="min-h-screen bg-canvas">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 border-r border-line bg-white px-3 py-5 lg:flex lg:flex-col">
        <div className="px-3">
          <Brand href="/espace-locataire" />
        </div>
        <p className="mb-3 mt-9 px-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">
          Espace locataire
        </p>
        <div className="flex-1">
          <TenantNavigation />
        </div>
        <Link
          className="flex min-h-11 items-center gap-3 rounded-xl border-t border-line px-3.5 pt-4 text-sm font-semibold text-muted hover:text-ink"
          href="/parametres/notifications"
        >
          <Bell aria-hidden="true" size={19} />
          Notifications
        </Link>
      </aside>

      <div className="lg:pl-60">
        <header className="sticky top-0 z-20 border-b border-line bg-white/95 backdrop-blur">
          <div className="flex h-[68px] items-center justify-between px-4 sm:px-7 lg:px-8">
            <div className="lg:hidden">
              <Brand href="/espace-locataire" />
            </div>
            <div className="hidden lg:block">
              <p className="text-sm font-semibold text-ink">Mon espace locataire</p>
              <p className="text-xs text-muted">Loyers, paiements et preuves</p>
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
                  className={`hidden text-muted transition-transform sm:block ${accountOpen ? "rotate-180" : ""}`}
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
                    <p className="mt-0.5 truncate text-xs text-muted">{user?.phone}</p>
                  </div>
                  {user?.has_owner_access ? (
                    <Link
                      className="mt-1 flex min-h-10 w-full items-center gap-2 rounded-[9px] px-3 text-sm font-semibold text-ink hover:bg-canvas"
                      href="/tableau-de-bord"
                      onClick={() => setAccountOpen(false)}
                      role="menuitem"
                    >
                      <PanelsTopLeft aria-hidden="true" size={17} />
                      Passer à l’espace bailleur
                    </Link>
                  ) : null}
                  <Link
                    className="mt-1 flex min-h-10 w-full items-center gap-2 rounded-[9px] px-3 text-sm font-semibold text-ink hover:bg-canvas"
                    href="/parametres/notifications"
                    onClick={() => setAccountOpen(false)}
                    role="menuitem"
                  >
                    <Bell aria-hidden="true" size={17} />
                    Préférences de notification
                  </Link>
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
                  {logoutError ? (
                    <p className="px-3 py-2 text-xs text-red-700" role="alert">
                      {logoutError}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>
          <div className="border-t border-line lg:hidden">
            <button
              aria-expanded={navigationOpen}
              className="flex min-h-12 w-full items-center justify-between px-4 text-sm font-semibold text-ink sm:px-7"
              onClick={() => setNavigationOpen((current) => !current)}
              type="button"
            >
              Navigation locataire
              {navigationOpen ? <X size={19} /> : <Menu size={19} />}
            </button>
            {navigationOpen ? <TenantNavigation mobile /> : null}
          </div>
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
