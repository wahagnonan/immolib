export type CurrentUser = {
  id: string;
  phone: string;
  full_name: string;
  email: string;
  first_name: string;
  last_name: string;
  phone_verified_at: string | null;
  email_verified_at: string | null;
  has_verified_contact: boolean;
  has_owner_access: boolean;
  has_tenant_access: boolean;
  created_at: string;
};

export type AuthResponse = { user: CurrentUser };

export type LoginPayload = { phone: string; password: string };

export type RegisterPayload = LoginPayload & {
  password_confirmation: string;
  first_name?: string;
  last_name?: string;
  email?: string;
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

export type PhoneCodePayload = { phone: string; code: string };

export type PasswordResetConfirmPayload = PhoneCodePayload & {
  password: string;
  password_confirmation: string;
};
