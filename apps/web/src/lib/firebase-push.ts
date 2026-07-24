import { deleteToken, getMessaging, getToken, isSupported } from "firebase/messaging";
import { getApp, getApps, initializeApp } from "firebase/app";


const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

const vapidKey = process.env.NEXT_PUBLIC_FIREBASE_VAPID_KEY;
const TOKEN_STORAGE_KEY = "immolib_fcm_token";

export const FIREBASE_PUSH_CONFIGURED = Boolean(
  firebaseConfig.apiKey &&
    firebaseConfig.projectId &&
    firebaseConfig.messagingSenderId &&
    firebaseConfig.appId &&
    vapidKey,
);

function firebaseApp() {
  return getApps().length ? getApp() : initializeApp(firebaseConfig);
}

export async function enableBrowserPush(): Promise<string> {
  if (!FIREBASE_PUSH_CONFIGURED) {
    throw new Error("Firebase n’est pas encore configuré pour cet environnement.");
  }
  if (
    typeof window === "undefined" ||
    !("serviceWorker" in navigator) ||
    !("Notification" in window)
  ) {
    throw new Error("Ce navigateur ne prend pas en charge les notifications push.");
  }
  if (!(await isSupported())) {
    throw new Error("Firebase Push n’est pas disponible sur ce navigateur.");
  }

  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("L’autorisation de notification n’a pas été accordée.");
  }

  const registration = await navigator.serviceWorker.register(
    "/firebase-messaging-sw.js",
  );
  const token = await getToken(getMessaging(firebaseApp()), {
    vapidKey,
    serviceWorkerRegistration: registration,
  });
  if (!token) {
    throw new Error("Firebase n’a pas pu créer le jeton de cet appareil.");
  }
  window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  return token;
}

export async function disableBrowserPush(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const storedToken = window.localStorage.getItem(TOKEN_STORAGE_KEY);
  if (FIREBASE_PUSH_CONFIGURED && (await isSupported())) {
    await deleteToken(getMessaging(firebaseApp()));
  }
  window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  return storedToken;
}

