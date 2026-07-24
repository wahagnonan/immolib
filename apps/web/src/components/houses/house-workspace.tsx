"use client";

import {
  Building2,
  CheckCircle2,
  ChevronRight,
  HousePlus,
  MapPin,
  Search,
  UserRound,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { createHouse, listHouses } from "@/lib/api-client";
import type { CreateHousePayload, House, HouseStatus } from "@/types/domain";

const STATUS_STYLE: Record<HouseStatus, string> = {
  OCCUPIED: "status-paid",
  VACANT: "status-vacant",
  UNAVAILABLE: "bg-zinc-100 text-zinc-700",
};

const EMPTY_FORM: CreateHousePayload = {
  name: "",
  address: "",
  city: "Abidjan",
  commune: "",
  landmark: "",
};

export function HouseWorkspace() {
  const [houses, setHouses] = useState<House[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"ALL" | HouseStatus>("ALL");
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<CreateHousePayload>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listHouses()
      .then(setHouses)
      .catch((caughtError) =>
        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "Impossible de charger les maisons.",
        ),
      )
      .finally(() => setLoading(false));
  }, []);

  const filteredHouses = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("fr");

    return houses.filter((house) => {
      const matchesStatus = status === "ALL" || house.status === status;
      const searchable = [
        house.name,
        house.address,
        house.commune,
        house.city,
        house.landmark,
      ]
        .join(" ")
        .toLocaleLowerCase("fr");
      return matchesStatus && (!normalizedQuery || searchable.includes(normalizedQuery));
    });
  }, [houses, query, status]);

  const occupied = houses.filter((house) => house.status === "OCCUPIED").length;

  function updateField(field: keyof CreateHousePayload, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setFeedback(null);

    try {
      const house = await createHouse(form);
      setHouses((current) => [house, ...current]);
      setForm(EMPTY_FORM);
      setFormOpen(false);
      setFeedback("Maison ajoutée avec succès.");
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible d’ajouter cette maison pour le moment.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-col justify-between gap-5 xl:flex-row xl:items-end">
        <div>
          <p className="eyebrow">Patrimoine</p>
          <h1 className="page-title">Mes maisons</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted sm:text-base">
            Une maison devient le point de départ de tout le reste : copropriétaires,
            locataire, bail, échéances et quittances.
          </p>
        </div>
        <button
          className="primary-button w-fit"
          onClick={() => {
            setFormOpen(true);
            setFeedback(null);
          }}
          type="button"
        >
          <HousePlus aria-hidden="true" size={18} />
          Nouvelle maison
        </button>
      </section>

      {feedback ? (
        <div className="flex items-start gap-3 rounded-[10px] border border-[#dbeadf] bg-[#edf5ef] px-4 py-3 text-sm text-[#275c3b]">
          <CheckCircle2 aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
          <span>{feedback}</span>
        </div>
      ) : null}

      <section aria-label="Résumé des maisons" className="grid gap-3 sm:grid-cols-3">
        <div className="panel p-4">
          <p className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Total</p>
          <p className="mt-1 text-2xl font-bold tracking-[-0.04em] text-ink">{houses.length}</p>
        </div>
        <div className="panel p-4">
          <p className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Occupées</p>
          <p className="mt-1 text-2xl font-semibold tracking-[-0.04em] text-ink">{occupied}</p>
        </div>
        <div className="panel p-4">
          <p className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Vacantes</p>
          <p className="mt-1 text-2xl font-semibold tracking-[-0.04em] text-ink">
            {houses.filter((house) => house.status === "VACANT").length}
          </p>
        </div>
      </section>

      <section className="panel overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-line p-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <label className="relative block w-full sm:max-w-sm">
            <span className="sr-only">Rechercher une maison</span>
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted"
              size={18}
            />
            <input
              className="form-input pl-10"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Nom, commune, ville…"
              type="search"
              value={query}
            />
          </label>
          <label className="flex items-center gap-2 text-sm font-semibold text-muted">
            <span>Statut</span>
            <select
              className="form-input min-w-36"
              onChange={(event) => setStatus(event.target.value as "ALL" | HouseStatus)}
              value={status}
            >
              <option value="ALL">Toutes</option>
              <option value="OCCUPIED">Occupées</option>
              <option value="VACANT">Vacantes</option>
              <option value="UNAVAILABLE">Indisponibles</option>
            </select>
          </label>
        </div>

        {loading ? (
          <div className="px-5 py-16 text-center">
            <p className="font-bold text-ink">Chargement des maisons…</p>
          </div>
        ) : filteredHouses.length ? (
          <div className="grid gap-4 p-4 sm:p-5 md:grid-cols-2 2xl:grid-cols-3">
            {filteredHouses.map((house) => (
              <article
                className="group rounded-[14px] border border-line bg-white p-5 transition-colors hover:border-[#bbb3af]"
                key={house.id}
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="grid size-10 place-items-center rounded-[9px] bg-canvas text-ink">
                    <Building2 aria-hidden="true" size={20} />
                  </span>
                  <span className={`status-pill ${STATUS_STYLE[house.status]}`}>
                    {house.status_label}
                  </span>
                </div>
                <h2 className="mt-5 text-lg font-bold tracking-[-0.02em] text-ink">
                  {house.name}
                </h2>
                <p className="mt-2 flex items-start gap-2 text-sm leading-5 text-muted">
                  <MapPin aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
                  <span>
                    {house.address}
                    <span className="block">
                      {[house.commune, house.city].filter(Boolean).join(", ")}
                    </span>
                  </span>
                </p>
                <div className="mt-5 flex items-center justify-between border-t border-line pt-4">
                  <span className="flex items-center gap-2 text-xs font-semibold text-muted">
                    <UserRound aria-hidden="true" size={15} />
                    {house.ownerships.length > 1
                      ? `${house.ownerships.length} copropriétaires`
                      : "1 propriétaire"}
                  </span>
                  <button
                    aria-label={`Voir ${house.name}`}
                    className="grid size-9 place-items-center rounded-[9px] text-muted hover:bg-canvas hover:text-ink"
                    title={`Voir ${house.name}`}
                    type="button"
                  >
                    <ChevronRight aria-hidden="true" size={18} />
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="px-5 py-16 text-center">
            <p className="font-bold text-ink">
              {houses.length ? "Aucune maison trouvée" : "Aucune maison enregistrée"}
            </p>
            <p className="mt-1 text-sm text-muted">
              {houses.length
                ? "Modifiez votre recherche ou le filtre."
                : "Ajoutez votre première maison pour commencer la gestion locative."}
            </p>
          </div>
        )}
      </section>

      {formOpen ? (
        <div
          aria-labelledby="new-house-title"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-end justify-center bg-ink/40 p-0 sm:items-center sm:p-5"
          role="dialog"
        >
          <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-t-[18px] bg-white shadow-[0_24px_70px_rgba(18,16,18,0.18)] sm:rounded-[14px]">
            <div className="sticky top-0 flex items-center justify-between border-b border-line bg-white px-5 py-4 sm:px-6">
              <div>
                <p className="section-kicker">Étape 1</p>
                <h2 className="section-title" id="new-house-title">
                  Créer une maison
                </h2>
              </div>
              <button
                aria-label="Fermer le formulaire"
                className="grid size-10 place-items-center rounded-[9px] text-muted hover:bg-canvas hover:text-ink"
                onClick={() => setFormOpen(false)}
                title="Fermer"
                type="button"
              >
                <X aria-hidden="true" size={20} />
              </button>
            </div>

            <form className="p-5 sm:p-6" onSubmit={handleSubmit}>
              <p className="mb-6 text-sm leading-6 text-muted">
                Seules les maisons sont disponibles dans le MVP. Le créateur devient
                automatiquement propriétaire principal avec un accès actif.
              </p>
              <div className="grid gap-5 sm:grid-cols-2">
                <label className="sm:col-span-2">
                  <span className="form-label">Nom de la maison *</span>
                  <input
                    autoFocus
                    className="form-input"
                    maxLength={120}
                    onChange={(event) => updateField("name", event.target.value)}
                    placeholder="Ex. Villa des Lauriers"
                    required
                    value={form.name}
                  />
                </label>
                <label>
                  <span className="form-label">Ville *</span>
                  <input
                    className="form-input"
                    maxLength={120}
                    onChange={(event) => updateField("city", event.target.value)}
                    placeholder="Abidjan"
                    required
                    value={form.city}
                  />
                </label>
                <label>
                  <span className="form-label">Commune</span>
                  <input
                    className="form-input"
                    maxLength={120}
                    onChange={(event) => updateField("commune", event.target.value)}
                    placeholder="Cocody"
                    value={form.commune}
                  />
                </label>
                <label className="sm:col-span-2">
                  <span className="form-label">Adresse *</span>
                  <input
                    className="form-input"
                    maxLength={255}
                    onChange={(event) => updateField("address", event.target.value)}
                    placeholder="Rue, quartier ou lot"
                    required
                    value={form.address}
                  />
                </label>
                <label className="sm:col-span-2">
                  <span className="form-label">Repère</span>
                  <input
                    className="form-input"
                    maxLength={255}
                    onChange={(event) => updateField("landmark", event.target.value)}
                    placeholder="Ex. à 200 m de la pharmacie"
                    value={form.landmark}
                  />
                </label>
              </div>

              {error ? (
                <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
                  {error}
                </p>
              ) : null}

              <div className="mt-7 flex flex-col-reverse gap-3 border-t border-line pt-5 sm:flex-row sm:justify-end">
                <button
                  className="secondary-button"
                  onClick={() => setFormOpen(false)}
                  type="button"
                >
                  Annuler
                </button>
                <button className="primary-button" disabled={saving} type="submit">
                  <HousePlus aria-hidden="true" size={18} />
                  {saving ? "Enregistrement…" : "Créer la maison"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
