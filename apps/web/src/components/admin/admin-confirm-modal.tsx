"use client";

import { AlertTriangle } from "lucide-react";

import { Modal } from "@/components/ui/modal";

export function AdminConfirmModal({
  open,
  title,
  description,
  confirmLabel = "Confirmer",
  busyLabel = "En cours…",
  busy = false,
  error,
  onConfirm,
  onClose,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  busyLabel?: string;
  busy?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <Modal
      description={description}
      onClose={onClose}
      open={open}
      size="md"
      title={title}
    >
      <div className="px-5 py-5 sm:px-6">
        <p className="flex items-start gap-2 rounded-[10px] bg-amber-50 p-3 text-sm leading-5 text-[#7c5a15]">
          <AlertTriangle aria-hidden="true" className="mt-0.5 shrink-0" size={17} />
          Cette action est sensible et sera enregistrée dans le journal d’audit.
        </p>
        {error ? (
          <p className="mt-3 rounded-[10px] bg-red-50 p-3 text-sm text-red-800" role="alert">
            {error}
          </p>
        ) : null}
        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            className="secondary-button"
            disabled={busy}
            onClick={onClose}
            type="button"
          >
            Annuler
          </button>
          <button
            className="primary-button"
            disabled={busy}
            onClick={onConfirm}
            type="button"
          >
            {busy ? busyLabel : confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  );
}
