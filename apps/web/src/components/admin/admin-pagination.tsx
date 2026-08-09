"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

export function AdminPagination({
  page,
  count,
  pageSize,
  onChange,
}: {
  page: number;
  count: number;
  pageSize: number;
  onChange: (page: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(count / pageSize));
  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between gap-4 border-t border-line px-5 py-4">
      <p className="text-xs text-muted">
        {count} élément{count > 1 ? "s" : ""} — page {page} sur {totalPages}
      </p>
      <div className="flex items-center gap-2">
        <button
          aria-label="Page précédente"
          className="grid size-9 place-items-center rounded-[9px] border border-line text-muted hover:bg-canvas hover:text-ink disabled:opacity-40"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
          type="button"
        >
          <ChevronLeft aria-hidden="true" size={17} />
        </button>
        <span className="min-w-16 text-center text-xs font-semibold text-ink">
          {page} / {totalPages}
        </span>
        <button
          aria-label="Page suivante"
          className="grid size-9 place-items-center rounded-[9px] border border-line text-muted hover:bg-canvas hover:text-ink disabled:opacity-40"
          disabled={page >= totalPages}
          onClick={() => onChange(page + 1)}
          type="button"
        >
          <ChevronRight aria-hidden="true" size={17} />
        </button>
      </div>
    </div>
  );
}
