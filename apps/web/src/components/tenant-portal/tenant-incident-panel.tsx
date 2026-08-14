"use client";

import {
  CheckCircle2,
  Clock3,
  LoaderCircle,
  MessageSquare,
  Plus,
  RotateCcw,
  Wrench,
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { Feedback } from "@/components/ui/feedback";
import { Modal } from "@/components/ui/modal";
import {
  commentOnTenantPortalIncident,
  createTenantPortalIncident,
  listTenantPortalIncidents,
  respondToTenantPortalIncident,
} from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import type {
  CreateMaintenanceIncidentPayload,
  MaintenanceCategory,
  MaintenanceIncident,
  MaintenancePriority,
  MaintenanceStatus,
  TenantPortalLease,
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

export function TenantIncidentPanel({
  leases,
}: {
  leases: TenantPortalLease[];
}) {
  const [incidents, setIncidents] = useState<MaintenanceIncident[]>([]);
  const [selected, setSelected] = useState<MaintenanceIncident | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<CreateMaintenanceIncidentPayload>(emptyForm);
  const [comment, setComment] = useState("");
  const [reopenReason, setReopenReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listTenantPortalIncidents()
      .then((data) => {
        if (active) setIncidents(data);
      })
      .catch((caughtError) => {
        if (active) {
          setError(
            caughtError instanceof Error
              ? caughtError.message
              : "Impossible de charger les incidents.",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  function sync(updated: MaintenanceIncident) {
    setIncidents((current) => replaceIncident(current, updated));
    setSelected(updated);
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const created = await createTenantPortalIncident(form);
      setIncidents((current) => [created, ...current]);
      setForm(emptyForm);
      setCreateOpen(false);
      setFeedback("Votre signalement a été transmis au bailleur.");
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible de transmettre le signalement.",
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
      const updated = await commentOnTenantPortalIncident(
        selected.id,
        comment.trim(),
      );
      sync(updated);
      setComment("");
      setFeedback("Votre commentaire a été ajouté à l’historique.");
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

  async function handleResponse(action: "CLOSE" | "REOPEN") {
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await respondToTenantPortalIncident(
        selected.id,
        action,
        reopenReason.trim(),
      );
      sync(updated);
      setReopenReason("");
      setFeedback(
        action === "CLOSE"
          ? "L’incident est clôturé."
          : "Le bailleur a été notifié du problème persistant.",
      );
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible d’enregistrer votre réponse.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="scroll-mt-28" id="incidents">
      <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <p className="section-kicker">Maison et entretien</p>
          <h2 className="section-title">Signalements</h2>
          <p className="mt-1 text-sm text-muted">
            Problèmes signalés et suivi de leur résolution.
          </p>
        </div>
        <button
          className="primary-button w-fit"
          disabled={!leases.length}
          onClick={() => setCreateOpen(true)}
          type="button"
        >
          <Plus aria-hidden="true" size={17} />
          Signaler un problème
        </button>
      </div>
      <Feedback message={feedback} />
      <div className="mt-3">
        <Feedback message={error} tone="error" />
      </div>

      {loading ? (
        <p className="panel mt-4 flex items-center justify-center gap-2 p-10 text-sm font-semibold text-muted">
          <LoaderCircle className="animate-spin" size={18} />
          Chargement…
        </p>
      ) : incidents.length ? (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          {incidents.map((incident) => (
            <button
              className="panel p-5 text-left transition-colors hover:border-brand/30"
              key={incident.id}
              onClick={() => setSelected(incident)}
              type="button"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className={`status-pill ${statusStyle[incident.status]}`}>
                  {incident.status_label}
                </span>
                <span className="text-xs font-bold text-muted">
                  {incident.priority_label}
                </span>
              </div>
              <h3 className="mt-4 font-bold text-ink">{incident.title}</h3>
              <p className="mt-1 text-sm text-muted">
                {incident.house_name} · {incident.category_label}
              </p>
              <p className="mt-4 flex items-center gap-1.5 text-xs text-muted">
                <Clock3 aria-hidden="true" size={14} />
                {formatDateTime(incident.updated_at)}
              </p>
            </button>
          ))}
        </div>
      ) : (
        <div className="panel mt-4 p-8 text-center text-sm text-muted">
          Aucun signalement pour le moment.
        </div>
      )}

      <Modal
        description="Décrivez le problème. Le signalement sera horodaté et transmis au bailleur."
        kicker="Nouveau signalement"
        onClose={() => setCreateOpen(false)}
        open={createOpen}
        title="Signaler un problème"
      >
        <form className="space-y-4 p-5 sm:p-6" onSubmit={handleCreate}>
          <label>
            <span className="form-label">Maison concernée *</span>
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
              <option value="">Choisir la maison</option>
              {leases.map((lease) => (
                <option key={lease.id} value={lease.id}>
                  {lease.house.name}
                </option>
              ))}
            </select>
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label>
              <span className="form-label">Catégorie</span>
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
              <span className="form-label">Priorité</span>
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
              placeholder="Ex. fuite dans la cuisine"
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
              }              placeholder="Quand, où et quel impact ?"
              required
              value={form.description}
            />
          </label>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
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
              <Wrench aria-hidden="true" size={17} />
              Envoyer au bailleur
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        kicker={selected?.category_label}
        onClose={() => {
          setSelected(null);
          setComment("");
          setReopenReason("");
        }}
        open={Boolean(selected)}
        size="lg"
        title={selected?.title ?? "Incident"}
      >
        {selected ? (
          <div className="space-y-6 p-5 sm:p-6">
            <div>
              <span className={`status-pill ${statusStyle[selected.status]}`}>
                {selected.status_label}
              </span>
              <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-ink">
                {selected.description}
              </p>
            </div>

            {selected.status === "RESOLVED" ? (
              <div className="rounded-[14px] border border-line bg-canvas p-4">
                <p className="font-semibold text-ink">
                  Le bailleur indique que le problème est résolu.
                </p>
                <p className="mt-1 text-sm text-muted">
                  Confirmez la clôture ou expliquez pourquoi l’intervention doit
                  reprendre.
                </p>
                <textarea
                  className="form-input mt-4 min-h-20 resize-y"
                  maxLength={2000}
                  onChange={(event) => setReopenReason(event.target.value)}
                  placeholder="Motif obligatoire uniquement pour rouvrir…"
                  value={reopenReason}
                />
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    className="primary-button"
                    disabled={saving}
                    onClick={() => void handleResponse("CLOSE")}
                    type="button"
                  >
                    <CheckCircle2 size={17} />
                    Confirmer la résolution
                  </button>
                  <button
                    className="secondary-button"
                    disabled={saving || !reopenReason.trim()}
                    onClick={() => void handleResponse("REOPEN")}
                    type="button"
                  >
                    <RotateCcw size={17} />
                    Le problème persiste
                  </button>
                </div>
              </div>
            ) : null}

            <div>
              <p className="section-kicker">Historique partagé</p>
              <div className="mt-3 space-y-3">
                {selected.events.map((item) => (
                  <article className="rounded-xl border border-line p-4" key={item.id}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-bold text-ink">{item.event_label}</p>
                      <time className="text-xs text-muted">
                        {formatDateTime(item.created_at)}
                      </time>
                    </div>
                    <p className="mt-1 text-xs font-semibold text-brand">
                      {item.actor_role_label} · {item.actor_name}
                    </p>
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
                  <span className="form-label">Ajouter une précision</span>
                  <textarea
                    className="form-input min-h-24 resize-y"
                    maxLength={2000}
                    onChange={(event) => setComment(event.target.value)}
                    placeholder="Ajoutez une information utile au bailleur…"
                    required
                    value={comment}
                  />
                </label>
                <button
                  className="primary-button mt-3"
                  disabled={saving || !comment.trim()}
                  type="submit"
                >
                  <MessageSquare size={17} />
                  Publier
                </button>
              </form>
            ) : null}
          </div>
        ) : null}
      </Modal>
    </section>
  );
}
