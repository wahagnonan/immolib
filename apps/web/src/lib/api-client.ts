import type {
  AuthResponse,
  AccountOtpRequestResult,
  CoOwner,
  CoOwnerInvitation,
  CreateHousePayload,
  CreateLeasePayload,
  CreateTenantPayload,
  CurrentUser,
  DeliveryChannel,
  DirectDeliveryChannel,
  GenerateChargesResult,
  House,
  Lease,
  LoginPayload,
  ManualShareChannel,
  ManualShareResult,
  NotificationPreference,
  NotificationPreferenceUpdate,
  PasswordResetConfirmPayload,
  PhoneCodePayload,
  NotificationDelivery,
  NotificationDeliveryKind,
  NotificationDeliveryStatus,
  OtpRequestResult,
  Payment,
  PaymentStatus,
  PaymentMethodAccount,
  PaymentRequest,
  PaymentRequestStatus,
  CreatePaymentMethodPayload,
  InitiatePaymentRequestPayload,
  ConfirmPaymentRequestPayload,
  PreparePaymentObligationsPayload,
  PreparePaymentObligationsResult,
  RecordPaymentPayload,
  RegisterPayload,
  RegistrationResult,
  RentalDocument,
  RentCharge,
  ShareDocumentResult,
  PushSubscription,
  PublicTenantInvitation,
  Tenant,
  TenantInvitation,
  TenantInvitationShareChannel,
  TenantInvitationShareResult,
  TenantPortalLease,
  TenantPortalOverview,
  InviteCoOwnerPayload,
  CreateMaintenanceIncidentPayload,
  MaintenanceIncident,
  MaintenanceStatus,
  PublicDocumentVerification,
  UpdateCoOwnerPayload,
  DashboardOverview,
  PaginatedPage,
  SecurityDeposit,
  SettleSecurityDepositPayload,
  SubscriptionDetail,
  SubscriptionPlan,
  SubscriptionTransaction,
  UpgradeSubscriptionResult,
} from "@/types/domain";

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

function delay(milliseconds: number) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

// Le backend peut redémarrer en développement (rechargement automatique de
// Django) et le proxy Next.js répond alors 500 ou coupe la connexion. Les
// requêtes en lecture sont relancées avec un délai court, jamais les écritures.
async function fetchWithRetry(
  url: string,
  init: RequestInit,
  maxAttempts = 4,
): Promise<Response> {
  const method = init.method?.toUpperCase() ?? "GET";
  for (let attempt = 1; ; attempt += 1) {
    try {
      const response = await fetch(url, init);
      const retriable =
        method === "GET" &&
        (response.status === 500 ||
          response.status === 502 ||
          response.status === 503 ||
          response.status === 504);
      if (!retriable || attempt >= maxAttempts) return response;
    } catch (networkError) {
      if (attempt >= maxAttempts || method !== "GET") throw networkError;
    }
    await delay(250 * attempt);
  }
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const method = init?.method?.toUpperCase() ?? "GET";
  const token = csrfToken();
  const response = await fetchWithRetry(`${API_BASE_URL}${path}`, {
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

async function apiFile(path: string, init?: RequestInit): Promise<Blob> {
  const method = init?.method?.toUpperCase() ?? "GET";
  const token = csrfToken();
  const response = await fetchWithRetry(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/pdf",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(token && method !== "GET" ? { "X-CSRFToken": token } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorBody | null;
    throw new ApiError(errorMessage(body), response.status, body);
  }

  return response.blob();
}

function unwrapList<T>(data: PaginatedPage<T> | T[]): T[] {
  return Array.isArray(data) ? data : data.results;
}

async function listRequest<T>(path: string): Promise<T[]> {
  const separator = path.includes("?") ? "&" : "?";
  const data = await apiRequest<PaginatedPage<T> | T[]>(
    `${path}${separator}page=1&page_size=100`,
  );
  return unwrapList(data);
}

function queryString(values: Record<string, string | undefined>) {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function listHouses(): Promise<House[]> {
  return listRequest<House>("/houses/");
}

export function createHouse(payload: CreateHousePayload): Promise<House> {
  return apiRequest<House>("/houses/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function prepareCsrf(): Promise<{ csrf_token: string }> {
  return apiRequest<{ csrf_token: string }>("/auth/csrf/");
}

export async function getCurrentUser(): Promise<CurrentUser> {
  const response = await apiRequest<AuthResponse>("/auth/me/");
  return response.user;
}

export async function loginUser(payload: LoginPayload): Promise<CurrentUser> {
  await prepareCsrf();
  const response = await apiRequest<AuthResponse>("/auth/login/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return response.user;
}

export async function registerUser(
  payload: RegisterPayload,
): Promise<RegistrationResult> {
  await prepareCsrf();
  return apiRequest<RegistrationResult>("/auth/register/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function requestPhoneVerification(
  phone: string,
): Promise<AccountOtpRequestResult> {
  await prepareCsrf();
  return apiRequest<AccountOtpRequestResult>(
    "/auth/phone-verification/request/",
    { method: "POST", body: JSON.stringify({ phone }) },
  );
}

export async function confirmPhoneVerification(
  payload: PhoneCodePayload,
): Promise<CurrentUser> {
  await prepareCsrf();
  const response = await apiRequest<AuthResponse>(
    "/auth/phone-verification/confirm/",
    { method: "POST", body: JSON.stringify(payload) },
  );
  return response.user;
}

export async function requestEmailVerification(
  phone: string,
): Promise<AccountOtpRequestResult> {
  await prepareCsrf();
  return apiRequest<AccountOtpRequestResult>(
    "/auth/email-verification/request/",
    { method: "POST", body: JSON.stringify({ phone }) },
  );
}

export async function confirmEmailVerification(
  payload: PhoneCodePayload,
): Promise<CurrentUser> {
  await prepareCsrf();
  const response = await apiRequest<AuthResponse>(
    "/auth/email-verification/confirm/",
    { method: "POST", body: JSON.stringify(payload) },
  );
  return response.user;
}

export async function requestPasswordReset(
  phone: string,
): Promise<AccountOtpRequestResult> {
  await prepareCsrf();
  return apiRequest<AccountOtpRequestResult>("/auth/password-reset/request/", {
    method: "POST",
    body: JSON.stringify({ phone }),
  });
}

export async function confirmPasswordReset(
  payload: PasswordResetConfirmPayload,
): Promise<{ detail: string }> {
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

export function listCoOwners(houseId?: string): Promise<CoOwner[]> {
  return listRequest<CoOwner>(
    `/co-owners/${queryString({ house_id: houseId })}`,
  );
}

export function listCoOwnerInvitations(filters?: {
  houseId?: string;
  status?: string;
}): Promise<CoOwnerInvitation[]> {
  return listRequest<CoOwnerInvitation>(
    `/co-owner-invitations/${queryString({
      house_id: filters?.houseId,
      status: filters?.status,
    })}`,
  );
}

export function inviteCoOwner(
  payload: InviteCoOwnerPayload,
): Promise<CoOwnerInvitation> {
  return apiRequest<CoOwnerInvitation>("/co-owner-invitations/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCoOwner(
  id: string,
  payload: UpdateCoOwnerPayload,
): Promise<CoOwner> {
  return apiRequest<CoOwner>(`/co-owners/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function removeCoOwner(id: string): Promise<void> {
  return apiRequest<void>(`/co-owners/${id}/`, { method: "DELETE" });
}

export function revokeCoOwnerInvitation(
  id: string,
): Promise<CoOwnerInvitation> {
  return apiRequest<CoOwnerInvitation>(
    `/co-owner-invitations/${id}/revoke/`,
    { method: "POST" },
  );
}

export function listTenants(houseId?: string): Promise<Tenant[]> {
  return listRequest<Tenant>(`/tenants/${queryString({ house_id: houseId })}`);
}

export function createTenant(payload: CreateTenantPayload): Promise<Tenant> {
  return apiRequest<Tenant>("/tenants/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listTenantInvitations(filters?: {
  tenantId?: string;
  houseId?: string;
  status?: string;
}): Promise<TenantInvitation[]> {
  return listRequest<TenantInvitation>(
    `/tenant-invitations/${queryString({
      tenant_id: filters?.tenantId,
      house_id: filters?.houseId,
      status: filters?.status,
    })}`,
  );
}

export function createTenantInvitation(
  tenantId: string,
): Promise<TenantInvitation> {
  return apiRequest<TenantInvitation>("/tenant-invitations/", {
    method: "POST",
    body: JSON.stringify({ tenant_id: tenantId }),
  });
}

export function shareTenantInvitation(
  id: string,
  channel: TenantInvitationShareChannel,
): Promise<TenantInvitationShareResult> {
  return apiRequest<TenantInvitationShareResult>(
    `/tenant-invitations/${id}/share/`,
    {
      method: "POST",
      body: JSON.stringify({ channel }),
    },
  );
}

export function revokeTenantInvitation(id: string): Promise<TenantInvitation> {
  return apiRequest<TenantInvitation>(
    `/tenant-invitations/${id}/revoke/`,
    { method: "POST" },
  );
}

export function previewTenantInvitation(
  token: string,
): Promise<PublicTenantInvitation> {
  return apiRequest<PublicTenantInvitation>(
    "/public-tenant-invitations/preview/",
    {
      method: "POST",
      body: JSON.stringify({ token }),
    },
  );
}

export async function claimTenantInvitation(
  token: string,
): Promise<PublicTenantInvitation> {
  await prepareCsrf();
  return apiRequest<PublicTenantInvitation>(
    "/public-tenant-invitations/claim/",
    {
      method: "POST",
      body: JSON.stringify({ token }),
    },
  );
}

export function listLeases(houseId?: string): Promise<Lease[]> {
  return listRequest<Lease>(`/leases/${queryString({ house_id: houseId })}`);
}

export function createLease(payload: CreateLeasePayload): Promise<Lease> {
  return apiRequest<Lease>("/leases/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function activateLease(id: string): Promise<Lease> {
  return apiRequest<Lease>(`/leases/${id}/activate/`, { method: "POST" });
}

export function closeLease(id: string): Promise<Lease> {
  return apiRequest<Lease>(`/leases/${id}/close/`, { method: "POST" });
}

export function listRentCharges(filters?: {
  houseId?: string;
  leaseId?: string;
  period?: string;
}): Promise<RentCharge[]> {
  return listRequest<RentCharge>(
    `/rent-charges/${queryString({
      house_id: filters?.houseId,
      lease_id: filters?.leaseId,
      period: filters?.period,
    })}`,
  );
}

export function listRentChargesPage(filters?: {
  page?: number;
  pageSize?: number;
  period?: string;
  periodFrom?: string;
  periodTo?: string;
}): Promise<PaginatedPage<RentCharge>> {
  return apiRequest<PaginatedPage<RentCharge>>(
    `/rent-charges/${queryString({
      page: String(filters?.page ?? 1),
      page_size: String(filters?.pageSize ?? 25),
      period: filters?.period,
      period_from: filters?.periodFrom,
      period_to: filters?.periodTo,
    })}`,
  );
}

export function generateRentCharges(period: string): Promise<GenerateChargesResult> {
  return apiRequest<GenerateChargesResult>("/rent-charges/generate/", {
    method: "POST",
    body: JSON.stringify({ period }),
  });
}

export function listLeaseObligations(leaseId?: string): Promise<RentCharge[]> {
  return listRequest<RentCharge>(
    `/lease-obligations/${queryString({
      lease_id: leaseId,
      unpaid_only: "true",
    })}`,
  );
}

export function preparePaymentObligations(
  payload: PreparePaymentObligationsPayload,
): Promise<PreparePaymentObligationsResult> {
  return apiRequest<PreparePaymentObligationsResult>(
    "/lease-obligations/prepare-payment/",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function listPayments(rentChargeId?: string): Promise<Payment[]> {
  return listRequest<Payment>(
    `/payments/${queryString({ rent_charge_id: rentChargeId })}`,
  );
}

export function listPaymentsPage(filters?: {
  page?: number;
  pageSize?: number;
  receivedFrom?: string;
  receivedTo?: string;
}): Promise<PaginatedPage<Payment>> {
  return apiRequest<PaginatedPage<Payment>>(
    `/payments/${queryString({
      page: String(filters?.page ?? 1),
      page_size: String(filters?.pageSize ?? 25),
      received_from: filters?.receivedFrom,
      received_to: filters?.receivedTo,
    })}`,
  );
}

export function listSecurityDeposits(): Promise<SecurityDeposit[]> {
  return listRequest<SecurityDeposit>("/security-deposits/");
}

export function settleSecurityDeposit(
  id: string,
  payload: SettleSecurityDepositPayload,
): Promise<SecurityDeposit> {
  return apiRequest<SecurityDeposit>(`/security-deposits/${id}/settle/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listMaintenanceIncidents(filters?: {
  houseId?: string;
  status?: MaintenanceStatus;
  priority?: string;
}): Promise<MaintenanceIncident[]> {
  return listRequest<MaintenanceIncident>(
    `/incidents/${queryString({
      house_id: filters?.houseId,
      status: filters?.status,
      priority: filters?.priority,
    })}`,
  );
}

export function createMaintenanceIncident(
  payload: CreateMaintenanceIncidentPayload,
): Promise<MaintenanceIncident> {
  return apiRequest<MaintenanceIncident>("/incidents/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function setMaintenanceIncidentStatus(
  id: string,
  status: MaintenanceStatus,
  message = "",
): Promise<MaintenanceIncident> {
  return apiRequest<MaintenanceIncident>(`/incidents/${id}/set-status/`, {
    method: "POST",
    body: JSON.stringify({ status, message }),
  });
}

export function commentOnMaintenanceIncident(
  id: string,
  message: string,
): Promise<MaintenanceIncident> {
  return apiRequest<MaintenanceIncident>(`/incidents/${id}/comment/`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export function recordPayment(payload: RecordPaymentPayload): Promise<Payment> {
  return apiRequest<Payment>("/payments/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function cancelPayment(id: string, reason: string): Promise<Payment> {
  return apiRequest<Payment>(`/payments/${id}/cancel/`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function listPaymentMethods(): Promise<PaymentMethodAccount[]> {
  return listRequest<PaymentMethodAccount>("/payment-methods/");
}

export function createPaymentMethod(
  payload: CreatePaymentMethodPayload,
): Promise<PaymentMethodAccount> {
  return apiRequest<PaymentMethodAccount>("/payment-methods/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deletePaymentMethod(id: string): Promise<void> {
  return apiRequest<void>(`/payment-methods/${id}/`, {
    method: "DELETE",
  });
}

export function setDefaultPaymentMethod(id: string): Promise<PaymentMethodAccount> {
  return apiRequest<PaymentMethodAccount>(`/payment-methods/${id}/make-default/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function listLandlordPaymentRequests(
  status?: PaymentRequestStatus,
): Promise<PaymentRequest[]> {
  return listRequest<PaymentRequest>(
    `/payment-requests/${queryString({ status })}`,
  );
}

export function listMyPaymentRequests(
  status?: PaymentRequestStatus,
): Promise<PaymentRequest[]> {
  return listRequest<PaymentRequest>(
    `/payment-requests/my/${queryString({ status })}`,
  );
}

export function initiatePayment(
  payload: InitiatePaymentRequestPayload,
): Promise<PaymentRequest> {
  return apiRequest<PaymentRequest>("/payment-requests/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function confirmPaymentRequest(
  id: string,
  payload: ConfirmPaymentRequestPayload = {},
): Promise<PaymentRequest> {
  return apiRequest<PaymentRequest>(`/payment-requests/${id}/confirm/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function refusePaymentRequest(
  id: string,
  reason: string,
): Promise<PaymentRequest> {
  return apiRequest<PaymentRequest>(`/payment-requests/${id}/refuse/`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function cancelPaymentRequest(
  id: string,
  reason = "",
): Promise<PaymentRequest> {
  return apiRequest<PaymentRequest>(`/payment-requests/${id}/cancel/`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function initiatePiSpiPayment(id: string): Promise<{
  payment_request: PaymentRequest;
  external_transaction_id: string;
  provider_status: string;
  created: boolean;
}> {
  return apiRequest<{
    payment_request: PaymentRequest;
    external_transaction_id: string;
    provider_status: string;
    created: boolean;
  }>(`/payment-requests/${id}/initiate-pi-spi/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function getPiSpiStatus(id: string): Promise<PaymentRequest> {
  return apiRequest<PaymentRequest>(`/payment-requests/${id}/pi-spi-status/`);
}

export function getTenantPortalOverview(): Promise<TenantPortalOverview> {
  return apiRequest<TenantPortalOverview>("/tenant-portal/overview/");
}

export function listTenantPortalLeases(): Promise<TenantPortalLease[]> {
  return listRequest<TenantPortalLease>("/tenant-portal/leases/");
}

export function listTenantPortalCharges(): Promise<RentCharge[]> {
  return listRequest<RentCharge>("/tenant-portal/charges/");
}

export function listTenantPortalPayments(): Promise<Payment[]> {
  return listRequest<Payment>("/tenant-portal/payments/");
}

export function confirmTenantPortalPayment(id: string): Promise<Payment> {
  return apiRequest<Payment>(`/tenant-portal/payments/${id}/confirm/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function disputeTenantPortalPayment(
  id: string,
  reason: string,
): Promise<Payment> {
  return apiRequest<Payment>(`/tenant-portal/payments/${id}/dispute/`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function listTenantPortalDocuments(): Promise<RentalDocument[]> {
  return listRequest<RentalDocument>("/tenant-portal/documents/");
}

export function listTenantPortalIncidents(): Promise<MaintenanceIncident[]> {
  return listRequest<MaintenanceIncident>("/tenant-portal/incidents/");
}

export function createTenantPortalIncident(
  payload: CreateMaintenanceIncidentPayload,
): Promise<MaintenanceIncident> {
  return apiRequest<MaintenanceIncident>("/tenant-portal/incidents/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function commentOnTenantPortalIncident(
  id: string,
  message: string,
): Promise<MaintenanceIncident> {
  return apiRequest<MaintenanceIncident>(
    `/tenant-portal/incidents/${id}/comment/`,
    {
      method: "POST",
      body: JSON.stringify({ message }),
    },
  );
}

export function respondToTenantPortalIncident(
  id: string,
  action: "CLOSE" | "REOPEN",
  message = "",
): Promise<MaintenanceIncident> {
  return apiRequest<MaintenanceIncident>(
    `/tenant-portal/incidents/${id}/respond/`,
    {
      method: "POST",
      body: JSON.stringify({ action, message }),
    },
  );
}

export function downloadTenantPortalDocumentPdf(id: string): Promise<Blob> {
  return apiFile(`/tenant-portal/documents/${id}/pdf/`);
}

export function listDocuments(): Promise<RentalDocument[]> {
  return listRequest<RentalDocument>("/documents/");
}

export function listDocumentsPage(filters?: {
  page?: number;
  pageSize?: number;
  documentType?: RentalDocument["document_type"];
  issuedFrom?: string;
  issuedTo?: string;
}): Promise<PaginatedPage<RentalDocument>> {
  return apiRequest<PaginatedPage<RentalDocument>>(
    `/documents/${queryString({
      page: String(filters?.page ?? 1),
      page_size: String(filters?.pageSize ?? 25),
      document_type: filters?.documentType,
      issued_from: filters?.issuedFrom,
      issued_to: filters?.issuedTo,
    })}`,
  );
}

export function getDashboardOverview(): Promise<DashboardOverview> {
  return apiRequest<DashboardOverview>("/dashboard/overview/");
}

export function downloadDocumentPdf(id: string): Promise<Blob> {
  return apiFile(`/documents/${id}/pdf/`);
}

export function listNotificationDeliveries(filters?: {
  documentId?: string;
  rentChargeId?: string;
  status?: NotificationDeliveryStatus;
  kind?: NotificationDeliveryKind;
}): Promise<NotificationDelivery[]> {
  return listRequest<NotificationDelivery>(
    `/notification-deliveries/${queryString({
      document_id: filters?.documentId,
      rent_charge_id: filters?.rentChargeId,
      status: filters?.status,
      kind: filters?.kind,
    })}`,
  );
}

export function shareDocument(
  id: string,
  channels: DirectDeliveryChannel[],
): Promise<ShareDocumentResult> {
  return apiRequest<ShareDocumentResult>(`/documents/${id}/share/`, {
    method: "POST",
    body: JSON.stringify({ channels }),
  });
}

export function prepareManualDocumentShare(
  id: string,
  channel: ManualShareChannel,
): Promise<ManualShareResult> {
  return apiRequest<ManualShareResult>(`/documents/${id}/manual-share/`, {
    method: "POST",
    body: JSON.stringify({ channel }),
  });
}

export function getNotificationPreference(): Promise<NotificationPreference> {
  return apiRequest<NotificationPreference>("/notification-preferences/");
}

export function updateNotificationPreference(
  payload: NotificationPreferenceUpdate,
): Promise<NotificationPreference> {
  return apiRequest<NotificationPreference>("/notification-preferences/", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function listPushSubscriptions(): Promise<PushSubscription[]> {
  return listRequest<PushSubscription>("/push-subscriptions/");
}

export function registerPushSubscription(
  token: string,
  deviceName: string,
): Promise<PushSubscription> {
  return apiRequest<PushSubscription>("/push-subscriptions/", {
    method: "POST",
    body: JSON.stringify({ token, device_name: deviceName }),
  });
}

export function deactivatePushSubscription(token: string): Promise<void> {
  return apiRequest<void>("/push-subscriptions/", {
    method: "DELETE",
    body: JSON.stringify({ token }),
  });
}

export function requestDocumentOtp(
  accessToken: string,
  channel: DeliveryChannel,
): Promise<OtpRequestResult> {
  return apiRequest<OtpRequestResult>("/public-access/request-otp/", {
    method: "POST",
    body: JSON.stringify({ access_token: accessToken, channel }),
  });
}

export function verifyDocumentOtp(challengeId: string, code: string) {
  return apiRequest<{ grant_token: string }>("/public-access/verify-otp/", {
    method: "POST",
    body: JSON.stringify({ challenge_id: challengeId, code }),
  });
}

export function viewPublicDocument(grantToken: string): Promise<RentalDocument> {
  return apiRequest<RentalDocument>("/public-access/view-document/", {
    method: "POST",
    body: JSON.stringify({ grant_token: grantToken }),
  });
}

export function downloadPublicDocumentPdf(grantToken: string): Promise<Blob> {
  return apiFile("/public-access/download-document/", {
    method: "POST",
    body: JSON.stringify({ grant_token: grantToken }),
  });
}

export function verifyDocumentReference(
  reference: string,
): Promise<PublicDocumentVerification> {
  return apiRequest<PublicDocumentVerification>(
    `/public-access/verify-reference/${queryString({ reference })}`,
  );
}

export function respondToPayment(
  grantToken: string,
  action: "CONFIRM" | "DISPUTE",
  reason?: string,
): Promise<{ id: string; status: PaymentStatus; status_label: string; updated_at: string }> {
  return apiRequest("/public-access/payment-response/", {
    method: "POST",
    body: JSON.stringify({ grant_token: grantToken, action, reason }),
  });
}

export function getSubscription(): Promise<SubscriptionDetail> {
  return apiRequest<SubscriptionDetail>("/subscription/");
}

export function listSubscriptionPlans(): Promise<SubscriptionPlan[]> {
  return listRequest<SubscriptionPlan>("/subscription/plans/");
}

export function upgradeSubscription(
  planSlug: string,
): Promise<UpgradeSubscriptionResult> {
  return apiRequest<UpgradeSubscriptionResult>("/subscription/upgrade/", {
    method: "POST",
    body: JSON.stringify({ plan_slug: planSlug }),
  });
}

export function cancelSubscription(): Promise<{
  status: string;
  status_label: string;
}> {
  return apiRequest("/subscription/cancel/", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function refreshSubscriptionTransaction(
  transactionId: string,
): Promise<SubscriptionTransaction> {
  return apiRequest<SubscriptionTransaction>(
    `/subscription/transactions/${transactionId}/refresh/`,
  );
}
