"use client";

import { Download, X } from "lucide-react";
import { useEffect, useState } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const DISMISSED_KEY = "immolib_pwa_dismissed";
const DISMISSED_EXPIRY_DAYS = 7;

export function PwaInstallBanner() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [showBanner, setShowBanner] = useState(false);
  const [isInstalling, setIsInstalling] = useState(false);

  useEffect(() => {
    // Vérifier si l'utilisateur a déjà été redirigé
    const dismissedAt = localStorage.getItem(DISMISSED_KEY);
    if (dismissedAt) {
      const daysSinceDismissed = (Date.now() - Number(dismissedAt)) / (1000 * 60 * 60 * 24);
      if (daysSinceDismissed < DISMISSED_EXPIRY_DAYS) {
        return;
      }
    }

    // Vérifier si déjà installé
    if (window.matchMedia("(display-mode: standalone)").matches) {
      return;
    }

    // Vérifier si l'événement beforeinstallprompt est disponible
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      setShowBanner(true);
    };

    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  async function handleInstall() {
    if (!deferredPrompt) return;

    setIsInstalling(true);
    try {
      await deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      if (outcome === "accepted") {
        setShowBanner(false);
      }
    } catch {
      // Erreur silencieuse
    } finally {
      setIsInstalling(false);
      setDeferredPrompt(null);
    }
  }

  function handleDismiss() {
    setShowBanner(false);
    localStorage.setItem(DISMISSED_KEY, String(Date.now()));
  }

  if (!showBanner || !deferredPrompt) return null;

  return (
    <div className="fixed bottom-4 left-4 right-4 z-50 sm:left-auto sm:right-4 sm:max-w-sm">
      <div className="rounded-2xl border border-line bg-white p-4 shadow-[0_8px_30px_rgba(18,16,18,0.15)]">
        <div className="flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand text-white">
            <Download size={18} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-bold text-ink">Installer ImmoLib</p>
            <p className="mt-1 text-xs leading-5 text-muted">
              Accédez rapidement depuis votre écran d'accueil. Fonctionne même hors ligne.
            </p>
            <div className="mt-3 flex gap-2">
              <button
                className="primary-button !px-3 !py-1.5 !text-xs"
                disabled={isInstalling}
                onClick={handleInstall}
                type="button"
              >
                {isInstalling ? "Installation…" : "Installer"}
              </button>
              <button
                className="text-xs font-semibold text-muted hover:text-ink"
                onClick={handleDismiss}
                type="button"
              >
                Pas maintenant
              </button>
            </div>
          </div>
          <button
            className="shrink-0 rounded-lg p-1 text-muted hover:text-ink"
            onClick={handleDismiss}
            type="button"
          >
            <X size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
