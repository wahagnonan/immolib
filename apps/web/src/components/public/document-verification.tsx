"use client";

import {
  AlertTriangle,
  BadgeCheck,
  CalendarDays,
  LoaderCircle,
  SearchCheck,
  ShieldX,
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { verifyDocumentReference } from "@/lib/api-client";
import { formatDate, monthLabel } from "@/lib/format";
import type { PublicDocumentVerification } from "@/types/domain";

function formatCurrency(value: string, currency: string) {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(value));
}

export function DocumentVerification({
  initialReference = "",
}: {
  initialReference?: string;
}) {
  const [reference, setReference] = useState(initialReference);
  const [result, setResult] = useState<PublicDocumentVerification | null>(null);
  const [loading, setLoading] = useState(() => Boolean(initialReference.trim()));
  const [error, setError] = useState<string | null>(null);

  async function verify(value: string) {
    const normalized = value.trim().toUpperCase();
    if (!normalized) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const verification = await verifyDocumentReference(normalized);
      setResult(verification);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "La vérification est momentanément indisponible.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const normalized = initialReference.trim().toUpperCase();
    if (!normalized) return;
    let active = true;
    verifyDocumentReference(normalized)
      .then((verification) => {
        if (active) setResult(verification);
      })
      .catch((caughtError) => {
        if (active) {
          setError(
            caughtError instanceof Error
              ? caughtError.message
              : "La vérification est momentanément indisponible.",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [initialReference]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = reference.trim().toUpperCase();
    setReference(normalized);
    const nextUrl = normalized
      ? `/verifier-quittance?reference=${encodeURIComponent(normalized)}`
      : "/verifier-quittance";
    window.history.replaceState(null, "", nextUrl);
    void verify(normalized);
  }

  const active = result?.authentic && result.status === "ACTIVE";

  return (
    <div className="space-y-5">
      <form className="panel p-5 sm:p-6" onSubmit={handleSubmit}>
        <label htmlFor="verification-reference">
          <span className="form-label">Référence du document</span>
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              autoComplete="off"
              className="form-input font-mono uppercase"
              id="verification-reference"
              onChange={(event) => setReference(event.target.value)}
              placeholder="IMM-QUT-2026-…"
              required
              value={reference}
            />
            <button
              className="primary-button shrink-0"
              disabled={loading || !reference.trim()}
              type="submit"
            >
              {loading ? (
                <LoaderCircle aria-hidden="true" className="animate-spin" size={18} />
              ) : (
                <SearchCheck aria-hidden="true" size={18} />
              )}
              Vérifier
            </button>
          </div>
        </label>
      </form>

      {error ? (
        <section className="rounded-2xl border border-red-200 bg-red-50 p-6 sm:p-8">
          <span className="grid size-12 place-items-center rounded-2xl bg-white text-red-700">
            <ShieldX aria-hidden="true" size={25} />
          </span>
          <h2 className="mt-5 text-xl font-bold text-red-900">
            Document non reconnu
          </h2>
          <p className="mt-2 text-sm leading-6 text-red-800">{error}</p>
          <p className="mt-3 text-xs leading-5 text-red-700">
            Vérifiez chaque caractère de la référence. Ne considérez pas le
            document comme vérifiable tant que la vérification échoue.
          </p>
        </section>
      ) : null}

      {result ? (
        <section
          className={`overflow-hidden rounded-2xl border bg-white shadow-[0_16px_45px_rgba(22,45,34,0.08)] ${
            active ? "border-brand/30" : "border-red-200"
          }`}
        >
          <div
            className={`flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between sm:p-8 ${
            active ? "bg-[#edf5ef]" : "bg-red-50"
            }`}
          >
            <div className="flex items-center gap-4">
              <span
                className={`grid size-14 shrink-0 place-items-center rounded-2xl bg-white ${
                  active ? "text-[#275c3b]" : "text-red-700"
                }`}
              >
                {active ? (
                  <BadgeCheck aria-hidden="true" size={30} />
                ) : (
                  <AlertTriangle aria-hidden="true" size={28} />
                )}
              </span>
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-muted">
                  Résultat de la vérification
                </p>
                <h2 className="mt-1 text-2xl font-bold text-ink">
                  {active
                    ? "Document ImmoLib vérifiable"
                    : "Document ImmoLib annulé"}
                </h2>
              </div>
            </div>
            <span className={`status-pill ${active ? "status-paid" : "status-late"}`}>
              {result.status_label}
            </span>
          </div>

          <div className="p-6 sm:p-8">
            <p className="font-mono text-xs font-bold uppercase tracking-[0.08em] text-brand">
              {result.reference}
            </p>
            <h3 className="mt-2 text-xl font-bold text-ink">
              {result.document_type_label}
            </h3>
            <dl className="mt-7 grid gap-5 border-t border-line pt-6 sm:grid-cols-2">
              <div>
                <dt className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.1em] text-muted">
                  Type de document
                </dt>
                <dd className="mt-2 font-bold text-ink">
                  {result.document_type_label}
                </dd>
                <dd className="mt-1 text-sm text-muted">
                  Émis le {formatDate(result.issued_at)}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted">
                  Statut
                </dt>
                <dd className="mt-2 font-bold text-ink">{result.status_label}</dd>
                <dd className="mt-1 text-sm text-muted">
                  Les identités et l’adresse restent confidentielles.
                </dd>
              </div>
              <div>
                <dt className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.1em] text-muted">
                  <CalendarDays size={15} /> Période
                </dt>
                <dd className="mt-2 font-bold capitalize text-ink">
                  {monthLabel(result.period)}
                </dd>
                <dd className="mt-1 text-sm text-muted">
                  Émis le {formatDate(result.issued_at)}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted">
                  Montant documenté
                </dt>
                <dd className="mt-2 text-xl font-bold text-ink">
                  {formatCurrency(result.amount, result.currency)}
                </dd>
                <dd className="mt-1 text-sm text-muted">{result.currency}</dd>
              </div>
            </dl>
          </div>
        </section>
      ) : null}
    </div>
  );
}
