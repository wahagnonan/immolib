"use client";

import {
  AtSign,
  House,
  MailPlus,
  Phone,
  Search,
  UserPlus,
  Users,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { TenantInvitationModal } from "@/components/tenants/tenant-invitation-modal";
import { Feedback } from "@/components/ui/feedback";
import { Modal } from "@/components/ui/modal";
import { ModuleHeader } from "@/components/ui/module-header";
import {
  createTenant,
  createTenantInvitation,
  listHouses,
  listTenantInvitations,
  listTenants,
} from "@/lib/api-client";
import type {
  CreateTenantPayload,
  House as HouseType,
  Tenant,
  TenantInvitation,
} from "@/types/domain";

const EMPTY_FORM: CreateTenantPayload = {
  house_id: "",
  full_name: "",
  phone: "",
  email: "",
};

const statusStyle: Record<Tenant["status"], string> = {
  ACTIVE: "status-paid",
  INVITED: "status-vacant",
  UNREGISTERED: "status-partial",
  BLOCKED: "bg-red-50 text-red-700",
};

export function TenantWorkspace() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [houses, setHouses] = useState<HouseType[]>([]);
  const [invitations, setInvitations] = useState<TenantInvitation[]>([]);
  const [query, setQuery] = useState("");
  const [houseFilter, setHouseFilter] = useState("ALL");
  const [form, setForm] = useState<CreateTenantPayload>(EMPTY_FORM);
  const [open, setOpen] = useState(false);
  const [invitedTenant, setInvitedTenant] = useState<Tenant | null>(null);
  const [activeInvitation, setActiveInvitation] =
    useState<TenantInvitation | null>(null);
  const [invitingTenantId, setInvitingTenantId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([listTenants(), listHouses(), listTenantInvitations()])
      .then(([tenantData, houseData, invitationData]) => {
        setTenants(tenantData);
        setHouses(houseData);
        setInvitations(invitationData);
      })
      .catch((caughtError) =>
        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "Impossible de charger les locataires.",
        ),
      );
  }, []);

  const housesById = useMemo(
    () => new Map(houses.map((house) => [house.id, house])),
    [houses],
  );

  const invitationsByTenant = useMemo(() => {
    const map = new Map<string, TenantInvitation>();
    invitations.forEach((invitation) => {
      if (!map.has(invitation.tenant_id)) {
        map.set(invitation.tenant_id, invitation);
      }
    });
    return map;
  }, [invitations]);

  const filteredTenants = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("fr");
    return tenants.filter((tenant) => {
      const house = housesById.get(tenant.house_id);
      const matchesHouse = houseFilter === "ALL" || tenant.house_id === houseFilter;
      const searchable = [
        tenant.full_name,
        tenant.phone,
        tenant.email,
        house?.name,
      ]
        .join(" ")
        .toLocaleLowerCase("fr");
      return matchesHouse && (!normalized || searchable.includes(normalized));
    });
  }, [houseFilter, housesById, query, tenants]);

  function updateField(field: keyof CreateTenantPayload, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const tenant = await createTenant(form);
      setTenants((current) => [tenant, ...current]);
      setForm(EMPTY_FORM);
      setOpen(false);
      setFeedback("Locataire ajouté avec succès.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Création impossible.");
    } finally {
      setSaving(false);
    }
  }

  async function openInvitation(tenant: Tenant) {
    setInvitedTenant(tenant);
    setError(null);
    const existing = invitationsByTenant.get(tenant.id);
    if (existing?.status === "PENDING" && !existing.is_expired) {
      setActiveInvitation(existing);
      return;
    }

    setActiveInvitation(null);
    setInvitingTenantId(tenant.id);
    try {
      const invitation = await createTenantInvitation(tenant.id);
      setInvitations((current) => [
        invitation,
        ...current.filter((item) => item.id !== invitation.id),
      ]);
      setTenants((current) =>
        current.map((item) =>
          item.id === tenant.id
            ? {
                ...item,
                status: "INVITED",
                status_label: "Invité",
                updated_at: invitation.updated_at,
              }
            : item,
        ),
      );
      setActiveInvitation(invitation);
    } catch (caughtError) {
      setInvitedTenant(null);
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Création de l’invitation impossible.",
      );
    } finally {
      setInvitingTenantId(null);
    }
  }

  function updateInvitation(invitation: TenantInvitation) {
    setActiveInvitation(invitation);
    setInvitations((current) => [
      invitation,
      ...current.filter((item) => item.id !== invitation.id),
    ]);
    setTenants((current) =>
      current.map((tenant) => {
        if (tenant.id !== invitation.tenant_id) return tenant;
        if (invitation.status === "ACCEPTED") {
          return {
            ...tenant,
            status: "ACTIVE",
            status_label: "Compte activé",
            has_account: true,
          };
        }
        if (invitation.status === "REVOKED") {
          return {
            ...tenant,
            status: "UNREGISTERED",
            status_label: "Sans compte ImmoLib",
          };
        }
        return tenant;
      }),
    );
  }

  return (
    <div className="space-y-6">
      <ModuleHeader
        action={
          <button
            className="primary-button w-fit"
            onClick={() => {
              setOpen(true);
              setError(null);
            }}
            type="button"
          >
            <UserPlus aria-hidden="true" size={18} />
            Ajouter un locataire
          </button>
        }
        description="Un locataire peut être enregistré sans compte ImmoLib. Son téléphone suffit pour lui envoyer plus tard un lien sécurisé vers sa quittance."
        eyebrow="Occupation"
        title="Locataires"
      />

      <Feedback message={feedback} />
      <Feedback message={error} tone="error" />

      <section className="grid gap-3 sm:grid-cols-3">
        <div className="panel p-4">
          <p className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Total</p>
          <p className="mt-1 text-2xl font-bold text-ink">{tenants.length}</p>
        </div>
        <div className="panel p-4">
          <p className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Avec compte</p>
          <p className="mt-1 text-2xl font-semibold text-ink">
            {tenants.filter((tenant) => tenant.has_account).length}
          </p>
        </div>
        <div className="panel p-4">
          <p className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Sans compte</p>
          <p className="mt-1 text-2xl font-semibold text-ink">
            {tenants.filter((tenant) => !tenant.has_account).length}
          </p>
        </div>
      </section>

      <section className="panel overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-line p-4 sm:flex-row sm:px-5">
          <label className="relative block flex-1">
            <span className="sr-only">Rechercher un locataire</span>
            <Search
              aria-hidden="true"
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted"
              size={18}
            />
            <input
              className="form-input pl-10"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Nom, téléphone, email…"
              type="search"
              value={query}
            />
          </label>
          <label>
            <span className="sr-only">Filtrer par maison</span>
            <select
              className="form-input min-w-48"
              onChange={(event) => setHouseFilter(event.target.value)}
              value={houseFilter}
            >
              <option value="ALL">Toutes les maisons</option>
              {houses.map((house) => (
                <option key={house.id} value={house.id}>
                  {house.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        {filteredTenants.length ? (
          <div className="grid gap-4 p-4 sm:p-5 lg:grid-cols-2 2xl:grid-cols-3">
            {filteredTenants.map((tenant) => {
              const house = housesById.get(tenant.house_id);
              const invitation = invitationsByTenant.get(tenant.id);
              return (
                <article className="rounded-2xl border border-line p-5" key={tenant.id}>
                  <div className="flex items-start justify-between gap-3">
                    <span className="grid size-10 place-items-center rounded-xl bg-brand-soft text-brand">
                      <Users aria-hidden="true" size={20} />
                    </span>
                    <span className={`status-pill ${statusStyle[tenant.status]}`}>
                      {tenant.status_label}
                    </span>
                  </div>
                  <h2 className="mt-5 text-lg font-bold text-ink">{tenant.full_name}</h2>
                  <div className="mt-3 space-y-2 text-sm text-muted">
                    <p className="flex items-center gap-2">
                      <House aria-hidden="true" size={16} />
                      {house?.name ?? "Maison inconnue"}
                    </p>
                    <p className="flex items-center gap-2">
                      <Phone aria-hidden="true" size={16} />
                      {tenant.phone}
                    </p>
                    <p className="flex items-center gap-2">
                      <AtSign aria-hidden="true" size={16} />
                      {tenant.email || "Aucun email"}
                    </p>
                  </div>
                  {!tenant.has_account ? (
                    <button
                      className="secondary-button mt-5 w-full"
                      disabled={invitingTenantId === tenant.id}
                      onClick={() => openInvitation(tenant)}
                      type="button"
                    >
                      <MailPlus aria-hidden="true" size={17} />
                      {invitingTenantId === tenant.id
                        ? "Création…"
                        : invitation?.status === "PENDING" &&
                            !invitation.is_expired
                          ? "Partager l’invitation"
                          : "Inviter sur ImmoLib"}
                    </button>
                  ) : null}
                </article>
              );
            })}
          </div>
        ) : (
          <div className="px-5 py-16 text-center">
            <p className="font-bold text-ink">
              {tenants.length
                ? "Aucun locataire ne correspond à cette recherche"
                : "Aucun locataire enregistré"}
            </p>
            <p className="mt-1 text-sm text-muted">
              {tenants.length
                ? "Modifiez la recherche ou le filtre."
                : "Ajoutez un locataire à l’une de vos maisons pour commencer."}
            </p>
          </div>
        )}
      </section>

      <Modal
        description="Le locataire est rattaché à une seule maison. Aucun compte ImmoLib n’est nécessaire."
        kicker="Nouvelle fiche"
        onClose={() => setOpen(false)}
        open={open}
        title="Ajouter un locataire"
      >
        <form className="p-5 sm:p-6" onSubmit={handleSubmit}>
          <div className="grid gap-5 sm:grid-cols-2">
            <label className="sm:col-span-2">
              <span className="form-label">Maison *</span>
              <select
                className="form-input"
                onChange={(event) => updateField("house_id", event.target.value)}
                required
                value={form.house_id}
              >
                <option value="">Sélectionner une maison</option>
                {houses.map((house) => (
                  <option key={house.id} value={house.id}>
                    {house.name} — {house.commune || house.city}
                  </option>
                ))}
              </select>
            </label>
            <label className="sm:col-span-2">
              <span className="form-label">Nom complet *</span>
              <input
                className="form-input"
                maxLength={160}
                onChange={(event) => updateField("full_name", event.target.value)}
                placeholder="Ex. Aïcha Koné"
                required
                value={form.full_name}
              />
            </label>
            <label>
              <span className="form-label">Téléphone *</span>
              <input
                className="form-input"
                maxLength={20}
                onChange={(event) => updateField("phone", event.target.value)}
                placeholder="+225 07 00 00 00 00"
                required
                type="tel"
                value={form.phone}
              />
            </label>
            <label>
              <span className="form-label">Email</span>
              <input
                className="form-input"
                onChange={(event) => updateField("email", event.target.value)}
                placeholder="nom@example.com"
                type="email"
                value={form.email}
              />
            </label>
          </div>
          <Feedback message={error} tone="error" />
          <div className="mt-7 flex flex-col-reverse gap-3 border-t border-line pt-5 sm:flex-row sm:justify-end">
            <button className="secondary-button" onClick={() => setOpen(false)} type="button">
              Annuler
            </button>
            <button className="primary-button" disabled={saving} type="submit">
              <UserPlus aria-hidden="true" size={18} />
              {saving ? "Enregistrement…" : "Ajouter le locataire"}
            </button>
          </div>
        </form>
      </Modal>

      <TenantInvitationModal
        invitation={activeInvitation}
        onClose={() => {
          setInvitedTenant(null);
          setActiveInvitation(null);
        }}
        onInvitationChange={updateInvitation}
        tenant={invitedTenant}
      />
    </div>
  );
}
