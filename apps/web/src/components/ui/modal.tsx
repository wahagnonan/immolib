"use client";

import { X } from "lucide-react";
import { useEffect } from "react";

type ModalProps = {
  open: boolean;
  title: string;
  kicker?: string;
  description?: string;
  onClose: () => void;
  children: React.ReactNode;
  size?: "md" | "lg" | "xl";
};

const sizes = {
  md: "max-w-xl",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
};

export function Modal({
  open,
  title,
  kicker,
  description,
  onClose,
  children,
  size = "lg",
}: ModalProps) {
  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose, open]);

  if (!open) return null;

  return (
    <div
      aria-labelledby="modal-title"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink/40 p-0 sm:items-center sm:p-5"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      role="dialog"
    >
      <div
        className={`max-h-[94vh] w-full ${sizes[size]} overflow-y-auto rounded-t-[18px] bg-white shadow-[0_24px_70px_rgba(18,16,18,0.18)] sm:rounded-[14px]`}
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-line bg-white px-5 py-4 sm:px-6">
          <div>
            {kicker ? <p className="section-kicker">{kicker}</p> : null}
            <h2 className="section-title" id="modal-title">
              {title}
            </h2>
            {description ? (
              <p className="mt-1 max-w-2xl text-sm leading-5 text-muted">{description}</p>
            ) : null}
          </div>
          <button
            aria-label="Fermer"
            className="grid size-10 shrink-0 place-items-center rounded-[9px] text-muted hover:bg-canvas hover:text-ink"
            onClick={onClose}
            title="Fermer"
            type="button"
          >
            <X aria-hidden="true" size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
