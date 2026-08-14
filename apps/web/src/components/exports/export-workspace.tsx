"use client";

import {
  CalendarRange,
  Download,
  FileSpreadsheet,
  FileText,
  FileUp,
  LoaderCircle,
  ReceiptText,
  Users,
} from "lucide-react";
import { FormEvent, useState } from "react";

import { Feedback } from "@/components/ui/feedback";
import { ModuleHeader } from "@/components/ui/module-header";

type ExportType = "payments" | "charges" | "documents" | "tenants" | "leases";
type ExportFormat = "csv" | "pdf";

const exportOptions: Array<{
  value: ExportType;
  label: string;
  description: string;
  icon: typeof Download;
}> = [
  {
    value: "payments",
    label: "Paiements",
    description: "Historique des paiements avec montants, statuts et affectations",
    icon: ReceiptText,
  },
  {
    value: "charges",
    label: "Échéances",
    description: "Échéances mensuelles avec soldes et dates d'échéance",
    icon: CalendarRange,
  },
  {
    value: "documents",
    label: "Documents",
    description: "Reçus, quittances et relevés avec références vérifiables",
    icon: FileText,
  },
  {
    value: "tenants",
    label: "Locataires",
    description: "Liste des locataires avec coordonnées et statuts",
    icon: Users,
  },
  {
    value: "leases",
    label: "Baux",
    description: "Baux actifs et terminés avec montants et conditions",
    icon: FileSpreadsheet,
  },
];

export function ExportWorkspace() {
  const [selectedType, setSelectedType] = useState<ExportType>("payments");
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>("csv");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const needsDateFilter = selectedType === "payments" || selectedType === "charges" || selectedType === "documents";

  async function handleExport(format: ExportFormat) {
    setLoading(true);
    setError(null);
    setFeedback(null);

    try {
      const params = new URLSearchParams({ type: selectedType, format });
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "/backend";
      const url = `${apiUrl}/api/v1/exports/?${params.toString()}`;

      const response = await fetch(url, {
        credentials: "include",
        headers: {
          "X-CSRFToken": getCookie("csrftoken"),
        },
      });

      if (!response.ok) {
        throw new Error("Erreur lors de l'export");
      }

      // Télécharger le fichier
      const blob = await response.blob();
      const contentDisposition = response.headers.get("Content-Disposition");
      const filenameMatch = contentDisposition?.match(/filename="?(.+?)"?$/);
      const filename = filenameMatch?.[1] || `immolib-${selectedType}.${format}`;

      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);

      setFeedback("Export téléchargé avec succès.");
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible de générer l'export.",
      );
    } finally {
      setLoading(false);
    }
  }

  const selectedOption = exportOptions.find((opt) => opt.value === selectedType);

  return (
    <div className="space-y-6">
      <ModuleHeader
        description="Téléchargez vos données locatives en CSV (Excel, Google Sheets) ou en PDF imprimable."
        eyebrow="Données"
        title="Exporter"
      />
      <Feedback message={feedback} />
      <Feedback message={error} tone="error" />

      <form onSubmit={(e) => e.preventDefault()}>
        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {exportOptions.map((option) => {
            const Icon = option.icon;
            const active = selectedType === option.value;
            return (
              <button
                className={`rounded-[14px] border p-5 text-left transition-colors ${
                  active
                    ? "border-brand bg-brand-soft ring-2 ring-brand/10"
                    : "border-line bg-white hover:border-brand/40"
                }`}
                key={option.value}
                onClick={() => setSelectedType(option.value)}
                type="button"
              >
                <span
                  className={`grid size-10 place-items-center rounded-[9px] ${
                    active ? "bg-brand text-white" : "bg-canvas text-ink"
                  }`}
                >
                  <Icon size={19} />
                </span>
                <p className="mt-4 font-semibold text-ink">{option.label}</p>
                <p className="mt-1 text-sm text-muted">{option.description}</p>
              </button>
            );
          })}
        </section>

        {needsDateFilter && (
          <section className="mt-5 rounded-[14px] border border-line bg-white p-5">
            <p className="text-sm font-semibold text-ink">Filtrer par période</p>
            <div className="mt-3 flex flex-col gap-3 sm:flex-row">
              <label className="flex-1">
                <span className="form-label">Du</span>
                <input
                  className="form-input"
                  onChange={(event) => setDateFrom(event.target.value)}
                  type="date"
                  value={dateFrom}
                />
              </label>
              <label className="flex-1">
                <span className="form-label">Au</span>
                <input
                  className="form-input"
                  onChange={(event) => setDateTo(event.target.value)}
                  type="date"
                  value={dateTo}
                />
              </label>
            </div>
            <p className="mt-2 text-xs text-muted">
              Laissez vide pour exporter toutes les données.
            </p>
          </section>
        )}

        <div className="mt-5 rounded-[14px] border border-line bg-canvas p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-semibold text-ink">
                Export {selectedOption?.label}
              </p>
              <p className="mt-1 text-sm text-muted">
                Choisissez le format de téléchargement
              </p>
            </div>
            <div className="flex gap-3">
              <button
                className="secondary-button"
                disabled={loading}
                onClick={() => handleExport("csv")}
                type="button"
              >
                {loading ? (
                  <LoaderCircle aria-hidden="true" className="animate-spin" size={18} />
                ) : (
                  <FileSpreadsheet aria-hidden="true" size={18} />
                )}
                CSV
              </button>
              <button
                className="primary-button"
                disabled={loading}
                onClick={() => handleExport("pdf")}
                type="button"
              >
                {loading ? (
                  <LoaderCircle aria-hidden="true" className="animate-spin" size={18} />
                ) : (
                  <FileUp aria-hidden="true" size={18} />
                )}
                PDF
              </button>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}

function getCookie(name: string): string {
  const cookies = document.cookie.split(";");
  for (const cookie of cookies) {
    const [key, value] = cookie.trim().split("=");
    if (key === name) return value;
  }
  return "";
}
