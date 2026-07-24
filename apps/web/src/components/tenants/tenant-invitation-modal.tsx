"use client";

import {
  Copy,
  Mail,
  MessageCircleMore,
  Send,
  Share2,
  Smartphone,
  Trash2,
} from "lucide-react";
import { useState } from "react";

import { Feedback } from "@/components/ui/feedback";
import { Modal } from "@/components/ui/modal";
import {
  revokeTenantInvitation,
  shareTenantInvitation,
} from "@/lib/api-client";
import { formatDate } from "@/lib/format";
import type {
  Tenant,
  TenantInvitation,
  TenantInvitationShareChannel,
  TenantInvitationShareResult,
} from "@/types/domain";

export function TenantInvitationModal({
  invitation,
  tenant,
  onClose,
  onInvitationChange,
}: {
  invitation: TenantInvitation | null;
  tenant: Tenant | null;
  onClose: () => void;
  onInvitationChange: (invitation: TenantInvitation) => void;
}) {
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<TenantInvitationShareResult | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function share(channel: TenantInvitationShareChannel) {
    if (!tenant || !invitation) return;
    setSaving(true);
    setError(null);
    try {
      const shareResult = await shareTenantInvitation(invitation.id, channel);
      setResult(shareResult);
      onInvitationChange(shareResult.invitation);

      if (channel === "COPY") {
        await navigator.clipboard.writeText(shareResult.message);
        setFeedback("Message d’invitation copié.");
      } else if (channel === "NATIVE") {
        if (navigator.share) {
          await navigator.share({
            title: shareResult.subject,
            text: shareResult.message,
          });
          setFeedback("Menu de partage ouvert.");
        } else {
          await navigator.clipboard.writeText(shareResult.message);
          setFeedback("Partage natif indisponible : message copié.");
        }
      } else if (channel === "EMAIL_AUTOMATIC") {
        setFeedback("Email placé dans la file Amazon SES.");
      } else {
        window.location.href = shareResult.action_url;
      }
    } catch (caughtError) {
      if (caughtError instanceof DOMException && caughtError.name === "AbortError") {
        return;
      }
      setError(
        caughtError instanceof Error ? caughtError.message : "Partage impossible.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function revoke() {
    if (!invitation) return;
    setSaving(true);
    setError(null);
    try {
      const revoked = await revokeTenantInvitation(invitation.id);
      onInvitationChange(revoked);
      setFeedback("Invitation révoquée.");
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Révocation impossible.",
      );
    } finally {
      setSaving(false);
    }
  }

  const active = invitation?.status === "PENDING" && !invitation.is_expired;

  return (
    <Modal
      description="Envoyez le lien avec l’application du bailleur ou automatiquement par Amazon SES."
      kicker="Onboarding locataire"
      onClose={onClose}
      open={Boolean(tenant)}
      title={`Inviter ${tenant?.full_name ?? "le locataire"}`}
    >
      <div className="p-5 sm:p-6">
        {!invitation ? (
          <p className="text-sm font-semibold text-muted">
            Création de l’invitation…
          </p>
        ) : (
          <>
            <div className="rounded-xl border border-brand/20 bg-brand-soft p-4 text-sm text-brand-dark">
              <p className="font-bold">Lien sécurisé prêt</p>
              <p className="mt-1">
                Valable jusqu’au {formatDate(invitation.expires_at)}.
              </p>
            </div>

            <Feedback message={feedback} />
            <Feedback message={error} tone="error" />

            {active ? (
              <>
                <section className="mt-5">
                  <p className="form-label">Partage gratuit depuis votre appareil</p>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                    <ShareButton
                      disabled={saving}
                      icon={MessageCircleMore}
                      label="WhatsApp"
                      onClick={() => share("WHATSAPP")}
                    />
                    <ShareButton
                      disabled={saving || !tenant?.email}
                      icon={Mail}
                      label="Email local"
                      onClick={() => share("EMAIL")}
                    />
                    <ShareButton
                      disabled={saving}
                      icon={Smartphone}
                      label="SMS local"
                      onClick={() => share("SMS")}
                    />
                    <ShareButton
                      disabled={saving}
                      icon={Share2}
                      label="Partager"
                      onClick={() => share("NATIVE")}
                    />
                    <ShareButton
                      disabled={saving}
                      icon={Copy}
                      label="Copier"
                      onClick={() => share("COPY")}
                    />
                  </div>
                </section>

                <section className="mt-5 border-t border-line pt-5">
                  <p className="form-label">Envoi automatique</p>
                  <button
                    className="primary-button w-full"
                    disabled={saving || !tenant?.email}
                    onClick={() => share("EMAIL_AUTOMATIC")}
                    type="button"
                  >
                    <Send aria-hidden="true" size={18} />
                    Envoyer avec Amazon SES
                  </button>
                  {!tenant?.email ? (
                    <p className="mt-2 text-xs text-amber-800">
                      Ajoutez un email au locataire pour utiliser SES.
                    </p>
                  ) : null}
                </section>

                {result ? (
                  <label className="mt-5 block">
                    <span className="form-label">Lien d’invitation</span>
                    <input
                      className="form-input"
                      readOnly
                      value={result.secure_url}
                    />
                  </label>
                ) : null}

                <button
                  className="mt-6 inline-flex min-h-10 items-center gap-2 rounded-xl px-3 text-sm font-bold text-red-700 hover:bg-red-50"
                  disabled={saving}
                  onClick={revoke}
                  type="button"
                >
                  <Trash2 aria-hidden="true" size={17} />
                  Révoquer cette invitation
                </button>
              </>
            ) : (
              <p className="mt-5 text-sm text-muted">
                Cette invitation est {invitation.status_label.toLowerCase()}.
                Créez-en une nouvelle depuis la fiche du locataire si nécessaire.
              </p>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}

function ShareButton({
  disabled,
  icon: Icon,
  label,
  onClick,
}: {
  disabled: boolean;
  icon: typeof Mail;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className="secondary-button"
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      <Icon aria-hidden="true" size={17} />
      {label}
    </button>
  );
}
