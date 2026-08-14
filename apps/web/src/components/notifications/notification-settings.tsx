"use client";

import {
  BellRing,
  CheckCircle2,
  Mail,
  MessageCircleMore,
  ShieldCheck,
  Smartphone,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useState } from "react";

import { Feedback } from "@/components/ui/feedback";
import { ModuleHeader } from "@/components/ui/module-header";
import {
  deactivatePushSubscription,
  getNotificationPreference,
  listPushSubscriptions,
  registerPushSubscription,
  updateNotificationPreference,
} from "@/lib/api-client";
import {
  disableBrowserPush,
  enableBrowserPush,
  isPushSupported,
} from "@/lib/web-push";
import type {
  DeliveryChannel,
  NotificationPreference,
  NotificationPreferenceUpdate,
  PreferredNotificationChannel,
  PushSubscription,
} from "@/types/domain";

const channelLabels: Record<DeliveryChannel, string> = {
  PUSH: "Push",
  EMAIL: "Email",
  WHATSAPP: "WhatsApp",
  SMS: "SMS",
};

const preferredOptions: Array<{
  value: PreferredNotificationChannel;
  label: string;
}> = [
  { value: "AUTO", label: "Automatique : push, puis email" },
  { value: "PUSH", label: "Push en priorité" },
  { value: "EMAIL", label: "Email en priorité" },
  { value: "WHATSAPP", label: "WhatsApp en priorité" },
  { value: "SMS", label: "SMS en priorité" },
];

export function NotificationSettings() {
  const [preference, setPreference] = useState<NotificationPreference | null>(null);
  const [subscriptions, setSubscriptions] = useState<PushSubscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getNotificationPreference(), listPushSubscriptions()])
      .then(([loadedPreference, loadedSubscriptions]) => {
        setPreference(loadedPreference);
        setSubscriptions(loadedSubscriptions);
      })
      .catch((caughtError) =>
        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "Chargement impossible.",
        ),
      )
      .finally(() => setLoading(false));
  }, []);

  async function save(
    payload: NotificationPreferenceUpdate,
    successMessage: string,
  ) {
    if (!preference) return;
    setSaving(true);
    setError(null);
    try {
      setPreference(await updateNotificationPreference(payload));
      setFeedback(successMessage);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Enregistrement impossible.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function activatePush() {
    setSaving(true);
    setError(null);
    try {
      const token = await enableBrowserPush();
      const device = await registerPushSubscription(
        token,
        navigator.userAgent.includes("Android")
          ? "Navigateur Android"
          : "Navigateur web",
      );
      setSubscriptions((current) => [
        device,
        ...current.filter((item) => item.id !== device.id),
      ]);
      setPreference(await getNotificationPreference());
      setFeedback("Cet appareil recevra les notifications ImmoLib.");
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Activation push impossible.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function deactivatePush() {
    setSaving(true);
    setError(null);
    try {
      const token = await disableBrowserPush();
      if (token) await deactivatePushSubscription(token);
      setPreference(
        await updateNotificationPreference({ push_enabled: false }),
      );
      setSubscriptions(await listPushSubscriptions());
      setFeedback("Notifications push désactivées sur cet appareil.");
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Désactivation impossible.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="text-sm font-semibold text-muted">Chargement des préférences…</p>;
  }
  if (!preference) {
    return (
      <div className="panel p-5">
        <h1 className="section-title">Notifications indisponibles</h1>
        <Feedback
          message={error ?? "Impossible de charger vos préférences de notification."}
          tone="error"
        />
      </div>
    );
  }

  const pushActive =
    preference.push_enabled && preference.active_push_devices > 0;

  return (
    <div className="space-y-6">
      <ModuleHeader
        description="ImmoLib privilégie les canaux gratuits. Le SMS reste désactivé tant que vous ne le choisissez pas."
        eyebrow="Compte"
        title="Notifications"
      />
      <Feedback message={feedback} />
      <Feedback message={error} tone="error" />

      <section className="panel p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand">
            <BellRing aria-hidden="true" size={21} />
          </span>
          <div>
            <h2 className="text-lg font-bold text-ink">Ordre de priorité</h2>
            <p className="mt-1 text-sm leading-6 text-muted">
              En mode automatique : push si l’utilisateur a activé son appareil,
              sinon email vérifié. WhatsApp et SMS exigent un choix explicite.
            </p>
          </div>
        </div>
        <label className="mt-5 block max-w-xl">
          <span className="form-label">Canal préféré</span>
          <select
            className="form-input"
            disabled={saving}
            onChange={(event) =>
              save(
                {
                  preferred_channel: event.target
                    .value as PreferredNotificationChannel,
                },
                "Ordre de priorité enregistré.",
              )
            }
            value={preference.preferred_channel}
          >
            {preferredOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <div className="mt-5 flex flex-wrap gap-2">
          {(["PUSH", "EMAIL", "WHATSAPP", "SMS"] as const).map((channel) => {
            const available = preference.available_channels.includes(channel);
            return (
              <span
                className={`status-pill ${available ? "status-paid" : "status-vacant"}`}
                key={channel}
              >
                {available ? <CheckCircle2 aria-hidden="true" size={14} /> : null}
                {channelLabels[channel]} {available ? "disponible" : "indisponible"}
              </span>
            );
          })}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <article className="panel p-5 sm:p-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand">
                <BellRing aria-hidden="true" size={21} />
              </span>
              <div>
                <h2 className="font-bold text-ink">Push Firebase</h2>
                <p className="mt-1 text-sm leading-6 text-muted">
                  Gratuit et immédiat après autorisation du navigateur.
                </p>
              </div>
            </div>
            <span className={`status-pill ${pushActive ? "status-paid" : "status-vacant"}`}>
              {pushActive ? "Actif" : "Inactif"}
            </span>
          </div>
          <p className="mt-5 text-sm text-muted">
            {preference.active_push_devices} appareil
            {preference.active_push_devices > 1 ? "s" : ""} actif
            {preference.active_push_devices > 1 ? "s" : ""}
          </p>
          {!isPushSupported() ? (
            <p className="mt-4 flex gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900">
              <TriangleAlert aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
              Ce navigateur ne prend pas en charge les notifications push.
            </p>
          ) : null}
          <button
            className={pushActive ? "secondary-button mt-5" : "primary-button mt-5"}
            disabled={saving || !isPushSupported()}
            onClick={pushActive ? deactivatePush : activatePush}
            type="button"
          >
            <BellRing aria-hidden="true" size={17} />
            {pushActive ? "Désactiver sur cet appareil" : "Activer sur cet appareil"}
          </button>
          {subscriptions.length ? (
            <p className="mt-4 text-xs text-muted">
              Dernier appareil : {subscriptions[0].device_name || "Navigateur web"}
            </p>
          ) : null}
        </article>

        <ChannelCard
          active={preference.email_enabled}
          description={
            preference.email_verified
              ? `${preference.email} est vérifié et utilisable avec Amazon SES.`
              : "L’adresse email doit d’abord être vérifiée."
          }
          disabled={!preference.email_verified || saving}
          icon={Mail}
          label="Email Amazon SES"
          onChange={(active) =>
            save({ email_enabled: active }, "Préférence email enregistrée.")
          }
        />

        <ChannelCard
          active={preference.whatsapp_enabled}
          description="Le destinataire peut recevoir le message sans avoir enregistré votre numéro. L’opt-in reste obligatoire pour l’envoi automatique."
          disabled={saving}
          icon={MessageCircleMore}
          label="WhatsApp"
          onChange={(active) =>
            save(
              active
                ? { whatsapp_enabled: true, whatsapp_opt_in: true }
                : { whatsapp_enabled: false },
              "Préférence WhatsApp enregistrée.",
            )
          }
        />

        <ChannelCard
          active={preference.sms_enabled}
          description="Canal payant de dernier recours, utile si le locataire n’a ni push, ni email, ni WhatsApp autorisé."
          disabled={saving}
          icon={Smartphone}
          label="SMS de secours"
          onChange={(active) =>
            save({ sms_enabled: active }, "Préférence SMS enregistrée.")
          }
          warning
        />
      </section>

      <section className="rounded-[14px] border border-line bg-white p-5 text-sm leading-6 text-muted">
        <p className="flex items-center gap-2 font-bold">
          <ShieldCheck aria-hidden="true" size={18} />
          Vérifications séparées
        </p>
        <p className="mt-1">
          Vérifier un email ne marque jamais le téléphone comme vérifié. Une
          invitation de copropriétaire liée au numéro attend donc toujours la
          preuve du téléphone.
        </p>
      </section>
    </div>
  );
}

function ChannelCard({
  active,
  description,
  disabled,
  icon: Icon,
  label,
  onChange,
  warning = false,
}: {
  active: boolean;
  description: string;
  disabled: boolean;
  icon: typeof Mail;
  label: string;
  onChange: (active: boolean) => void;
  warning?: boolean;
}) {
  return (
    <article className="panel p-5 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span
            className={`grid size-11 shrink-0 place-items-center rounded-xl ${
              warning ? "bg-amber-50 text-amber-800" : "bg-sky-soft text-sky-dark"
            }`}
          >
            <Icon aria-hidden="true" size={21} />
          </span>
          <div>
            <h2 className="font-bold text-ink">{label}</h2>
            <p className="mt-1 text-sm leading-6 text-muted">{description}</p>
          </div>
        </div>
        <label className="relative inline-flex cursor-pointer items-center">
          <input
            checked={active}
            className="peer sr-only"
            disabled={disabled}
            onChange={(event) => onChange(event.target.checked)}
            type="checkbox"
          />
          <span className="h-7 w-12 rounded-full bg-slate-300 transition-colors after:absolute after:left-1 after:top-1 after:size-5 after:rounded-full after:bg-white after:transition-transform peer-checked:bg-brand peer-checked:after:translate-x-5 peer-disabled:cursor-not-allowed peer-disabled:opacity-50" />
        </label>
      </div>
    </article>
  );
}
