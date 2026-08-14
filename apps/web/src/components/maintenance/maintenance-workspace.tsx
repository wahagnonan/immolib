"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  House as HouseIcon,
  LoaderCircle,
  MessageSquare,
  Plus,
  RefreshCw,
  ShieldAlert,
  Wrench,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { Feedback } from "@/components/ui/feedback";
import { Modal } from "@/components/ui/modal";
import { ModuleHeader } from "@/components/ui/module-header";
import {
  commentOnMaintenanceIncident,
  createMaintenanceIncident,
  listHouses,
  listLeases,
  listMaintenanceIncidents,
  setMaintenanceIncidentStatus,
} from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import type {
  CreateMaintenanceIncidentPayload,
  House,
  Lease,
  MaintenanceCategory,
  MaintenanceIncident,
  MaintenancePriority,
  MaintenanceStatus,
} from "@/types/domain";

const categories: Array<{ value: MaintenanceCategory; label: string }> = [
  { value: "PLUMBING", label: "Plomberie" },
  { value: "ELECTRICITY", label: "Électricité" },
  { value: "SECURITY", label: "Sécurité" },
  { value: "ROOF", label: "Toiture" },
  { value: "STRUCTURE", label: "Structure" },
  { value: "EQUIPMENT", label: "Équipement" },
  { value: "OTHER", label: "Autre" },
];

const priorities: Array<{ value: MaintenancePriority; label: string }> = [
  { value: "LOW", label: "Faible" },
  { value: "NORMAL", label: "Normale" },
  { value: "HIGH", label: "Élevée" },
  { value: "URGENT", label: "Urgente" },
];

const statusStyle: Record<MaintenanceStatus, string> = {
  REPORTED: "status-partial",
  ACKNOWLEDGED: "bg-sky-soft text-sky-dark",
  IN_PROGRESS: "bg-sky-soft text-sky-dark",
  RESOLVED: "status-paid",
  CLOSED: "status-paid",
  CANCELLED: "bg-zinc-100 text-zinc-700",
};

const priorityStyle: Record<MaintenancePriority, string> = {
  LOW: "bg-zinc-100 text-zinc-700",
  NORMAL: "bg-sky-soft text-sky-dark",
  HIGH: "status-partial",
  URGENT: "status-late",
};

const transitions: Partial<
  Record<MaintenanceStatus, Array<{ status: MaintenanceStatus; label: string }>>
> = {
  REPORTED: [
    { status: "ACKNOWLEDGED", label: "Prendre en compte" },
    { status: "CANCELLED", label: "Annuler" },
  ],
  ACKNOWLEDGED: [
    { status: "IN_PROGRESS", label: "Démarrer l’intervention" },
    { status: "CANCELLED", label: "Annuler" },
  ],
  IN_PROGRESS: [
    { status: "RESOLVED", label: "Marquer comme résolu" },
    { status: "CANCELLED", label: "Annuler" },
  ],
  RESOLVED: [{ status: "IN_PROGRESS", label: "Reprendre l’intervention" }],
};

const emptyForm: CreateMaintenanceIncidentPayload = {
  lease_id: "",
  title: "",
  description: "",
  category: "OTHER",
  priority: "NORMAL",
};

function replaceIncident(
  incidents: MaintenanceIncident[],
  updated: MaintenanceIncident,
) {
  return incidents.map((incident) =>
    incident.id === updated.id ? updated : incident,
  );
}

export function MaintenanceWorkspace() {
  const [incidents, setIncidents] = useState<MaintenanceIncident[]>([]);
  const [leases, setLeases] = useState<Lease[]>([]);
  const [houses, setHouses] = useState<House[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<CreateMaintenanceIncidentPayload>(emptyForm);
  const [comment, setComment] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [incidentData, leaseData, houseData] = await Promise.all([
        listMaintenanceIncidents(),
        listLeases(),
        listHouses(),
      ]);
      setIncidents(incidentData);
      setLeases(leaseData);
      setHouses(houseData);
      setSelectedId((current) => current ?? incidentData[0]?.id ?? null);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible de charger les incidents.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([
      listMaintenanceIncidents(),
      listLeases(),
      listHouses(),
    ])
      .then(([incidentData, leaseData, houseData]) => {
        if (!active) return;
        setIncidents(incidentData);
        setLeases(leaseData);
        setHouses(houseData);
        setSelectedId(incidentData[0]?.id ?? null);
      })
      .catch((caughtError) => {
        if (!active) return;
        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "Impossible de charger les incidents.",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const selected = incidents.find((incident) => incident.id === selectedId);
  const activeLeases = leases.filter((lease) => lease.status === "ACTIVE");
  const housesById = useMemo(
    () => new Map(houses.map((house) => [house.id, house])),
    [houses],
  );
  const openCount = incidents.filter(
    (incident) => !["CLOSED", "CANCELLED"].includes(incident.status),
  ).length;
  const urgentCount = incidents.filter(
    (incident) =>
      incident.priority === "URGENT" &&
      !["CLOSED", "CANCELLED"].includes(incident.status),
  ).length;

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const created = await createMaintenanceIncident(form);
      setIncidents((current) => [created, ...current]);
      setSelectedId(created.id);
      setForm(emptyForm);
      setCreateOpen(false);
      setFeedback("Incident enregistré et ajouté au suivi.");
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible d’enregistrer l’incident.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleStatus(target: MaintenanceStatus) {
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await setMaintenanceIncidentStatus(
        selected.id,
        target,
        statusMessage.trim(),
      );
      setIncidents((current) => replaceIncident(current, updated));
      setStatusMessage("");
      setFeedback("Le statut de l’incident a été mis à jour.");
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Mise à jour impossible.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !comment.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await commentOnMaintenanceIncident(selected.id, comment.trim());
      setIncidents((current) => replaceIncident(current, updated));
      setComment("");
      setFeedback("Commentaire ajouté à l’historique.");
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible d’ajouter le commentaire.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm font-semibold text-muted">
        <LoaderCircle aria-hidden="true" className="animate-spin" size={18} />
        Chargement des incidents…
      </p>
    );
  }

  return (
    <div className="space-y-7">
      <ModuleHeader
        action={
          <button className="primary-button" onClick={() => setCreateOpen(true)}>
            <Plus aria-hidden="true" size={18} />
            Signaler un incident
          </button>
        }
        description="Suivez les problèmes du bien depuis leur signalement jusqu’à la confirmation du locataire."
        eyebrow="Entretien des biens"
        title="Incidents et maintenance"
      />

      <Feedback message={feedback} />
      <Feedback message={error} tone="error" />

      <section className="grid gap-4 sm:grid-cols-3">
        <article className="metric-card">
          <Wrench className="mb-5 text-ink" size={22} />
          <p className="metric-label">Incidents ouverts</p>
          <p className="metric-value">{openCount}</p>
        </article>
        <article className="metric-card">
          <ShieldAlert className="mb-5 text-red-700" size={23} />
          <p className="metric-label">Urgences à traiter</p>
          <p className="metric-value">{urgentCount}</p>
        </article>
        <article className="metric-card">
          <CheckCircle2 className="mb-5 text-ink" size={22} />
          <p className="metric-label">Clôturés par le locataire</p>
          <p className="metric-value">
            {incidents.filter((incident) => incident.status === "CLOSED").length}
          </p>
        </article>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(420px,1.1fr)]">
        <div className="panel overflow-hidden">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">File de suivi</p>
              <h2 className="section-title">{incidents.length} incident(s)</h2>
            </div>
            <button
              aria-label="Actualiser"
              className="secondary-button"
              disabled={loading}
              onClick={() => void load()}
              type="button"
            >
              <RefreshCw aria-hidden="true" className={loading ? "animate-spin" : ""} size={17} />
            </button>
          </div>
          <div className="divide-y divide-line">
            {incidents.map((incident) => (
              <button
                className={`w-full p-5 text-left transition-colors hover:bg-canvas ${
                  selectedId === incident.id ? "bg-brand-soft/45" : ""
                }`}
                key={incident.id}
                onClick={() => setSelectedId(incident.id)}
                type="button"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`status-pill ${statusStyle[incident.status]}`}>
                    {incident.status_label}
                  </span>
                  <span
                    className={`status-pill ${priorityStyle[incident.priority]}`}
                  >
                    {incident.priority_label}
                  </span>
                </div>
                <h3 className="mt-3 font-bold text-ink">{incident.title}</h3>
                <p className="mt-1 text-sm text-muted">
                  {incident.house_name} · {incident.tenant_name}
                </p>
                <p className="mt-3 flex items-center gap-1.5 text-xs text-muted">
                  <Clock3 aria-hidden="true" size={14} />
                  Mis à jour {formatDateTime(incident.updated_at)}
                </p>
              </button>
            ))}
            {!incidents.length ? (
              <p className="p-10 text-center text-sm text-muted">
                Aucun incident signalé.
              </p>
            ) : null}
          </div>
        </div>

        <div className="panel h-fit overflow-hidden">
          {selected ? (
            <>
              <div className="panel-heading">
                <div>
                  <p className="section-kicker">{selected.category_label}</p>
                  <h2 className="section-title">{selected.title}</h2>
                </div>
                <span className={`status-pill ${statusStyle[selected.status]}`}>
                  {selected.status_label}
                </span>
              </div>
              <div className="space-y-6 p-5 sm:p-6">
                <div>
                  <p className="flex items-center gap-2 text-sm font-bold text-ink">
                    <HouseIcon aria-hidden="true" className="text-brand" size={18} />
                    {selected.house_name}
                  </p>
                  <p className="mt-1 text-sm text-muted">
                    {selected.tenant_name} · {selected.house_address}
                  </p>
                  <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-ink">
                    {selected.description}
                  </p>
                </div>

                {transitions[selected.status]?.length ? (
                  <div className="rounded-2xl border border-line bg-canvas p-4">
                    <label>
                      <span className="form-label">
                        Note accompagnant le changement
                      </span>
                      <textarea
                        className="form-input min-h-20 resize-y bg-white"
                        maxLength={2000}
                        onChange={(event) => setStatusMessage(event.target.value)}
                        placeholder="Ex. rendez-vous prévu avec l’artisan…"
                        value={statusMessage}
                      />
                    </label>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {transitions[selected.status]?.map((transition) => (
                        <button
                          className={
                            transition.status === "CANCELLED"
                              ? "secondary-button text-red-700"
                              : "primary-button"
                          }
                          disabled={saving}
                          key={transition.status}
                          onClick={() => void handleStatus(transition.status)}
                          type="button"
                        >
                          {transition.label}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}

                <div>
                  <p className="section-kicker">Historique partagé</p>
                  <div className="mt-3 space-y-3">
                    {selected.events.map((item) => (
                      <article
                        className="rounded-xl border border-line p-4"
                        key={item.id}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-bold text-ink">
                            {item.event_label}
                          </p>
                          <time className="text-xs text-muted">
                            {formatDateTime(item.created_at)}
                          </time>
                        </div>
                        <p className="mt-1 text-xs font-semibold text-brand">
                          {item.actor_role_label} · {item.actor_name}
                        </p>
                        {item.from_status && item.to_status ? (
                          <p className="mt-2 text-xs text-muted">
                            {item.from_status_label} → {item.to_status_label}
                          </p>
                        ) : null}
                        {item.message ? (
                          <p className="mt-2 text-sm leading-6 text-muted">
                            {item.message}
                          </p>
                        ) : null}
                      </article>
                    ))}
                  </div>
                </div>

                {!["CLOSED", "CANCELLED"].includes(selected.status) ? (
                  <form className="border-t border-line pt-5" onSubmit={handleComment}>
                    <label>
                      <span className="form-label">Ajouter un commentaire</span>
                      <textarea
                        className="form-input min-h-24 resize-y"
                        maxLength={2000}
                        onChange={(event) => setComment(event.target.value)}
                        placeholder="Informez le locataire de l’avancement…"
                        required
                        value={comment}
                      />
                    </label>
                    <button
                      className="primary-button mt-3"
                      disabled={saving || !comment.trim()}
                      type="submit"
                    >
                      <MessageSquare aria-hidden="true" size={17} />
                      Publier
                    </button>
                  </form>
                ) : null}
              </div>
            </>
          ) : (
            <p className="p-10 text-center text-sm text-muted">
              Sélectionnez un incident pour afficher son historique.
            </p>
          )}
        </div>
      </section>

      <Modal
        description="Le locataire verra le signalement et toutes ses mises à jour dans son espace."
        kicker="Nouveau signalement"
        onClose={() => setCreateOpen(false)}
        open={createOpen}
        title="Enregistrer un incident"
      >
        <form className="space-y-4 p-5 sm:p-6" onSubmit={handleCreate}>
          <label>
            <span className="form-label">Bail concerné *</span>
            <select
              className="form-input"
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  lease_id: event.target.value,
                }))
              }
              required
              value={form.lease_id}
            >
              <option value="">Sélectionner un bien et un locataire</option>
              {activeLeases.map((lease) => (
                <option key={lease.id} value={lease.id}>
                  {housesById.get(lease.house_id)?.name ?? "Bien"} —{" "}
                  {lease.tenant.full_name}
                </option>
              ))}
            </select>
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label>
              <span className="form-label">Catégorie *</span>
              <select
                className="form-input"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    category: event.target.value as MaintenanceCategory,
                  }))
                }
                value={form.category}
              >
                {categories.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="form-label">Priorité *</span>
              <select
                className="form-input"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    priority: event.target.value as MaintenancePriority,
                  }))
                }
                value={form.priority}
              >
                {priorities.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label>
            <span className="form-label">Titre *</span>
            <input
              className="form-input"
              maxLength={160}
              onChange={(event) =>
                setForm((current) => ({ ...current, title: event.target.value }))
              }
              placeholder="Ex. fuite sous l’évier"
              required
              value={form.title}
            />
          </label>
          <label>
            <span className="form-label">Description *</span>
            <textarea
              className="form-input min-h-32 resize-y"
              maxLength={5000}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  description: event.target.value,
                }))
              }
              placeholder="Décrivez le problème et son impact."
              required
              value={form.description}
            />
          </label>
          {!activeLeases.length ? (
            <p className="flex gap-2 rounded-xl bg-amber-soft p-3 text-sm text-amber-dark">
              <AlertTriangle aria-hidden="true" className="shrink-0" size={18} />
              Activez d’abord un bail pour rattacher l’incident à une location.
            </p>
          ) : null}
          <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
            <button
              className="secondary-button"
              onClick={() => setCreateOpen(false)}
              type="button"
            >
              Annuler
            </button>
            <button
              className="primary-button"
              disabled={
                saving ||
                !form.lease_id ||
                !form.title.trim() ||
                !form.description.trim()
              }
              type="submit"
            >
              {saving ? (
                <LoaderCircle className="animate-spin" size={17} />
              ) : (
                <Wrench size={17} />
              )}
              Enregistrer
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
