"use client";

import {
  Building2,
  CreditCard,
  FileCheck2,
  Gauge,
  HandCoins,
  House,
  Menu,
  ReceiptText,
  Settings2,
  Users,
  UsersRound,
  Wrench,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const navigation = [
  { href: "/tableau-de-bord", label: "Tableau de bord", icon: Gauge },
  { href: "/maisons", label: "Maisons", icon: House },
  { href: "/locataires", label: "Locataires", icon: Users },
  { href: "/baux", label: "Baux", icon: FileCheck2 },
  { href: "/echeances", label: "Échéances", icon: ReceiptText },
  { href: "/paiements", label: "Paiements", icon: HandCoins },
  { href: "/documents", label: "Documents", icon: Building2 },
  { href: "/incidents", label: "Incidents", icon: Wrench },
  { href: "/coproprietaires", label: "Copropriétaires", icon: UsersRound },
  { href: "/abonnement", label: "Abonnement", icon: CreditCard },
  { href: "/parametres/notifications", label: "Notifications", icon: Settings2 },
];

function isCurrent(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function DesktopNavigation() {
  const pathname = usePathname();

  return (
    <nav aria-label="Navigation principale" className="space-y-1">
      {navigation.map((item) => {
        const active = isCurrent(pathname, item.href);
        const Icon = item.icon;

        return (
          <Link
            aria-current={active ? "page" : undefined}
            className={`flex min-h-11 items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-semibold transition-colors ${
              active
                ? "bg-canvas text-ink"
                : "text-muted hover:bg-canvas/70 hover:text-ink"
            }`}
            href={item.href}
            key={item.href}
          >
            <Icon
              aria-hidden="true"
              className={active ? "text-brand" : ""}
              size={18}
              strokeWidth={active ? 2.3 : 1.9}
            />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

export function MobileNavigation() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const current =
    navigation.find((item) => isCurrent(pathname, item.href))?.label ??
    "Navigation";

  return (
    <div className="border-b border-line bg-white lg:hidden">
      <button
        aria-expanded={open}
        className="flex min-h-12 w-full items-center justify-between px-4 text-sm font-semibold text-ink sm:px-7"
        onClick={() => setOpen((currentValue) => !currentValue)}
        type="button"
      >
        <span>{current}</span>
        {open ? <X aria-hidden="true" size={19} /> : <Menu aria-hidden="true" size={19} />}
      </button>
      {open ? (
        <nav
          aria-label="Navigation mobile"
          className="grid grid-cols-2 gap-1 border-t border-line p-3 sm:grid-cols-3 sm:px-6"
        >
          {navigation.map((item) => {
            const active = isCurrent(pathname, item.href);
            const Icon = item.icon;

            return (
              <Link
                aria-current={active ? "page" : undefined}
                className={`flex min-h-11 items-center gap-2.5 rounded-[9px] px-3 text-xs font-semibold ${
                  active ? "bg-canvas text-ink" : "text-muted hover:bg-canvas"
                }`}
                href={item.href}
                key={item.href}
                onClick={() => setOpen(false)}
              >
                <Icon
                  aria-hidden="true"
                  className={active ? "text-brand" : ""}
                  size={16}
                />
                {item.label}
              </Link>
            );
          })}
        </nav>
      ) : null}
    </div>
  );
}
