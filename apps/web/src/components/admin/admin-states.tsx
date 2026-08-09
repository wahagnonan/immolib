"use client";

import { LoaderCircle } from "lucide-react";

export function AdminLoading({ label = "Chargement…" }: { label?: string }) {
  return (
    <div className="flex min-h-48 items-center justify-center gap-2 text-sm font-semibold text-muted">
      <LoaderCircle aria-hidden="true" className="animate-spin" size={18} />
      {label}
    </div>
  );
}

export function AdminEmpty({ label }: { label: string }) {
  return (
    <div className="grid min-h-48 place-items-center rounded-[14px] border border-dashed border-line text-sm text-muted">
      {label}
    </div>
  );
}

export function AdminError({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="rounded-[14px] border border-red-200 bg-red-50 p-4 text-sm text-red-800">
      <p className="font-semibold">Impossible de charger les données.</p>
      <p className="mt-1">{message}</p>
      {onRetry ? (
        <button className="mt-3 text-sm font-bold text-red-800 underline" onClick={onRetry} type="button">
          Réessayer
        </button>
      ) : null}
    </div>
  );
}
