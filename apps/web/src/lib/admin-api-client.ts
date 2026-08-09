import type { PaginatedPage } from "@/types/domain";

import type {
  AdminAuditLog,
  AdminDashboardMetrics,
  AdminHouse,
  AdminListFilters,
  AdminNotification,
  AdminPayment,
  AdminSeriesPoint,
  AdminSubscription,
  AdminSubscriptionAction,
  AdminTenant,
  AdminUserDetail,
  AdminUserSummary,
} from "@/types/admin";

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

function adminQuery(filters: AdminListFilters = {}) {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.page) params.set("page", String(filters.page));
  if (filters.page_size) params.set("page_size", String(filters.page_size));
  if (filters.role) params.set("role", filters.role);
  if (filters.status) params.set("status", filters.status);
  if (filters.profile) params.set("profile", filters.profile);
  if (filters.plan) params.set("plan", filters.plan);
  if (filters.occupancy) params.set("occupancy", filters.occupancy);
  if (filters.channel) params.set("channel", filters.channel);
  if (filters.action) params.set("action", filters.action);
  if (filters.from) params.set("from", filters.from);
  if (filters.to) params.set("to", filters.to);
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function getAdminDashboard(): Promise<AdminDashboardMetrics> {
  return apiRequest<AdminDashboardMetrics>("/admin/dashboard/");
}

export function getAdminUsersEvolution(
  period: "7d" | "30d" | "3m" | "12m",
): Promise<AdminSeriesPoint[]> {
  return apiRequest<AdminSeriesPoint[]>(
    `/admin/stats/users-evolution/?period=${period}`,
  );
}

export function getAdminHousesEvolution(
  period: "7d" | "30d" | "3m" | "12m",
): Promise<AdminSeriesPoint[]> {
  return apiRequest<AdminSeriesPoint[]>(`/admin/stats/houses/?period=${period}`);
}

export function getAdminRevenueSeries(
  period: "weekly" | "monthly" | "yearly",
): Promise<AdminSeriesPoint[]> {
  return apiRequest<AdminSeriesPoint[]>(`/admin/stats/revenue/?period=${period}`);
}

export function listAdminUsers(
  filters?: AdminListFilters,
): Promise<PaginatedPage<AdminUserSummary>> {
  return apiRequest<PaginatedPage<AdminUserSummary>>(
    `/admin/users/${adminQuery({ page: 1, ...filters })}`,
  );
}

export function getAdminUser(id: string): Promise<AdminUserDetail> {
  return apiRequest<AdminUserDetail>(`/admin/users/${id}/`);
}

export function updateAdminUserStatus(
  id: string,
  isActive: boolean,
): Promise<AdminUserSummary> {
  return apiRequest<AdminUserSummary>(`/admin/users/${id}/status/`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
}

export function listAdminLandlords(
  filters?: AdminListFilters,
): Promise<PaginatedPage<AdminUserSummary>> {
  return apiRequest<PaginatedPage<AdminUserSummary>>(
    `/admin/landlords/${adminQuery({ page: 1, ...filters })}`,
  );
}

export function listAdminTenants(
  filters?: AdminListFilters,
): Promise<PaginatedPage<AdminTenant>> {
  return apiRequest<PaginatedPage<AdminTenant>>(
    `/admin/tenants/${adminQuery({ page: 1, ...filters })}`,
  );
}

export function listAdminHouses(
  filters?: AdminListFilters,
): Promise<PaginatedPage<AdminHouse>> {
  return apiRequest<PaginatedPage<AdminHouse>>(
    `/admin/houses/${adminQuery({ page: 1, ...filters })}`,
  );
}

export function listAdminSubscriptions(
  filters?: AdminListFilters,
): Promise<PaginatedPage<AdminSubscription>> {
  return apiRequest<PaginatedPage<AdminSubscription>>(
    `/admin/subscriptions/${adminQuery({ page: 1, ...filters })}`,
  );
}

export function adminSubscriptionAction(
  id: string,
  payload: AdminSubscriptionAction,
): Promise<AdminSubscription> {
  return apiRequest<AdminSubscription>(`/admin/subscriptions/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function listAdminPayments(
  filters?: AdminListFilters,
): Promise<PaginatedPage<AdminPayment>> {
  return apiRequest<PaginatedPage<AdminPayment>>(
    `/admin/payments/${adminQuery({ page: 1, ...filters })}`,
  );
}

export function listAdminNotifications(
  filters?: AdminListFilters,
): Promise<PaginatedPage<AdminNotification>> {
  return apiRequest<PaginatedPage<AdminNotification>>(
    `/admin/notifications/${adminQuery({ page: 1, ...filters })}`,
  );
}

export function listAdminAuditLogs(
  filters?: AdminListFilters,
): Promise<PaginatedPage<AdminAuditLog>> {
  return apiRequest<PaginatedPage<AdminAuditLog>>(
    `/admin/audit-logs/${adminQuery({ page: 1, ...filters })}`,
  );
}
