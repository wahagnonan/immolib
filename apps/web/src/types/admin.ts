export type AdminUserRole = "ADMIN" | "USER";

export type AdminUserSummary = {
  id: string;
  role: AdminUserRole;
  full_name: string;
  phone: string;
  email: string;
  is_active: boolean;
  date_joined: string;
  last_login: string | null;
  created_at: string;
  houses_count: number;
  tenants_count: number;
  plan_slug: string | null;
  plan_name: string | null;
  subscription_status: string | null;
};

export type AdminUserDetail = AdminUserSummary & {
  first_name: string;
  last_name: string;
  phone_verified_at: string | null;
  email_verified_at: string | null;
};

export type AdminTenant = {
  id: string;
  full_name: string;
  phone: string;
  email: string;
  status: string;
  property_id: string;
  property_name: string;
  linked_user_id: string | null;
  linked_user_phone: string | null;
  created_at: string;
};

export type AdminHouse = {
  id: string;
  name: string;
  address: string;
  commune: string;
  city: string;
  status: string;
  property_type: string;
  primary_owner_name: string;
  current_tenant_name: string | null;
  has_active_lease: boolean;
  created_at: string;
};

export type AdminSubscription = {
  id: string;
  user_id: string;
  user_full_name: string;
  user_phone: string;
  user_email: string;
  plan_slug: string;
  plan_name: string;
  price_monthly: number;
  currency: string;
  status: string;
  started_at: string | null;
  expires_at: string | null;
  houses_count: number;
  max_houses: number;
  created_at: string;
};

export type AdminSubscriptionAction =
  | { action: "change_plan"; plan_slug: string }
  | { action: "extend"; days: number }
  | { action: "activate"; plan_slug?: string; days?: number }
  | { action: "cancel" };

export type AdminPayment = {
  id: string;
  user_id: string;
  user_full_name: string;
  user_phone: string;
  plan_slug: string;
  plan_name: string;
  amount: number;
  currency: string;
  status: string;
  provider: string;
  completed_at: string | null;
  created_at: string;
};

export type AdminNotification = {
  id: string;
  kind: string;
  channel: string;
  destination: string;
  status: string;
  attempt_count: number;
  last_attempt_at: string | null;
  failure_reason: string;
  scheduled_for: string | null;
  sent_at: string | null;
  created_at: string;
};

export type AdminAuditLog = {
  id: string;
  admin_id: string | null;
  admin_phone: string | null;
  admin_name: string | null;
  action: string;
  action_label: string;
  target_type: string;
  target_id: string;
  metadata: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
};

export type AdminDashboardMetrics = {
  users: {
    total: number;
    new_7d: number;
    landlords: number;
    tenants: number;
    admins: number;
  };
  houses: { total: number; occupied: number; recent_7d: number };
  subscriptions: {
    breakdown: Record<string, number>;
    active: number;
    expired: number;
  };
  revenue: { currency: string; month: number; day: number; previous_month: number };
};

export type AdminSeriesPoint = {
  date: string;
  count?: number;
  total?: number;
};

export type AdminListFilters = {
  search?: string;
  page?: number;
  page_size?: number;
  role?: string;
  status?: string;
  profile?: string;
  plan?: string;
  occupancy?: string;
  channel?: string;
  action?: string;
  from?: string;
  to?: string;
};
