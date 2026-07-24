"use client";

import {
  BadgeCheck,
  House,
  Link2,
  LoaderCircle,
  LogIn,
  MapPin,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { RegisterForm } from "@/components/auth/register-form";
import { Feedback } from "@/components/ui/feedback";
import {
  claimTenantInvitation,
  previewTenantInvitation,
} from "@/lib/api-client";
import { formatDate } from "@/lib/format";
import type { PublicTenantInvitation, RegisterPayload } from "@/types/domain";

function initialRegistrationValues(
  invitation: PublicTenantInvitation,
): Partial<RegisterPayload> {
  const [firstName = "", ...lastNameParts] = invitation.tenant_name.trim().split(/\s+/);
  return {
    phone: invitation.phone,
    email: invitation.email,
    first_name: firstName,
    last_name: lastNameParts.join(" "),
  };
}

export function TenantInvitationOnboarding({
  token,
  completed = false,
}: {
  token: string;
  completed?: boolean;
}) {
  const { user, loading: sessionLoading } = useAuth();
  const [invitation, setInvitation] = useState<PublicTenantInvitation | null>(null);
  const [loading, setLoading] = useState(true);
  const [claiming, setClaiming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    previewTenantInvitation(token)
      .then(setInvitation)
      .catch((caughtError) =>
        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "Cette invitation ne peut pas être ouverte.",
        ),
      )
      .finally(() => setLoading(false));
  }, [completed, token]);

  const registerValues = useMemo(
    () => (invitation ? initialRegistrationValues(invitation) : undefined),
    [invitation],
  );

  async function claimInvitation() {
    setClaiming(true);
    setError(null);
    try {
      setInvitation(await claimTenantInvitation(token));
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Rattachement impossible.",
      );
    } finally {
      setClaiming(false);
    }
  }

  if (loading || sessionLoading) {
    return (
      <p className="flex items-center justify-center gap-2 py-8 text-sm font-semibold text-muted">
        <LoaderCircle aria-hidden="true" className="animate-spin" size={18} />
        Vérification de l’invitation…
      </p>
    );
  }

  if (!invitation) {
    return (
      <div className="py-5 text-center">
        <Link2 aria-hidden="true" className="mx-auto text-muted" size={28} />
        <h2 className="mt-4 text-lg font-bold text-ink">Invitation indisponible</h2>
        <Feedback message={error} tone="error" />
      </div>
    );
  }

  const accepted = invitation.status === "ACCEPTED";
  if (accepted) {
    return (
      <div className="py-5 text-center">
        <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-brand-soft text-brand">
          <BadgeCheck aria-hidden="true" size={28} />
        </span>
        <h2 className="mt-5 text-xl font-bold text-ink">Compte rattaché</h2>
        <p className="mt-2 text-sm leading-6 text-muted">
          Votre compte est maintenant lié à {invitation.house_name}. Votre
          bail, vos échéances, vos paiements et vos documents sont disponibles
          dans votre espace locataire.
        </p>
        <div className="mt-5 rounded-xl border border-line bg-canvas p-4 text-left text-sm">
          <p className="font-bold text-ink">{invitation.tenant_name}</p>
          <p className="mt-1 text-muted">{invitation.house_address}</p>
        </div>
        <Link className="primary-button mt-5 w-full" href="/espace-locataire">
          <House aria-hidden="true" size={18} />
          Ouvrir mon espace locataire
        </Link>
      </div>
    );
  }

  if (invitation.status !== "PENDING" || invitation.is_expired) {
    return (
      <div className="py-5 text-center">
        <ShieldCheck aria-hidden="true" className="mx-auto text-muted" size={30} />
        <h2 className="mt-4 text-lg font-bold text-ink">
          Invitation {invitation.status_label.toLowerCase()}
        </h2>
        <p className="mt-2 text-sm text-muted">
          Demandez au bailleur de créer une nouvelle invitation.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="rounded-2xl border border-brand/20 bg-brand-soft p-4">
        <p className="text-sm font-bold text-brand-dark">
          {invitation.owner_name} vous invite
        </p>
        <div className="mt-3 space-y-2 text-sm text-brand-dark/85">
          <p className="flex items-center gap-2">
            <House aria-hidden="true" size={16} />
            {invitation.house_name}
          </p>
          <p className="flex items-center gap-2">
            <MapPin aria-hidden="true" size={16} />
            {invitation.house_address}
          </p>
        </div>
        <p className="mt-3 text-xs text-brand-dark/70">
          Invitation valable jusqu’au {formatDate(invitation.expires_at)}.
        </p>
      </div>

      <Feedback message={error} tone="error" />

      {user ? (
        <div className="mt-6">
          <p className="text-sm leading-6 text-muted">
            Vous êtes connecté comme <strong className="text-ink">{user.full_name || user.phone}</strong>.
            ImmoLib vérifiera que ce compte correspond aux coordonnées de
            l’invitation.
          </p>
          <button
            className="primary-button mt-5 w-full"
            disabled={claiming}
            onClick={claimInvitation}
            type="button"
          >
            <ShieldCheck aria-hidden="true" size={18} />
            {claiming ? "Rattachement…" : "Rattacher cette location"}
          </button>
        </div>
      ) : (
        <div className="mt-6">
          <h2 className="text-lg font-bold text-ink">Créer mon compte locataire</h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            Les coordonnées sont verrouillées pour empêcher qu’une autre
            personne détourne l’invitation.
          </p>
          <div className="mt-5">
            <RegisterForm
              initialValues={registerValues}
              nextPath={`/invitation-locataire/${token}?terminee=1`}
              tenantInvitationToken={token}
            />
          </div>
          <p className="mt-6 text-center text-sm text-muted">
            Vous avez déjà un compte ?{" "}
            <Link
              className="inline-flex items-center gap-1 font-bold text-brand hover:text-brand-dark"
              href={`/connexion?next=${encodeURIComponent(`/invitation-locataire/${token}`)}`}
            >
              <LogIn aria-hidden="true" size={15} />
              Se connecter
            </Link>
          </p>
        </div>
      )}
    </div>
  );
}
