import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PhoneVerificationForm } from "./phone-verification-form";
import { AuthContext } from "./auth-provider";

const mockRouter = { replace: vi.fn(), refresh: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/verification-telephone",
}));

vi.mock("@/lib/auth-api-client", () => ({
  requestPhoneVerification: vi.fn(),
  requestEmailVerification: vi.fn(),
}));

import {
  requestEmailVerification,
  requestPhoneVerification,
} from "@/lib/auth-api-client";

const baseUser = {
  id: "1", phone: "+22507000000", email: "", first_name: "Jean", last_name: "Dupont",
  full_name: "Jean Dupont", phone_verified_at: null, email_verified_at: null,
  has_verified_contact: false, has_owner_access: false, has_tenant_access: false,
  created_at: "2025-01-01T00:00:00Z",
};

function renderVerificationForm(props?: Record<string, unknown>) {
  const verifyPhone = vi.fn().mockResolvedValue({ ...baseUser, has_owner_access: true });
  const verifyEmail = vi.fn().mockResolvedValue({ ...baseUser, has_owner_access: true });

  const context = {
    user: null,
    loading: false,
    sessionError: null,
    login: vi.fn(),
    register: vi.fn(),
    verifyPhone,
    verifyEmail,
    logout: vi.fn(),
    refresh: vi.fn(),
  };

  return {
    verifyPhone,
    verifyEmail,
    ...render(
      <AuthContext.Provider value={context}>
        <PhoneVerificationForm {...props} />
      </AuthContext.Provider>,
    ),
  };
}

describe("PhoneVerificationForm", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders phone request form initially", () => {
    renderVerificationForm();
    expect(screen.getByText("Numéro de téléphone")).toBeInTheDocument();
    expect(screen.getByText("Recevoir mon code")).toBeInTheDocument();
  });

  it("sends verification code on submit", async () => {
    const user = userEvent.setup();
    renderVerificationForm();
    vi.mocked(requestPhoneVerification).mockResolvedValue({
      detail: "Code envoyé par SMS",
      otp_code: "123456",
      masked_destination: "+225****0000",
    });

    await user.type(screen.getByPlaceholderText("07 00 00 00 00"), "07000000");
    await user.click(screen.getByText("Recevoir mon code"));

    expect(await screen.findByText("Code envoyé par SMS")).toBeInTheDocument();
  });

  it("shows verification code input after sending code", async () => {
    const user = userEvent.setup();
    renderVerificationForm();
    vi.mocked(requestPhoneVerification).mockResolvedValue({
      detail: "Code envoyé", otp_code: "654321",
      masked_destination: "+225****0000",
    });

    await user.type(screen.getByPlaceholderText("07 00 00 00 00"), "07000000");
    await user.click(screen.getByText("Recevoir mon code"));

    expect(await screen.findByText("Code reçu par SMS")).toBeInTheDocument();
    expect(screen.getByText(/654321/)).toBeInTheDocument();
  });

  it("calls verifyPhone on code submit", async () => {
    const user = userEvent.setup();
    const { verifyPhone } = renderVerificationForm();
    vi.mocked(requestPhoneVerification).mockResolvedValue({
      detail: "Code envoyé", otp_code: "123456",
      masked_destination: "+225****0000",
    });

    await user.type(screen.getByPlaceholderText("07 00 00 00 00"), "07000000");
    await user.click(screen.getByText("Recevoir mon code"));
    await screen.findByText("Code reçu par SMS");

    await user.type(screen.getByLabelText("Code reçu par SMS"), "123456");
    await user.click(screen.getByText("Vérifier et me connecter"));

    expect(verifyPhone).toHaveBeenCalledWith({ phone: "+22507000000", code: "123456" });
  });

  it("calls verifyEmail when channel is EMAIL", async () => {
    const user = userEvent.setup();
    const { verifyEmail } = renderVerificationForm({ channel: "EMAIL" as const });
    vi.mocked(requestEmailVerification).mockResolvedValue({
      detail: "Code envoyé par email", otp_code: "123456",
      masked_destination: "j***@example.com",
    });

    await user.type(screen.getByPlaceholderText("07 00 00 00 00"), "07000000");
    await user.click(screen.getByText("Recevoir mon code"));
    await screen.findByText("Code reçu par email");

    await user.type(screen.getByLabelText("Code reçu par email"), "123456");
    await user.click(screen.getByText("Vérifier et me connecter"));

    expect(verifyEmail).toHaveBeenCalledWith({ phone: "+22507000000", code: "123456" });
  });

  it("shows resend button with cooldown after sending code", async () => {
    const user = userEvent.setup();
    renderVerificationForm();
    vi.mocked(requestPhoneVerification).mockResolvedValue({
      detail: "Code envoyé", otp_code: "123456",
      masked_destination: "+225****0000",
    });

    await user.type(screen.getByPlaceholderText("07 00 00 00 00"), "07000000");
    await user.click(screen.getByText("Recevoir mon code"));

    expect(await screen.findByText(/Renvoyer dans \d+/)).toBeInTheDocument();
  });

  it("shows error when sending code fails", async () => {
    const user = userEvent.setup();
    renderVerificationForm();
    vi.mocked(requestPhoneVerification).mockRejectedValue(
      new Error("Trop de tentatives. Réessayez plus tard."),
    );

    await user.type(screen.getByPlaceholderText("07 00 00 00 00"), "07000000");
    await user.click(screen.getByText("Recevoir mon code"));

    expect(await screen.findByText("Trop de tentatives. Réessayez plus tard.")).toBeInTheDocument();
  });

  it("shows pre-filled phone when initialPhone is provided", () => {
    renderVerificationForm({ initialPhone: "+22507000000", codeAlreadySent: true });
    expect(screen.getByText("+22507000000")).toBeInTheDocument();
  });

  it("has link to login page", () => {
    renderVerificationForm();
    expect(screen.getByText("Retour à la connexion")).toHaveAttribute("href", "/connexion");
  });
});
