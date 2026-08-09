"use client";

import {
  FileClock,
  Gauge,
  House,
  Landmark,
  Menu,
  Users,
  UsersRound,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

export const adminNavigation = [
  { href: "/admin", label: "Dashboard", icon: Gauge },
  { href: "/admin/users", label: "Utilisateurs", icon: Users },
  { href: "/admin/landlords", label: "Bailleurs", icon: Landmark },
  { href: "/admin/houses", label: "Maisons", icon: House },
  { href: "/admin/subscriptions", label: "Abonnements", icon: UsersRound },
  { href: "/admin/audit-logs", label: "Journal d’audit", icon: FileClock },
];

function isCurrent(pathname: string, href: string) {
  if (href === "/admin") return pathname === "/admin";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AdminDesktopNavigation() {
  const pathname = usePathname();

  return (
    <nav aria-label="Navigation administration" className="space-y-1">
      {adminNavigation.map((item) => {
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

export function AdminMobileNavigation() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const current =
    adminNavigation.find((item) => isCurrent(pathname, item.href))?.label ??
    "Administration";

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
          aria-label="Navigation admin mobile"
          className="grid grid-cols-2 gap-1 border-t border-line p-3 sm:grid-cols-3 sm:px-6"
        >
          {adminNavigation.map((item) => {
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
