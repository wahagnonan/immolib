/* eslint-disable no-restricted-globals */

// Service Worker pour les notifications Web Push standard
// Remplace Firebase Cloud Messaging

self.addEventListener("push", (event) => {
  if (!event.data) return;

  let payload = {};
  try {
    payload = event.data.json();
  } catch {
    payload = { title: "ImmoLib", body: event.data.text() };
  }

  const title = payload.title || "ImmoLib";
  const options = {
    body: payload.body || "Une nouvelle information est disponible.",
    icon: payload.icon || "/icon.png",
    badge: payload.badge || "/icon.png",
    data: { url: payload.url || payload.data?.url || "/" },
    tag: payload.tag || "immolib-notification",
    renotify: true,
    vibrate: [100, 50, 100],
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const destination = event.notification.data?.url || "/";

  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      // Si une fenêtre est déjà ouverte, la focus
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && "focus" in client) {
          client.navigate(destination);
          return client.focus();
        }
        }
      // Sinon, ouvrir une nouvelle fenêtre
      return clients.openWindow(destination);
    })
  );
});

self.addEventListener("pushsubscriptionchange", (event) => {
  // Réabonnement automatique si l'abonnement expire
  event.waitUntil(
    self.registration.pushManager.subscribe(event.oldSubscription.options).then((subscription) => {
      // Envoyer le nouvel abonnement au serveur
      return fetch("/api/v1/push-subscriptions/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          endpoint: subscription.endpoint,
          keys: {
            p256dh: arrayBufferToBase64(subscription.getKey("p256dh")),
            auth: arrayBufferToBase64(subscription.getKey("auth")),
          },
        }),
      });
    })
  );
});

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}
