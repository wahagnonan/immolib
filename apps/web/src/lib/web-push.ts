/**
 * Module Web Push standard (remplace Firebase Cloud Messaging)
 * Utilise l'API Push native des navigateurs avec VAPID keys.
 */

const PUSH_API_URL = "/api/v1/push-subscriptions";
const SW_REGISTRATION_KEY = "immolib_sw_registration";

// VAPID public key (à configurer côté serveur)
// En production, cette clé est générée avec web-push et stockée dans les variables d'env
const VAPID_PUBLIC_KEY = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY || "";

/**
 * Vérifie si le navigateur supporte les notifications push
 */
export function isPushSupported(): boolean {
  if (typeof window === "undefined") return false;
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

/**
 * Demande l'autorisation et s'abonne aux notifications push
 */
export async function enableBrowserPush(): Promise<string> {
  if (!isPushSupported()) {
    throw new Error("Ce navigateur ne prend pas en charge les notifications push.");
  }

  if (!VAPID_PUBLIC_KEY) {
    throw new Error("La clé VAPID n'est pas configurée. Contactez l'administrateur.");
  }

  // Demander l'autorisation
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("L'autorisation de notification n'a pas été accordée.");
  }

  // Enregistrer le service worker
  const registration = await navigator.serviceWorker.register("/sw.js");
  await navigator.serviceWorker.ready;

  // S'abonner aux notifications push
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
  });

  // Envoyer l'abonnement au serveur
  const response = await fetch(PUSH_API_URL, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({
      endpoint: subscription.endpoint,
      keys: {
        p256dh: arrayBufferToBase64(subscription.getKey("p256dh")),
        auth: arrayBufferToBase64(subscription.getKey("auth")),
      },
      platform: "WEB",
      device_name: getDeviceName(),
    }),
  });

  if (!response.ok) {
    throw new Error("Impossible d'enregistrer l'abonnement sur le serveur.");
  }

  const data = await response.json();
  localStorage.setItem(SW_REGISTRATION_KEY, data.id || subscription.endpoint);

  return subscription.endpoint;
}

/**
 * Désactive les notifications push
 */
export async function disableBrowserPush(): Promise<string | null> {
  if (typeof window === "undefined") return null;

  const storedEndpoint = localStorage.getItem(SW_REGISTRATION_KEY);

  // Supprimer l'abonnement du navigateur
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  if (subscription) {
    await subscription.unsubscribe();
  }

  // Supprimer du serveur
  if (storedEndpoint) {
    await fetch(PUSH_API_URL, {
      method: "DELETE",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: JSON.stringify({ endpoint: storedEndpoint }),
    }).catch(() => {});
  }

  localStorage.removeItem(SW_REGISTRATION_KEY);
  return storedEndpoint;
}

/**
 * Vérifie si l'utilisateur est actuellement abonné
 */
export async function isPushEnabled(): Promise<boolean> {
  if (!isPushSupported()) return false;

  try {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();
    return subscription !== null;
  } catch {
    return false;
  }
}

// --- Helpers ---

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

function arrayBufferToBase64(buffer: ArrayBuffer | null): string {
  if (!buffer) return "";
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function getCookie(name: string): string {
  const cookies = document.cookie.split(";");
  for (const cookie of cookies) {
    const [key, value] = cookie.trim().split("=");
    if (key === name) return value;
  }
  return "";
}

function getDeviceName(): string {
  const ua = navigator.userAgent;
  if (/android/i.test(ua)) return "Android";
  if (/iPad|iPhone|iPod/.test(ua)) return "iOS";
  if (/Mac/.test(ua)) return "Mac";
  if (/Windows/.test(ua)) return "Windows";
  if (/Linux/.test(ua)) return "Linux";
  return "Navigateur";
}
