"use client";

import {
  Banknote,
  CalendarDays,
  CheckCircle2,
  FilePlus2,
  LockKeyhole,
  Smartphone,
  UserRound,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { Feedback } from "@/components/ui/feedback";
import { Modal } from "@/components/ui/modal";
import { ModuleHeader } from "@/components/ui/module-header";
import {
  activateLease,
  closeLease,
  createLease,
  listHouses,
  listLeases,
  listTenants,
} from "@/lib/api-client";
import { formatDate, formatMoney } from "@/lib/format";
import type {
  CreateLeasePayload,
  House as HouseType,
  Lease,
  Tenant,
} from "@/types/domain";

const DEFAULT_FORM: CreateLeasePayload = {
  house_id: "",
  tenant_id: "",
  start_date: "",
  end_date: null,
  monthly_rent: "",
  monthly_charges: "0",
  due_day: 5,
  security_deposit: "0",
  rent_advance: "0",
  accepts_mobile_money: true,
  accepts_cash: true,
};

const statusStyle: Record<Lease["status"], string> = {
  ACTIVE: "status-paid",
  DRAFT: "status-partial",
  ENDED: "bg-zinc-100 text-zinc-700",
  CANCELLED: "bg-red-50 text-red-700",
};

export function LeaseWorkspace() {
  const [leases, setLeases] = useState<Lease[]>([]);
  const [houses, setHouses] = useState<HouseType[]>([]);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [filter, setFilter] = useState<"ALL" | Lease["status"]>("ALL");
  const [form, setForm] = useState<CreateLeasePayload>(DEFAULT_FORM);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [actingId, setActingId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([listLeases(), listHouses(), listTenants()])
      .then(([leaseData, houseData, tenantData]) => {
        setLeases(leaseData);
        setHouses(houseData);
        setTenants(tenantData);
      })
      .catch((caughtError) =>
        setError(caughtError instanceof Error ? caughtError.message : "Chargement impossible."),
      );
  }, []);

  const housesById = useMemo(
    () => new Map(houses.map((house) => [house.id, house])),
    [houses],
  );
  const availableTenants = tenants.filter(
    (tenant) => !form.house_id || tenant.house_id === form.house_id,
  );
  const filteredLeases = leases.filter((lease) => filter === "ALL" || lease.status === filter);

  function updateForm<K extends keyof CreateLeasePayload>(
    field: K,
    value: CreateLeasePayload[K],
  ) {
    setForm((current) => ({
      ...current,
      [field]: value,
      ...(field === "house_id" ? { tenant_id: "" } : {}),
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.accepts_cash && !form.accepts_mobile_money) {
      setError("Sélectionnez au moins un moyen de paiement accepté.");
      return;
    }
    if (!tenants.some((item) => item.id === form.tenant_id)) {
      setError("Sélectionnez un locataire rattaché à ce bien.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const lease = await createLease(form);
      setLeases((current) => [lease, ...current]);
      setForm(DEFAULT_FORM);
      setOpen(false);
      setFeedback("Bail créé en brouillon. Vérifiez-le avant de l’activer.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Création impossible.");
    } finally {
      setSaving(false);
    }
  }

  async function changeStatus(lease: Lease, action: "activate" | "close") {
    if (
      action === "close" &&
      !window.confirm("Clôturer ce bail et rendre le bien vacant ?")
    ) {
      return;
    }
    setActingId(lease.id);
    setError(null);
    try {
      const updated =
        action === "activate"
          ? await activateLease(lease.id)
          : await closeLease(lease.id);
      setLeases((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setFeedback(action === "activate" ? "Bail activé et bien occupé." : "Bail clôturé et bien libéré.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Action impossible.");
    } finally {
      setActingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <ModuleHeader
        action={
          <button className="primary-button w-fit" onClick={() => setOpen(true)} type="button">
            <FilePlus2 aria-hidden="true" size={18} />
            Nouveau bail
          </button>
        }
        description="Le bail relie un bien, un locataire et les conditions financières. Il commence en brouillon, puis son activation occupe le bien."
        eyebrow="Contrats"
        title="Baux"
      />
      <Feedback message={feedback} />
      <Feedback message={error} tone="error" />

      <section className="flex flex-wrap gap-2" aria-label="Filtrer les baux">
        {(["ALL", "ACTIVE", "DRAFT", "ENDED"] as const).map((item) => (
          <button
            className={`min-h-10 rounded-xl px-4 text-sm font-bold ${
              filter === item ? "bg-brand text-white" : "border border-line bg-white text-muted"
            }`}
            key={item}
            onClick={() => setFilter(item)}
            type="button"
          >
            {item === "ALL"
              ? "Tous"
              : item === "ACTIVE"
                ? "Actifs"
                : item === "DRAFT"
                  ? "Brouillons"
                  : "Terminés"}
          </button>
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
        {filteredLeases.map((lease) => {
          const house = housesById.get(lease.house_id);
          return (
            <article className="panel overflow-hidden" key={lease.id}>
              <div className="flex items-start justify-between gap-3 border-b border-line p-5">
                <div>
                  <span className={`status-pill ${statusStyle[lease.status]}`}>
                    {lease.status_label}
                  </span>
                  <h2 className="mt-3 text-lg font-bold text-ink">
                    {house?.name ?? "Bien"}
                  </h2>
                  <p className="mt-1 flex items-center gap-2 text-sm text-muted">
                    <UserRound aria-hidden="true" size={16} />
                    {lease.tenant.full_name}
                  </p>
                </div>
                <span className="grid size-10 place-items-center rounded-xl bg-brand-soft text-brand">
                  <FilePlus2 aria-hidden="true" size={20} />
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4 p-5 text-sm">
                <div>
                  <p className="text-muted">Loyer + charges</p>
                  <p className="mt-1 font-bold text-ink">
                    {formatMoney(Number(lease.monthly_rent) + Number(lease.monthly_charges))}
                  </p>
                </div>
                <div>
                  <p className="text-muted">Échéance</p>
                  <p className="mt-1 font-bold text-ink">Le {lease.due_day} du mois</p>
                </div>
                <div>
                  <p className="text-muted">Début</p>
                  <p className="mt-1 font-bold text-ink">{formatDate(lease.start_date)}</p>
                </div>
                <div>
                  <p className="text-muted">Fin</p>
                  <p className="mt-1 font-bold text-ink">
                    {lease.end_date ? formatDate(lease.end_date) : "Sans date"}
                  </p>
                </div>
              </div>
              {(lease.status === "DRAFT" || lease.status === "ACTIVE") && (
                <div className="border-t border-line px-5 py-4">
                  <button
                    className={lease.status === "DRAFT" ? "primary-button w-full" : "secondary-button w-full"}
                    disabled={actingId === lease.id}
                    onClick={() => changeStatus(lease, lease.status === "DRAFT" ? "activate" : "close")}
                    type="button"
                  >
                    {lease.status === "DRAFT" ? (
                      <CheckCircle2 aria-hidden="true" size={18} />
                    ) : (
                      <LockKeyhole aria-hidden="true" size={18} />
                    )}
                    {actingId === lease.id
                      ? "Traitement…"
                      : lease.status === "DRAFT"
                        ? "Activer le bail"
                        : "Clôturer le bail"}
                  </button>
                </div>
              )}
            </article>
          );
        })}
        {!filteredLeases.length ? (
          <div className="panel px-5 py-16 text-center lg:col-span-2 2xl:col-span-3">
            <p className="font-bold text-ink">
              {leases.length ? "Aucun bail avec ce statut" : "Aucun bail enregistré"}
            </p>
            <p className="mt-1 text-sm text-muted">
              {leases.length
                ? "Choisissez un autre filtre."
                : "Créez un bail après avoir ajouté un bien et son locataire."}
            </p>
          </div>
        ) : null}
      </section>

      <Modal
        description="Le bail sera enregistré en brouillon. Son activation sera une action séparée."
        kicker="Contrat de location"
        onClose={() => setOpen(false)}
        open={open}
        size="xl"
        title="Créer un bail"
      >
        <form className="p-5 sm:p-6" onSubmit={handleSubmit}>
          <div className="grid gap-5 sm:grid-cols-2">
            <label>
              <span className="form-label">Bien *</span>
              <select
                className="form-input"
                onChange={(event) => updateForm("house_id", event.target.value)}
                required
                value={form.house_id}
              >
                <option value="">Sélectionner</option>
                {houses.map((house) => (
                  <option key={house.id} value={house.id}>
                    {house.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="form-label">Locataire *</span>
              <select
                className="form-input"
                disabled={!form.house_id}
                onChange={(event) => updateForm("tenant_id", event.target.value)}
                required
                value={form.tenant_id}
              >
                <option value="">Sélectionner</option>
                {availableTenants.map((tenant) => (
                  <option key={tenant.id} value={tenant.id}>
                    {tenant.full_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="form-label">Date de début *</span>
              <input
                className="form-input"
                onChange={(event) => updateForm("start_date", event.target.value)}
                required
                type="date"
                value={form.start_date}
              />
            </label>
            <label>
              <span className="form-label">Date de fin</span>
              <input
                className="form-input"
                min={form.start_date}
                onChange={(event) => updateForm("end_date", event.target.value || null)}
                type="date"
                value={form.end_date ?? ""}
              />
            </label>
            <label>
              <span className="form-label">Loyer mensuel *</span>
              <div className="relative">
                <Banknote className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted" size={17} />
                <input
                  className="form-input pl-10"
                  min="1"
                  onChange={(event) => updateForm("monthly_rent", event.target.value)}
                  placeholder="200000"
                  required
                  type="number"
                  value={form.monthly_rent}
                />
              </div>
            </label>
            <label>
              <span className="form-label">Charges mensuelles</span>
              <input
                className="form-input"
                min="0"
                onChange={(event) => updateForm("monthly_charges", event.target.value)}
                type="number"
                value={form.monthly_charges}
              />
            </label>
            <label>
              <span className="form-label">Jour limite *</span>
              <div className="relative">
                <CalendarDays className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted" size={17} />
                <input
                  className="form-input pl-10"
                  max="28"
                  min="1"
                  onChange={(event) => updateForm("due_day", Number(event.target.value))}
                  required
                  type="number"
                  value={form.due_day}
                />
              </div>
            </label>
            <label>
              <span className="form-label">Caution</span>
              <input
                className="form-input"
                min="0"
                onChange={(event) => updateForm("security_deposit", event.target.value)}
                type="number"
                value={form.security_deposit}
              />
            </label>
            <label>
              <span className="form-label">Avance sur loyer</span>
              <input
                className="form-input"
                min="0"
                onChange={(event) => updateForm("rent_advance", event.target.value)}
                type="number"
                value={form.rent_advance}
              />
            </label>
            <fieldset className="sm:col-span-2">
              <legend className="form-label">Moyens de paiement acceptés *</legend>
              <div className="flex flex-wrap gap-3">
                <label className="flex min-h-11 items-center gap-3 rounded-xl border border-line px-4 text-sm font-semibold text-ink">
                  <input
                    checked={form.accepts_mobile_money}
                    onChange={(event) => updateForm("accepts_mobile_money", event.target.checked)}
                    type="checkbox"
                  />
                  <Smartphone aria-hidden="true" size={17} /> Mobile Money
                </label>
                <label className="flex min-h-11 items-center gap-3 rounded-xl border border-line px-4 text-sm font-semibold text-ink">
                  <input
                    checked={form.accepts_cash}
                    onChange={(event) => updateForm("accepts_cash", event.target.checked)}
                    type="checkbox"
                  />
                  <Banknote aria-hidden="true" size={17} /> Espèces
                </label>
              </div>
            </fieldset>
          </div>
          <Feedback message={error} tone="error" />
          <div className="mt-7 flex flex-col-reverse gap-3 border-t border-line pt-5 sm:flex-row sm:justify-end">
            <button className="secondary-button" onClick={() => setOpen(false)} type="button">Annuler</button>
            <button className="primary-button" disabled={saving} type="submit">
              <FilePlus2 aria-hidden="true" size={18} />
              {saving ? "Enregistrement…" : "Créer le brouillon"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
