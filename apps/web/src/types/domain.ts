export type Owner = {
  id: string;
  phone: string;
  full_name: string;
};

export type CurrentUser = Owner & {
  email: string;
  first_name: string;
  last_name: string;
  phone_verified_at: string | null;
  email_verified_at: string | null;
  has_verified_contact: boolean;
  has_owner_access: boolean;
  has_tenant_access: boolean;
  created_at: string;
  subscription: SubscriptionSummary | null;
};

export type SubscriptionStatus = "ACTIVE" | "PENDING" | "EXPIRED" | "CANCELLED";

export type SubscriptionSummary = {
  plan_slug: string;
  plan_name: string;
  price_monthly: number;
  currency: string;
  status: SubscriptionStatus;
  expires_at: string | null;
  house_count: number;
  max_houses: number | null;
  features: string[];
};

export type SubscriptionPlan = {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  price_monthly: number;
  currency: string;
  max_houses: number | null;
  features: string[];
  is_active: boolean;
};

export type SubscriptionTransactionStatus =
  | "PENDING"
  | "SUCCESSFUL"
  | "FAILED"
  | "CANCELLED"
  | "EXPIRED";

export type SubscriptionTransaction = {
  id: string;
  plan_slug: string;
  plan_name: string;
  amount: number;
  currency: string;
  status: SubscriptionTransactionStatus;
  status_label: string;
  provider: string;
  provider_reference: string | null;
  completed_at: string | null;
  created_at: string;
};

export type SubscriptionDetail = {
  plan: SubscriptionPlan;
  status: SubscriptionStatus;
  status_label: string;
  started_at: string;
  expires_at: string | null;
  house_count: number;
  max_houses: number | null;
  remaining_houses: number | null;
  features: string[];
  pending_transaction: SubscriptionTransaction | null;
};

export type UpgradeSubscriptionResult = {
  transaction: SubscriptionTransaction;
  redirect_url: string | null;
  activated: boolean;
};

export type AuthResponse = {
  user: CurrentUser;
};

export type LoginPayload = {
  email: string;
  password: string;
};

export type RegisterPayload = LoginPayload & {
  phone: string;
  password_confirmation: string;
  first_name?: string;
  last_name?: string;
  tenant_invitation_token?: string;
};

export type AccountOtpRequestResult = {
  detail: string;
  otp_code?: string;
  verification_channel?: "EMAIL" | "SMS";
  masked_destination?: string;
};

export type RegistrationResult = AuthResponse &
  AccountOtpRequestResult & {
    verification_required: boolean;
    verification_channel: "EMAIL" | "SMS";
  };

export type PhoneCodePayload = {
  phone: string;
  code: string;
};

export type PasswordResetConfirmPayload = PhoneCodePayload & {
  password: string;
  password_confirmation: string;
};

export type OwnershipAccessLevel = "ACTIVE" | "OBSERVER";

export type Ownership = {
  id: string;
  user: Owner;
  role: "PRIMARY" | "CO_OWNER";
  role_label: string;
  access_level: OwnershipAccessLevel;
  access_level_label: string;
  ownership_percentage: string | null;
};

export type CoOwner = Ownership & {
  house_id: string;
  house_name: string;
  created_at: string;
};

export type CoOwnerInvitationStatus =
  | "PENDING"
  | "ACCEPTED"
  | "REVOKED"
  | "EXPIRED";

export type CoOwnerInvitation = {
  id: string;
  house_id: string;
  house_name: string;
  phone: string;
  email: string;
  ownership_percentage: string | null;
  access_level: OwnershipAccessLevel;
  access_level_label: string;
  status: CoOwnerInvitationStatus;
  status_label: string;
  is_expired: boolean;
  invited_by: Owner;
  accepted_by: Owner | null;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  created_at: string;
  updated_at: string;
};

export type InviteCoOwnerPayload = {
  house_id: string;
  phone: string;
  email?: string;
  ownership_percentage?: string | null;
  access_level?: OwnershipAccessLevel;
};

export type UpdateCoOwnerPayload = {
  ownership_percentage?: string | null;
  access_level?: OwnershipAccessLevel;
};

export type HouseStatus = "VACANT" | "OCCUPIED" | "UNAVAILABLE";

export type PropertyType = "HOUSE" | "APARTMENT" | "LAND" | "COMMERCIAL";

export type House = {
  id: string;
  name: string;
  address: string;
  commune: string;
  city: string;
  landmark: string;
  property_type: PropertyType;
  property_type_label: string;
  status: HouseStatus;
  status_label: string;
  ownerships: Ownership[];
  created_at: string;
  updated_at: string;
};

export type CreateHousePayload = {
  name: string;
  address: string;
  commune?: string;
  city: string;
  landmark?: string;
  property_type?: PropertyType;
};

export type TenantStatus = "UNREGISTERED" | "INVITED" | "ACTIVE" | "BLOCKED";

export type Tenant = {
  id: string;
  house_id: string;
  full_name: string;
  phone: string;
  email: string;
  status: TenantStatus;
  status_label: string;
  has_account: boolean;
  created_at: string;
  updated_at: string;
};

export type CreateTenantPayload = {
  house_id: string;
  full_name: string;
  phone: string;
  email?: string;
};

export type TenantInvitationStatus =
  | "PENDING"
  | "ACCEPTED"
  | "REVOKED"
  | "EXPIRED";

export type TenantInvitation = {
  id: string;
  tenant_id: string;
  tenant_name: string;
  house_id: string;
  house_name: string;
  status: TenantInvitationStatus;
  status_label: string;
  secure_url: string;
  is_expired: boolean;
  claimed_by_id: string | null;
  accepted_by_id: string | null;
  expires_at: string;
  claimed_at: string | null;
  accepted_at: string | null;
  revoked_at: string | null;
  created_at: string;
  updated_at: string;
};

export type TenantInvitationShareChannel =
  | ManualShareChannel
  | "EMAIL_AUTOMATIC";

export type TenantInvitationShareResult = {
  invitation: TenantInvitation;
  secure_url: string;
  subject: string;
  message: string;
  action_url: string;
  channel: TenantInvitationShareChannel;
  delivery: {
    id: string;
    channel: "EMAIL";
    status: NotificationDeliveryStatus;
  } | null;
  share_event_id: string | null;
};

export type PublicTenantInvitation = {
  tenant_name: string;
  phone: string;
  email: string;
  house_name: string;
  house_address: string;
  owner_name: string;
  status: TenantInvitationStatus;
  status_label: string;
  is_expired: boolean;
  expires_at: string;
};

export type LeaseStatus = "DRAFT" | "ACTIVE" | "ENDED" | "CANCELLED";

export type Lease = {
  id: string;
  house_id: string;
  tenant: Tenant;
  status: LeaseStatus;
  status_label: string;
  start_date: string;
  end_date: string | null;
  monthly_rent: string;
  monthly_charges: string;
  due_day: number;
  security_deposit: string;
  rent_advance: string;
  currency: string;
  accepts_mobile_money: boolean;
  accepts_cash: boolean;
  activated_at: string | null;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateLeasePayload = {
  house_id: string;
  tenant_id: string;
  start_date: string;
  end_date?: string | null;
  monthly_rent: string;
  monthly_charges?: string;
  due_day: number;
  security_deposit?: string;
  rent_advance?: string;
  accepts_mobile_money?: boolean;
  accepts_cash?: boolean;
};

export type RentChargeStatus =
  | "UPCOMING"
  | "DUE"
  | "PARTIALLY_PAID"
  | "PAID"
  | "OVERDUE"
  | "DISPUTED"
  | "CANCELLED";

export type RentCharge = {
  id: string;
  lease_id: string;
  house_id: string;
  house_name: string;
  tenant_id: string;
  tenant_name: string;
  obligation_type: "RENT" | "SECURITY_DEPOSIT";
  obligation_type_label: string;
  obligation_label: string;
  period: string;
  period_start: string;
  period_end: string;
  due_date: string;
  rent_amount: string;
  charges_amount: string;
  amount_due: string;
  amount_paid: string;
  amount_released: string;
  balance_due: string;
  held_balance: string;
  deposit_state:
    | ""
    | "EXPECTED"
    | "PARTIALLY_HELD"
    | "HELD"
    | "PARTIALLY_SETTLED"
    | "SETTLED";
  currency: string;
  status: RentChargeStatus;
  status_label: string;
  generated_at: string;
  updated_at: string;
};

export type GenerateChargesResult = {
  created: number;
  existing: number;
  charges: RentCharge[];
};

export type PreparePaymentObligationsPayload = {
  lease_id: string;
  period_start?: string;
  period_end?: string;
  include_security_deposit: boolean;
};

export type PreparePaymentObligationsResult = {
  created: number;
  existing: number;
  obligations: RentCharge[];
};

export type PaymentMethod =
  | "CASH"
  | "BANK_TRANSFER"
  | "MOBILE_MONEY"
  | "EXTERNAL_MOBILE_MONEY"
  | "PI_SPI"
  | "SECURITY_DEPOSIT_APPLICATION"
  | "OTHER";

export type PaymentStatus =
  | "RECORDED_BY_OWNER"
  | "CONFIRMED_BY_TENANT"
  | "CONFIRMED_BY_PROVIDER"
  | "DISPUTED_BY_TENANT"
  | "CANCELLED";

export type PaymentAllocation = {
  id: string;
  rent_charge_id: string;
  obligation_id: string;
  obligation_type: "RENT" | "SECURITY_DEPOSIT";
  obligation_label: string;
  period: string;
  house_name: string;
  tenant_name: string;
  amount: string;
  created_at: string;
};

export type PaymentEvent = {
  id: string;
  event_type: string;
  event_label: string;
  reason: string;
  created_at: string;
};

export type Payment = {
  id: string;
  amount: string;
  currency: string;
  method: PaymentMethod;
  method_label: string;
  status: PaymentStatus;
  status_label: string;
  received_at: string;
  external_reference: string;
  note: string;
  is_cash_movement: boolean;
  idempotency_key: string;
  allocations: PaymentAllocation[];
  events: PaymentEvent[];
  created_at: string;
  updated_at: string;
};

export type RecordPaymentPayload = {
  rent_charge_id?: string;
  allocations?: Array<{
    obligation_id: string;
    amount: string;
  }>;
  amount: string;
  method: PaymentMethod;
  received_at?: string;
  external_reference?: string;
  note?: string;
  idempotency_key: string;
};

export type PaymentRequestOperator =
  | "MTN_MOMO"
  | "ORANGE_MONEY"
  | "MOOV_MONEY"
  | "WAVE"
  | "BANK_TRANSFER"
  | "PI_SPI"
  | "CASH"
  | "OTHER";

export type PaymentRequestStatus =
  | "PENDING"
  | "PROCESSING"
  | "CONFIRMED"
  | "NOT_RECEIVED"
  | "CANCELLED"
  | "FAILED"
  | "EXPIRED";

export type PaymentRequest = {
  id: string;
  reference: string;
  amount: string;
  amount_received: string | null;
  currency: string;
  rent_charge_id: string;
  lease_id: string;
  house_id: string;
  house_name: string;
  tenant_id: string;
  tenant_name: string;
  period: string;
  charge_status: string;
  charge_balance_due: string;
  operator: PaymentRequestOperator;
  operator_label: string;
  method_account: PaymentMethodAccountBrief | null;
  payee_name: string;
  payee_phone: string;
  status: PaymentRequestStatus;
  status_label: string;
  note: string;
  processing_note: string;
  payment_id: string | null;
  external_transaction_id: string | null;
  provider: string | null;
  provider_status: string | null;
  provider_reference: string | null;
  failure_reason: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
};

export type PaymentMethodAccountBrief = {
  id: string;
  operator: PaymentRequestOperator;
  operator_label: string;
  account_identifier: string;
  account_holder: string;
};

export type PaymentMethodAccount = PaymentMethodAccountBrief & {
  is_default: boolean;
  created_at: string;
  updated_at: string;
};

export type InitiatePaymentRequestPayload = {
  rent_charge_id: string;
  amount: string;
  operator: PaymentRequestOperator;
  method_account_id?: string | null;
  note?: string;
};

export type ConfirmPaymentRequestPayload = {
  received_amount?: string;
  note?: string;
};

export type RefusePaymentRequestPayload = {
  reason: string;
};

export type CancelPaymentRequestPayload = {
  reason?: string;
};

export type CreatePaymentMethodPayload = {
  operator: PaymentRequestOperator;
  account_identifier: string;
  account_holder?: string;
  is_default?: boolean;
};

export type TenantPortalHouse = {
  id: string;
  name: string;
  address: string;
  commune: string;
  city: string;
};

export type TenantPortalProfile = {
  id: string;
  full_name: string;
  phone: string;
  email: string;
  status: "ACTIVE";
  house: TenantPortalHouse;
  owner: Owner | null;
};

export type TenantPortalLease = {
  id: string;
  tenant_id: string;
  tenant_name: string;
  house: TenantPortalHouse;
  status: "ACTIVE" | "ENDED";
  status_label: string;
  start_date: string;
  end_date: string | null;
  monthly_rent: string;
  monthly_charges: string;
  due_day: number;
  security_deposit: string;
  rent_advance: string;
  currency: string;
  accepts_mobile_money: boolean;
  accepts_cash: boolean;
  activated_at: string | null;
  ended_at: string | null;
};

export type TenantPortalOverview = {
  has_profile: boolean;
  profiles: TenantPortalProfile[];
  active_leases: TenantPortalLease[];
  next_charge: RentCharge | null;
  balances: Array<{
    currency: string;
    amount: string;
  }>;
  overdue_charge_count: number;
  payment_to_review_count: number;
  document_count: number;
};

export type RentalDocumentType =
  | "PAYMENT_RECEIPT"
  | "RENT_RECEIPT"
  | "DEPOSIT_RECEIPT"
  | "DEPOSIT_SETTLEMENT";

export type RentalDocument = {
  id: string;
  reference: string;
  document_type: RentalDocumentType;
  document_type_label: string;
  status: "ACTIVE" | "VOIDED";
  status_label: string;
  payment_id: string | null;
  deposit_movement_id: string | null;
  rent_charge_id: string;
  amount: string;
  currency: string;
  period: string;
  period_start: string;
  period_end: string;
  payment_method: string;
  breakdown: Array<{
    obligation_id?: string;
    type: string;
    label: string;
    period?: string;
    amount: string;
    reason?: string;
    agreement_reference?: string;
    target?: string;
  }>;
  house_name: string;
  house_address: string;
  tenant_name: string;
  owner_name: string;
  issued_at: string;
  voided_at: string | null;
  void_reason: string;
};

export type PublicDocumentVerification = {
  authentic: boolean;
  reference: string;
  document_type: RentalDocumentType;
  document_type_label: string;
  status: "ACTIVE" | "VOIDED";
  status_label: string;
  amount: string;
  currency: string;
  period: string;
  period_start: string;
  period_end: string;
  issued_at: string;
  voided_at: string | null;
};

export type PaginatedPage<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type SecurityDepositMovementType =
  | "REFUND"
  | "RETENTION"
  | "APPLY_TO_RENT";

export type SecurityDepositMovement = {
  id: string;
  movement_type: SecurityDepositMovementType;
  movement_type_label: string;
  amount: string;
  reason: string;
  agreement_confirmed: boolean;
  agreement_reference: string;
  target_rent_charge_id: string | null;
  target_label: string | null;
  resulting_payment_id: string | null;
  document_id: string | null;
  document_reference: string;
  occurred_at: string;
  created_at: string;
};

export type SecurityDeposit = {
  id: string;
  lease_id: string;
  house_id: string;
  house_name: string;
  tenant_name: string;
  amount_due: string;
  amount_paid: string;
  amount_released: string;
  held_balance: string;
  deposit_state: Exclude<RentCharge["deposit_state"], "">;
  deposit_state_label: string;
  currency: string;
  status: RentChargeStatus;
  movements: SecurityDepositMovement[];
};

export type SettleSecurityDepositPayload = {
  movement_type: SecurityDepositMovementType;
  amount: string;
  reason?: string;
  agreement_confirmed?: boolean;
  agreement_reference?: string;
  target_rent_charge_id?: string | null;
  idempotency_key: string;
  occurred_at?: string;
};

export type MonthlyCollection = {
  period: string;
  expected: string;
  collected: string;
};

export type DashboardOverview = {
  period: string;
  currency: string;
  houses: {
    total: number;
    occupied: number;
    vacant: number;
  };
  collection: {
    expected: string;
    collected: string;
    remaining: string;
    rate: number;
    attention_count: number;
  };
  priority_charges: RentCharge[];
  recent_payments: Payment[];
  monthly_collection: MonthlyCollection[];
};

export type MaintenanceCategory =
  | "PLUMBING"
  | "ELECTRICITY"
  | "SECURITY"
  | "ROOF"
  | "STRUCTURE"
  | "EQUIPMENT"
  | "OTHER";

export type MaintenancePriority = "LOW" | "NORMAL" | "HIGH" | "URGENT";

export type MaintenanceStatus =
  | "REPORTED"
  | "ACKNOWLEDGED"
  | "IN_PROGRESS"
  | "RESOLVED"
  | "CLOSED"
  | "CANCELLED";

export type MaintenanceEvent = {
  id: string;
  event_type: "REPORTED" | "STATUS_CHANGED" | "COMMENTED";
  event_label: string;
  actor_role: "OWNER" | "TENANT";
  actor_role_label: string;
  actor_name: string;
  from_status: MaintenanceStatus | "";
  from_status_label: string;
  to_status: MaintenanceStatus | "";
  to_status_label: string;
  message: string;
  created_at: string;
};

export type MaintenanceIncident = {
  id: string;
  house_id: string;
  house_name: string;
  house_address: string;
  lease_id: string;
  tenant_id: string;
  tenant_name: string;
  title: string;
  description: string;
  category: MaintenanceCategory;
  category_label: string;
  priority: MaintenancePriority;
  priority_label: string;
  status: MaintenanceStatus;
  status_label: string;
  occurred_at: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  events: MaintenanceEvent[];
  created_at: string;
  updated_at: string;
};

export type CreateMaintenanceIncidentPayload = {
  lease_id: string;
  title: string;
  description: string;
  category: MaintenanceCategory;
  priority?: MaintenancePriority;
  occurred_at?: string | null;
};

export type DeliveryChannel = "SMS" | "EMAIL" | "WHATSAPP" | "PUSH";
export type DirectDeliveryChannel = Exclude<DeliveryChannel, "PUSH">;
export type ManualShareChannel =
  | "WHATSAPP"
  | "EMAIL"
  | "SMS"
  | "NATIVE"
  | "COPY";

export type NotificationDeliveryStatus =
  | "QUEUED"
  | "PROCESSING"
  | "SENT"
  | "FAILED";

export type NotificationDeliveryKind =
  | "DOCUMENT_LINK"
  | "OTP"
  | "RENT_REMINDER"
  | "TENANT_INVITATION";

export type NotificationDelivery = {
  id: string;
  access_link_id: string | null;
  rent_charge_id: string | null;
  document_id: string | null;
  document_reference: string | null;
  context_label: string;
  house_name: string;
  tenant_name: string;
  period: string;
  kind: NotificationDeliveryKind;
  kind_label: string;
  channel: DeliveryChannel;
  channel_label: string;
  masked_destination: string;
  status: NotificationDeliveryStatus;
  status_label: string;
  attempt_count: number;
  last_attempt_at: string | null;
  next_attempt_at: string | null;
  scheduled_for: string | null;
  sent_at: string | null;
  provider_reference: string;
  failure_reason: string;
  created_at: string;
};

export type ShareDocumentResult = {
  access_link_id: string;
  secure_url: string;
  expires_at: string;
  deliveries: Array<{
    channel: DeliveryChannel;
    status: NotificationDeliveryStatus;
  }>;
};

export type ManualShareResult = {
  event_id: string;
  access_link_id: string;
  secure_url: string;
  expires_at: string;
  subject: string;
  message: string;
  action_url: string;
  channel: ManualShareChannel;
};

export type PreferredNotificationChannel =
  | "AUTO"
  | "PUSH"
  | "EMAIL"
  | "WHATSAPP"
  | "SMS";

export type NotificationPreference = {
  preferred_channel: PreferredNotificationChannel;
  push_enabled: boolean;
  email_enabled: boolean;
  whatsapp_enabled: boolean;
  sms_enabled: boolean;
  whatsapp_opted_in_at: string | null;
  available_channels: DeliveryChannel[];
  email: string;
  email_verified: boolean;
  active_push_devices: number;
  updated_at: string;
};

export type NotificationPreferenceUpdate = Partial<
  Pick<
    NotificationPreference,
    | "preferred_channel"
    | "push_enabled"
    | "email_enabled"
    | "whatsapp_enabled"
    | "sms_enabled"
  >
> & { whatsapp_opt_in?: boolean };

export type PushSubscription = {
  id: string;
  platform: "WEB";
  device_name: string;
  token_suffix: string;
  is_active: boolean;
  last_seen_at: string;
  created_at: string;
};

export type OtpRequestResult = {
  challenge_id: string;
  masked_destination: string;
  expires_at: string;
  otp_code?: string;
};
