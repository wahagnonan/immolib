import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const STORAGE_KEY = "immolib_push_subscription";

const KEY_BYTES = Array.from({ length: 65 }, (_, index) => index);
const VAPID_KEY = Buffer.from(KEY_BYTES).toString("base64url");

type Subscription = { endpoint: string };

function existingSubscription(): Subscription {
  return { endpoint: "https://push.example/old" };
}

function newSubscription(): Subscription {
  return { endpoint: "https://push.example/new" };
}

type SubscribeOptions = {
  userVisibleOnly: boolean;
  applicationServerKey: Uint8Array;
};

function mockServiceWorker(options: { existing: boolean }) {
  const subscription = options.existing
    ? existingSubscription()
    : newSubscription();
  const pushManager = {
    getSubscription: vi.fn(async () =>
      options.existing ? existingSubscription() : null,
    ),
    subscribe: vi.fn(async (options: SubscribeOptions) => ({
      endpoint: `https://push.example/${options.userVisibleOnly ? "new" : "nope"}`,
    })),
  };
  const registration = { pushManager };
  const register = vi.fn(async () => registration);
  const getRegistration = vi.fn(async () => registration);
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: { register, getRegistration },
  });
  return { register, getRegistration, pushManager, subscription };
}

function mockNotification(permission: NotificationPermission) {
  Object.defineProperty(window, "Notification", {
    configurable: true,
    value: { requestPermission: vi.fn(async () => permission) },
  });
}

function mockPushManager() {
  Object.defineProperty(window, "PushManager", {
    configurable: true,
    value: class PushManager {},
  });
}

function mockPushEnvironment(permission: NotificationPermission, options: { existing: boolean }) {
  mockNotification(permission);
  mockPushManager();
  return mockServiceWorker(options);
}

async function loadWebPush() {
  vi.resetModules();
  return import("@/lib/web-push");
}

describe("enableBrowserPush", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_VAPID_PUBLIC_KEY", VAPID_KEY);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    window.localStorage.clear();
    Reflect.deleteProperty(navigator, "serviceWorker");
    Reflect.deleteProperty(window, "Notification");
    Reflect.deleteProperty(window, "PushManager");
  });

  it("throws when the VAPID key is not configured", async () => {
    vi.stubEnv("NEXT_PUBLIC_VAPID_PUBLIC_KEY", "");
    const { enableBrowserPush } = await loadWebPush();

    await expect(enableBrowserPush()).rejects.toThrow(/pas encore configur/);
  });

  it("throws when the browser does not support push", async () => {
    const { enableBrowserPush } = await loadWebPush();

    await expect(enableBrowserPush()).rejects.toThrow(/ne prend pas en charge/);
  });

  it("throws when the permission is denied", async () => {
    mockPushEnvironment("denied", { existing: false });
    const { enableBrowserPush } = await loadWebPush();

    await expect(enableBrowserPush()).rejects.toThrow(/pas été accordée/);
  });

  it("stores and returns an existing subscription without re-subscribing", async () => {
    const { register, pushManager } = mockPushEnvironment("granted", {
      existing: true,
    });
    const { enableBrowserPush } = await loadWebPush();

    const serialized = await enableBrowserPush();

    expect(register).toHaveBeenCalledWith("/sw.js");
    expect(pushManager.getSubscription).toHaveBeenCalledOnce();
    expect(pushManager.subscribe).not.toHaveBeenCalled();
    expect(JSON.parse(serialized).endpoint).toBe("https://push.example/old");
    expect(JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "{}").endpoint).toBe(
      "https://push.example/old",
    );
  });

  it("subscribes with the decoded VAPID key when none exists", async () => {
    const { pushManager } = mockPushEnvironment("granted", { existing: false });
    const { enableBrowserPush } = await loadWebPush();

    const serialized = await enableBrowserPush();

    expect(pushManager.subscribe).toHaveBeenCalledOnce();
    const options = pushManager.subscribe.mock.calls[0][0];
    expect(options.userVisibleOnly).toBe(true);
    expect(options.applicationServerKey).toBeInstanceOf(Uint8Array);
    expect(Array.from(options.applicationServerKey)).toEqual(KEY_BYTES);
    expect(JSON.parse(serialized).endpoint).toBe("https://push.example/new");
  });
});

describe("disableBrowserPush", () => {
  afterEach(() => {
    window.localStorage.clear();
    Reflect.deleteProperty(navigator, "serviceWorker");
  });

  it("unsubscribes and clears the stored subscription", async () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(existingSubscription()));
    const unsubscribe = vi.fn(async () => true);
    const pushManager = {
      getSubscription: vi.fn(async () => ({ endpoint: "e", unsubscribe })),
    };
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: {
        register: vi.fn(),
        getRegistration: vi.fn(async () => ({ pushManager })),
      },
    });
    const { disableBrowserPush } = await loadWebPush();

    const stored = await disableBrowserPush();

    expect(unsubscribe).toHaveBeenCalledOnce();
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(JSON.parse(stored ?? "{}").endpoint).toBe("https://push.example/old");
  });

  it("returns null when nothing is stored", async () => {
    const { disableBrowserPush } = await loadWebPush();

    await expect(disableBrowserPush()).resolves.toBeNull();
  });
});
