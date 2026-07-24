import type {
  AccountOtpRequestResult,
  AuthResponse,
  CurrentUser,
  LoginPayload,
  PasswordResetConfirmPayload,
  PhoneCodePayload,
  RegisterPayload,
  RegistrationResult,
} from "@/types/auth";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "/backend";

type ApiErrorBody = {
  detail?: string;
  non_field_errors?: string[];
  [field: string]: unknown;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly body: ApiErrorBody | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function csrfToken() {
  if (typeof document === "undefined") return null;
  return document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith("csrftoken="))
    ?.split("=")[1];
}

function errorMessage(body: ApiErrorBody | null) {
  if (body?.detail) return body.detail;
  if (body?.non_field_errors?.[0]) return body.non_field_errors[0];
  if (body) {
    const firstValue = Object.values(body)[0];
    if (Array.isArray(firstValue) && typeof firstValue[0] === "string") {
      return firstValue[0];
    }
    if (typeof firstValue === "string") return firstValue;
  }
  return "La requête vers ImmoLib a échoué.";
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const method = init?.method?.toUpperCase() ?? "GET";
  const token = csrfToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(token && method !== "GET" ? { "X-CSRFToken": token } : {}),
      ...init?.headers,
    },
  });
  const body = (await response.json().catch(() => null)) as ApiErrorBody | T | null;
  if (!response.ok) {
    const errorBody = body as ApiErrorBody | null;
    throw new ApiError(errorMessage(errorBody), response.status, errorBody);
  }
  return body as T;
}

export function prepareCsrf(): Promise<{ csrf_token: string }> {
  return apiRequest<{ csrf_token: string }>("/auth/csrf/");
}

export async function getCurrentUser(): Promise<CurrentUser> {
  return (await apiRequest<AuthResponse>("/auth/me/")).user;
}

export async function loginUser(payload: LoginPayload): Promise<CurrentUser> {
  await prepareCsrf();
  return (await apiRequest<AuthResponse>("/auth/login/", {
    method: "POST",
    body: JSON.stringify(payload),
  })).user;
}

export async function registerUser(payload: RegisterPayload) {
  await prepareCsrf();
  return apiRequest<RegistrationResult>("/auth/register/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function requestVerification(
  channel: "phone" | "email",
  phone: string,
): Promise<AccountOtpRequestResult> {
  await prepareCsrf();
  return apiRequest<AccountOtpRequestResult>(
    `/auth/${channel}-verification/request/`,
    { method: "POST", body: JSON.stringify({ phone }) },
  );
}

export const requestPhoneVerification = (phone: string) =>
  requestVerification("phone", phone);
export const requestEmailVerification = (phone: string) =>
  requestVerification("email", phone);

async function confirmVerification(
  channel: "phone" | "email",
  payload: PhoneCodePayload,
): Promise<CurrentUser> {
  await prepareCsrf();
  return (await apiRequest<AuthResponse>(
    `/auth/${channel}-verification/confirm/`,
    { method: "POST", body: JSON.stringify(payload) },
  )).user;
}

export const confirmPhoneVerification = (payload: PhoneCodePayload) =>
  confirmVerification("phone", payload);
export const confirmEmailVerification = (payload: PhoneCodePayload) =>
  confirmVerification("email", payload);

export async function requestPasswordReset(phone: string) {
  await prepareCsrf();
  return apiRequest<AccountOtpRequestResult>("/auth/password-reset/request/", {
    method: "POST",
    body: JSON.stringify({ phone }),
  });
}

export async function confirmPasswordReset(
  payload: PasswordResetConfirmPayload,
) {
  await prepareCsrf();
  return apiRequest<{ detail: string }>("/auth/password-reset/confirm/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function logoutUser(): Promise<void> {
  await prepareCsrf();
  return apiRequest<void>("/auth/logout/", { method: "POST" });
}
