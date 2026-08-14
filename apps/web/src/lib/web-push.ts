const vapidPublicKey = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;

export const WEB_PUSH_CONFIGURED = Boolean(vapidPublicKey);

const SUBSCRIPTION_STORAGE_KEY = "immolib_push_subscription";

function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(new ArrayBuffer(rawData.length));
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export async function enableBrowserPush(): Promise<string> {
  const publicKey = vapidPublicKey;
  if (!publicKey) {
    throw new Error(
      "Le Web Push n’est pas encore configuré pour cet environnement.",
    );
  }
  if (
    typeof window === "undefined" ||
    !("serviceWorker" in navigator) ||
    !("PushManager" in window) ||
    !("Notification" in window)
  ) {
    throw new Error("Ce navigateur ne prend pas en charge les notifications push.");
  }

  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("L’autorisation de notification n’a pas été accordée.");
  }

  const registration = await navigator.serviceWorker.register("/sw.js");
  let subscription = await registration.pushManager.getSubscription();
  if (!subscription) {
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    });
  }
  const serialized = JSON.stringify(subscription);
  window.localStorage.setItem(SUBSCRIPTION_STORAGE_KEY, serialized);
  return serialized;
}

export async function disableBrowserPush(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const stored = window.localStorage.getItem(SUBSCRIPTION_STORAGE_KEY);
  const registration = await navigator.serviceWorker?.getRegistration?.("/sw.js");
  const subscription = await registration?.pushManager.getSubscription();
  await subscription?.unsubscribe();
  window.localStorage.removeItem(SUBSCRIPTION_STORAGE_KEY);
  return stored;
}
