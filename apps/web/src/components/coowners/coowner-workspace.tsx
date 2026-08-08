"use client";

import {
  Clock3,
  Eye,
  House,
  KeyRound,
  Mail,
  Pencil,
  Phone,
  Plus,
  ShieldCheck,
  Trash2,
  UserRoundCheck,
  UserRoundPlus,
  UsersRound,
  XCircle,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { Feedback } from "@/components/ui/feedback";
import { Modal } from "@/components/ui/modal";
import { ModuleHeader } from "@/components/ui/module-header";
import { PhoneField } from "@/components/ui/phone-field";
import {
  inviteCoOwner,
  listCoOwnerInvitations,
  listCoOwners,
  listHouses,
  removeCoOwner,
  revokeCoOwnerInvitation,
  updateCoOwner,
} from "@/lib/api-client";
import { formatDate } from "@/lib/format";
import type {
  CoOwner,
  CoOwnerInvitation,
  House as HouseType,
  InviteCoOwnerPayload,
  UpdateCoOwnerPayload,
} from "@/types/domain";

const EMPTY_INVITATION: InviteCoOwnerPayload = {
  house_id: "",
  phone: "",
  email: "",
  ownership_percentage: null,
  access_level: "OBSERVER",
};

const invitationStatusStyle: Record<CoOwnerInvitation["status"], string> = {
  PENDING: "status-partial",
  ACCEPTED: "status-paid",
  REVOKED: "bg-red-50 text-red-700",
  EXPIRED: "status-vacant",
};

function displayPercentage(value: string | null) {
  return value === null ? "Non renseignée" : `${Number(value)} %`;
}

export function CoOwnerWorkspace() {
  const [houses, setHouses] = useState<HouseType[]>([]);
  const [coOwners, setCoOwners] = useState<CoOwner[]>([]);
  const [invitations, setInvitations] = useState<CoOwnerInvitation[]>([]);
  const { user: currentUser } = useAuth();
  const [houseFilter, setHouseFilter] = useState("ALL");
  const [invitationForm, setInvitationForm] =
    useState<InviteCoOwnerPayload>(EMPTY_INVITATION);
  const [editing, setEditing] = useState<CoOwner | null>(null);
  const [editForm, setEditForm] = useState<UpdateCoOwnerPayload>({});
  const [inviteOpen, setInviteOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      listHouses(),
      listCoOwners(),
      listCoOwnerInvitations(),
    ])
      .then(([houseData, coOwnerData, invitationData]) => {
        setHouses(houseData);
        setCoOwners(coOwnerData);
        setInvitations(invitationData);
      })
      .catch((caughtError) =>
        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "Impossible de charger les copropriétaires.",
        ),
      );
  }, []);

  const managedHouses = useMemo(
    () =>
      houses.filter((house) =>
        house.ownerships.some(
          (ownership) =>
            ownership.role === "PRIMARY" && ownership.user.id === currentUser?.id,
        ),
      ),
    [currentUser?.id, houses],
  );

  const displayedHouses = useMemo(
    () =>
      houseFilter === "ALL"
        ? managedHouses
        : managedHouses.filter((house) => house.id === houseFilter),
    [houseFilter, managedHouses],
  );

  const pendingCount = invitations.filter(
    (invitation) => invitation.status === "PENDING",
  ).length;
  const distinctCoOwnerCount = new Set(coOwners.map((coOwner) => coOwner.user.id)).size;

  function openInvitation(houseId?: string) {
    setInvitationForm({
      ...EMPTY_INVITATION,
      house_id:
        houseId ??
        (houseFilter !== "ALL" ? houseFilter : managedHouses.at(0)?.id ?? ""),
    });
    setError(null);
    setInviteOpen(true);
  }

  async function refreshOwnershipData() {
    const [houseData, coOwnerData, invitationData] = await Promise.all([
      listHouses(),
      listCoOwners(),
      listCoOwnerInvitations(),
    ]);
    setHouses(houseData);
    setCoOwners(coOwnerData);
    setInvitations(invitationData);
  }

  async function handleInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = {
        ...invitationForm,
        phone: invitationForm.phone.trim(),
        email: invitationForm.email?.trim(),
        ownership_percentage: invitationForm.ownership_percentage || null,
      };
      const invitation = await inviteCoOwner(payload);
      await refreshOwnershipData();

      setInviteOpen(false);
      setFeedback(
        invitation.status === "ACCEPTED"
          ? "Le compte existait déjà : le copropriétaire a été ajouté immédiatement."
          : "Invitation créée. La quote-part est réservée jusqu’à son acceptation.",
      );
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Invitation impossible.");
    } finally {
      setSaving(false);
    }
  }

  function openEdit(coOwner: CoOwner) {
    setEditing(coOwner);
    setEditForm({
      ownership_percentage: coOwner.ownership_percentage,
      access_level: coOwner.access_level,
    });
    setError(null);
  }

  async function handleEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    setSaving(true);
    setError(null);
    try {
      const payload: UpdateCoOwnerPayload = {
        ...editForm,
        ownership_percentage: editForm.ownership_percentage || null,
      };
      await updateCoOwner(editing.id, payload);
      await refreshOwnershipData();
      setEditing(null);
      setFeedback("Les droits et la quote-part du copropriétaire ont été mis à jour.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Modification impossible.");
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove(coOwner: CoOwner) {
    if (
      !window.confirm(
        `Retirer ${coOwner.user.full_name || coOwner.user.phone} de ${coOwner.house_name} ?`,
      )
    ) {
      return;
    }
    setError(null);
    try {
      await removeCoOwner(coOwner.id);
      await refreshOwnershipData();
      setFeedback("Le copropriétaire a été retiré de la maison.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Retrait impossible.");
    }
  }

  async function handleRevoke(invitation: CoOwnerInvitation) {
    if (!window.confirm(`Révoquer l’invitation envoyée à ${invitation.phone} ?`)) return;
    setError(null);
    try {
      await revokeCoOwnerInvitation(invitation.id);
      await refreshOwnershipData();
      setFeedback("L’invitation a été révoquée et sa quote-part a été libérée.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Révocation impossible.");
    }
  }

  return (
    <div className="space-y-6">
      <ModuleHeader
        action={
          <button
            className="primary-button w-fit"
            disabled={!managedHouses.length}
            onClick={() => openInvitation()}
            type="button"
          >
            <UserRoundPlus aria-hidden="true" size={18} />
            Inviter un copropriétaire
          </button>
        }
        description="Invitez une personne par téléphone, réservez sa quote-part et choisissez si elle peut agir ou seulement consulter. Seul le propriétaire principal gère ces droits."
        eyebrow="Propriété et accès"
        title="Copropriétaires"
      />
      <Feedback message={feedback} />
      <Feedback message={error} tone="error" />

      <div className="flex items-start gap-3 rounded-[10px] border border-line bg-white px-4 py-3 text-sm leading-6 text-muted">
        <ShieldCheck aria-hidden="true" className="mt-0.5 shrink-0" size={19} />
        <p>
          <strong>Deux réglages séparés.</strong> La quote-part décrit ce que la
          personne possède. Le niveau Actif ou Observateur décrit uniquement ce
          qu’elle peut faire dans ImmoLib.
        </p>
      </div>

      <section className="grid gap-3 sm:grid-cols-3">
        <div className="panel p-4">
          <p className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Maisons gérées</p>
          <p className="mt-1 text-2xl font-bold text-ink">{managedHouses.length}</p>
        </div>
        <div className="panel p-4">
          <p className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Copropriétaires</p>
          <p className="mt-1 text-2xl font-semibold text-ink">{distinctCoOwnerCount}</p>
        </div>
        <div className="panel p-4">
          <p className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Invitations en attente</p>
          <p className="mt-1 text-2xl font-semibold text-ink">{pendingCount}</p>
        </div>
      </section>

      <section className="panel p-4 sm:p-5">
        <label className="block sm:max-w-sm">
          <span className="form-label">Afficher une maison</span>
          <select
            className="form-input"
            onChange={(event) => setHouseFilter(event.target.value)}
            value={houseFilter}
          >
            <option value="ALL">Toutes les maisons</option>
            {managedHouses.map((house) => (
              <option key={house.id} value={house.id}>{house.name}</option>
            ))}
          </select>
        </label>
      </section>

      {displayedHouses.length ? (
        <section className="grid gap-5 xl:grid-cols-2">
          {displayedHouses.map((house) => {
            const primary = house.ownerships.find((item) => item.role === "PRIMARY");
            const houseCoOwners = coOwners.filter((item) => item.house_id === house.id);
            const houseInvitations = invitations.filter(
              (item) => item.house_id === house.id && item.status === "PENDING",
            );
            return (
              <article className="panel overflow-hidden" key={house.id}>
                <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
                  <div className="flex items-center gap-3">
                    <span className="grid size-10 place-items-center rounded-xl bg-brand-soft text-brand"><House aria-hidden="true" size={20} /></span>
                    <div><h2 className="font-bold text-ink">{house.name}</h2><p className="text-sm text-muted">{house.commune || house.city}</p></div>
                  </div>
                  <button className="secondary-button min-h-9 px-3 py-1.5" onClick={() => openInvitation(house.id)} type="button"><Plus aria-hidden="true" size={16} /> Inviter</button>
                </header>

                <div className="border-b border-line bg-canvas/45 px-5 py-3 text-xs font-bold uppercase tracking-[0.08em] text-muted">Propriétaire principal</div>
                {primary ? (
                  <div className="grid gap-3 px-5 py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                    <div className="flex min-w-0 items-center gap-3"><span className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-soft text-brand"><UserRoundCheck aria-hidden="true" size={17} /></span><div className="min-w-0"><p className="truncate font-bold text-ink">{primary.user.full_name || primary.user.phone}</p><p className="truncate text-xs text-muted">{primary.user.phone}</p></div></div>
                    <div className="sm:text-right"><p className="text-xs text-muted">Quote-part restante</p><p className="font-bold text-ink">{displayPercentage(primary.ownership_percentage)}</p></div>
                  </div>
                ) : null}

                <div className="border-y border-line bg-canvas/45 px-5 py-3 text-xs font-bold uppercase tracking-[0.08em] text-muted">Copropriétaires acceptés</div>
                {houseCoOwners.length ? (
                  <div className="divide-y divide-line">
                    {houseCoOwners.map((coOwner) => (
                      <div className="px-5 py-4" key={coOwner.id}>
                        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                          <div className="flex min-w-0 items-center gap-3"><span className="grid size-9 shrink-0 place-items-center rounded-full bg-canvas text-muted"><UsersRound aria-hidden="true" size={17} /></span><div className="min-w-0"><p className="truncate font-bold text-ink">{coOwner.user.full_name || coOwner.user.phone}</p><p className="truncate text-xs text-muted">{coOwner.user.phone}</p></div></div>
                          <div className="flex flex-wrap items-center gap-2"><span className="status-pill status-vacant">{displayPercentage(coOwner.ownership_percentage)}</span><span className={`status-pill ${coOwner.access_level === "ACTIVE" ? "status-paid" : "status-vacant"}`}>{coOwner.access_level === "ACTIVE" ? <KeyRound aria-hidden="true" className="mr-1" size={13} /> : <Eye aria-hidden="true" className="mr-1" size={13} />}{coOwner.access_level_label}</span></div>
                        </div>
                        <div className="mt-3 flex justify-end gap-2"><button aria-label={`Modifier ${coOwner.user.full_name}`} className="secondary-button min-h-9 px-3 py-1.5" onClick={() => openEdit(coOwner)} type="button"><Pencil aria-hidden="true" size={15} /> Modifier</button><button aria-label={`Retirer ${coOwner.user.full_name}`} className="grid size-9 place-items-center rounded-xl border border-red-200 text-red-700 hover:bg-red-50" onClick={() => handleRemove(coOwner)} title="Retirer" type="button"><Trash2 aria-hidden="true" size={16} /></button></div>
                      </div>
                    ))}
                  </div>
                ) : <p className="px-5 py-6 text-sm text-muted">Aucun copropriétaire accepté.</p>}

                {houseInvitations.length ? (
                  <><div className="border-y border-line bg-amber-soft/45 px-5 py-3 text-xs font-bold uppercase tracking-[0.08em] text-amber-dark">En attente d’un compte</div><div className="divide-y divide-line">{houseInvitations.map((invitation) => <div className="px-5 py-4" key={invitation.id}><div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start"><div><p className="flex items-center gap-2 font-bold text-ink"><Phone aria-hidden="true" size={15} />{invitation.phone}</p>{invitation.email ? <p className="mt-1 flex items-center gap-2 text-xs text-muted"><Mail aria-hidden="true" size={14} />{invitation.email}</p> : null}<p className="mt-2 flex items-center gap-2 text-xs text-muted"><Clock3 aria-hidden="true" size={14} />Expire le {formatDate(invitation.expires_at)}</p></div><div className="flex flex-wrap items-center gap-2"><span className="status-pill status-partial">{displayPercentage(invitation.ownership_percentage)}</span><button className="inline-flex min-h-9 items-center gap-1.5 rounded-xl px-2 text-xs font-bold text-red-700 hover:bg-red-50" onClick={() => handleRevoke(invitation)} type="button"><XCircle aria-hidden="true" size={15} /> Révoquer</button></div></div></div>)}</div></>
                ) : null}
              </article>
            );
          })}
        </section>
      ) : (
        <section className="panel px-5 py-16 text-center text-sm text-muted">Aucune maison dont vous êtes le propriétaire principal.</section>
      )}

      <section className="panel overflow-hidden">
        <div className="panel-heading"><div><p className="section-kicker">Traçabilité</p><h2 className="section-title">Historique des invitations</h2></div></div>
        {invitations.length ? (
          <div className="overflow-x-auto"><table className="data-table"><thead><tr><th>Destinataire</th><th>Maison</th><th>Quote-part</th><th>Statut</th><th>Créée le</th></tr></thead><tbody>{invitations.map((invitation) => <tr key={invitation.id}><td><p className="font-bold text-ink">{invitation.phone}</p><p className="text-xs">{invitation.email || "Sans email"}</p></td><td className="font-semibold text-ink">{invitation.house_name}</td><td>{displayPercentage(invitation.ownership_percentage)}</td><td><span className={`status-pill ${invitationStatusStyle[invitation.status]}`}>{invitation.status_label}</span></td><td>{formatDate(invitation.created_at)}</td></tr>)}</tbody></table></div>
        ) : <p className="px-5 py-12 text-center text-sm text-muted">Aucune invitation envoyée.</p>}
      </section>

      <Modal description="Si le numéro possède déjà un compte ImmoLib, l’ajout est immédiat. Sinon l’invitation reste en attente pendant 30 jours." kicker="Nouvelle invitation" onClose={() => setInviteOpen(false)} open={inviteOpen} title="Inviter un copropriétaire">
        <form className="p-5 sm:p-6" onSubmit={handleInvite}>
          <div className="grid gap-5 sm:grid-cols-2">
            <label className="sm:col-span-2"><span className="form-label">Maison *</span><select className="form-input" onChange={(event) => setInvitationForm((current) => ({ ...current, house_id: event.target.value }))} required value={invitationForm.house_id}><option value="">Sélectionner une maison</option>{managedHouses.map((house) => <option key={house.id} value={house.id}>{house.name} — {house.commune || house.city}</option>)}</select></label>
            <label><span className="form-label">Téléphone *</span><PhoneField onChange={(value) => setInvitationForm((current) => ({ ...current, phone: value }))} required value={invitationForm.phone} /></label>
            <label><span className="form-label">Email (facultatif)</span><input className="form-input" onChange={(event) => setInvitationForm((current) => ({ ...current, email: event.target.value }))} placeholder="nom@exemple.com" type="email" value={invitationForm.email ?? ""} /></label>
            <label><span className="form-label">Quote-part en %</span><input className="form-input" max="99.99" min="0.01" onChange={(event) => setInvitationForm((current) => ({ ...current, ownership_percentage: event.target.value || null }))} placeholder="Ex. 40" step="0.01" type="number" value={invitationForm.ownership_percentage ?? ""} /><span className="mt-1.5 block text-xs text-muted">Laissez vide si elle n’est pas encore connue.</span></label>
            <label><span className="form-label">Niveau d’accès *</span><select className="form-input" onChange={(event) => setInvitationForm((current) => ({ ...current, access_level: event.target.value as InviteCoOwnerPayload["access_level"] }))} value={invitationForm.access_level}><option value="OBSERVER">Observateur — consulter</option><option value="ACTIVE">Actif — agir</option></select><span className="mt-1.5 block text-xs text-muted">Ce choix ne modifie pas la quote-part.</span></label>
          </div>
          <div className="mt-6 flex flex-col-reverse gap-3 border-t border-line pt-5 sm:flex-row sm:justify-end"><button className="secondary-button" onClick={() => setInviteOpen(false)} type="button">Annuler</button><button className="primary-button" disabled={saving} type="submit"><UserRoundPlus aria-hidden="true" size={18} />{saving ? "Envoi…" : "Créer l’invitation"}</button></div>
        </form>
      </Modal>

      <Modal description="La quote-part et l’autorisation d’agir sont deux informations indépendantes." kicker={editing?.house_name} onClose={() => setEditing(null)} open={editing !== null} title="Modifier le copropriétaire">
        <form className="p-5 sm:p-6" onSubmit={handleEdit}>
          <div className="mb-5 rounded-xl bg-canvas p-4"><p className="font-bold text-ink">{editing?.user.full_name || editing?.user.phone}</p><p className="mt-1 text-sm text-muted">{editing?.user.phone}</p></div>
          <div className="grid gap-5 sm:grid-cols-2">
            <label><span className="form-label">Quote-part en %</span><input className="form-input" max="99.99" min="0.01" onChange={(event) => setEditForm((current) => ({ ...current, ownership_percentage: event.target.value || null }))} step="0.01" type="number" value={editForm.ownership_percentage ?? ""} /></label>
            <label><span className="form-label">Niveau d’accès</span><select className="form-input" onChange={(event) => setEditForm((current) => ({ ...current, access_level: event.target.value as UpdateCoOwnerPayload["access_level"] }))} value={editForm.access_level}><option value="OBSERVER">Observateur — consulter</option><option value="ACTIVE">Actif — agir</option></select></label>
          </div>
          <div className="mt-6 flex flex-col-reverse gap-3 border-t border-line pt-5 sm:flex-row sm:justify-end"><button className="secondary-button" onClick={() => setEditing(null)} type="button">Annuler</button><button className="primary-button" disabled={saving} type="submit"><Pencil aria-hidden="true" size={17} />{saving ? "Enregistrement…" : "Enregistrer"}</button></div>
        </form>
      </Modal>
    </div>
  );
}
