import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PasswordResetForm } from "./password-reset-form";

const mockRouter = { replace: vi.fn(), refresh: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/mot-de-passe-oublie",
}));

vi.mock("@/lib/auth-api-client", () => ({
  requestPasswordReset: vi.fn(),
  confirmPasswordReset: vi.fn(),
}));

import {
  confirmPasswordReset,
  requestPasswordReset,
} from "@/lib/auth-api-client";

describe("PasswordResetForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders phone step by default", () => {
    render(<PasswordResetForm />);
    expect(screen.getByText("Numéro de téléphone du compte")).toBeInTheDocument();
    expect(screen.getByText("Recevoir un code")).toBeInTheDocument();
  });

  it("transitions to reset step after requesting code", async () => {
    const user = userEvent.setup();
    vi.mocked(requestPasswordReset).mockResolvedValue({
      detail: "Code envoyé",
      otp_code: "123456",
      verification_channel: "SMS",
      masked_destination: "+225****0000",
    });

    render(<PasswordResetForm />);
    await user.type(screen.getByPlaceholderText("07 00 00 00 00"), "07000000");
    await user.click(screen.getByText("Recevoir un code"));

    expect(await screen.findByText("Code reçu par SMS")).toBeInTheDocument();
    expect(screen.getByText(/123456/)).toBeInTheDocument();
    expect(screen.getByText("Modifier mon mot de passe")).toBeInTheDocument();
  });

  it("shows password mismatch error on reset step", async () => {
    const user = userEvent.setup();
    vi.mocked(requestPasswordReset).mockResolvedValue({
      detail: "Code envoyé", otp_code: "123456",
      verification_channel: "SMS", masked_destination: "+225****0000",
    });

    render(<PasswordResetForm />);
    await user.type(screen.getByPlaceholderText("07 00 00 00 00"), "07000000");
    await user.click(screen.getByText("Recevoir un code"));
    await screen.findByText("Code reçu par SMS");

    await user.type(screen.getByLabelText("Code reçu par SMS"), "123456");
    await user.type(screen.getByLabelText("Nouveau mot de passe"), "secret123");
    await user.type(screen.getByLabelText("Confirmer le mot de passe"), "different");
    await user.click(screen.getByText("Modifier mon mot de passe"));

    expect(screen.getByText("Les deux mots de passe ne correspondent pas.")).toBeInTheDocument();
  });

  it("shows success step after password reset", async () => {
    const user = userEvent.setup();
    vi.mocked(requestPasswordReset).mockResolvedValue({
      detail: "Code envoyé", otp_code: "123456",
      verification_channel: "SMS", masked_destination: "+225****0000",
    });
    vi.mocked(confirmPasswordReset).mockResolvedValue({ detail: "Mot de passe modifié." });

    render(<PasswordResetForm />);
    await user.type(screen.getByPlaceholderText("07 00 00 00 00"), "07000000");
    await user.click(screen.getByText("Recevoir un code"));
    await screen.findByText("Code reçu par SMS");

    await user.type(screen.getByLabelText("Code reçu par SMS"), "123456");
    await user.type(screen.getByLabelText("Nouveau mot de passe"), "secret123");
    await user.type(screen.getByLabelText("Confirmer le mot de passe"), "secret123");
    await user.click(screen.getByText("Modifier mon mot de passe"));

    expect(await screen.findByText("Mot de passe modifié")).toBeInTheDocument();
    expect(screen.getByText("Se connecter")).toHaveAttribute("href", "/connexion");
  });

  it("goes back to phone step when clicking change number", async () => {
    const user = userEvent.setup();
    vi.mocked(requestPasswordReset).mockResolvedValue({
      detail: "Code envoyé", otp_code: "123456",
      verification_channel: "SMS", masked_destination: "+225****0000",
    });

    render(<PasswordResetForm />);
    await user.type(screen.getByPlaceholderText("07 00 00 00 00"), "07000000");
    await user.click(screen.getByText("Recevoir un code"));
    await screen.findByText("Code reçu par SMS");

    await user.click(screen.getByText("Changer de numéro"));
    expect(screen.getByText("Numéro de téléphone du compte")).toBeInTheDocument();
  });

  it("shows error when request fails", async () => {
    const user = userEvent.setup();
    vi.mocked(requestPasswordReset).mockRejectedValue(
      new Error("Aucun compte trouvé avec ce numéro."),
    );

    render(<PasswordResetForm />);
    await user.type(screen.getByPlaceholderText("07 00 00 00 00"), "07000000");
    await user.click(screen.getByText("Recevoir un code"));

    expect(await screen.findByText("Aucun compte trouvé avec ce numéro.")).toBeInTheDocument();
  });
});
