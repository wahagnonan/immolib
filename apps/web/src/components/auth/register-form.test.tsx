import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RegisterForm } from "./register-form";
import { AuthContext } from "./auth-provider";
import type { RegistrationResult } from "@/types/auth";

const mockRouter = { replace: vi.fn(), refresh: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/inscription",
}));

function renderRegisterForm(contextValues?: Partial<typeof defaultContext>) {
  const defaultContext = {
    user: null,
    loading: false,
    sessionError: null,
    login: vi.fn(),
    register: vi.fn(),
    verifyPhone: vi.fn(),
    verifyEmail: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  };
  const ctx = { ...defaultContext, ...contextValues };
  return render(
    <AuthContext.Provider value={ctx}>
      <RegisterForm />
    </AuthContext.Provider>,
  );
}

function passwordFields(container: HTMLElement) {
  return Array.from(
    container.querySelectorAll<HTMLInputElement>('input[autocomplete="new-password"]'),
  );
}

describe("RegisterForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders all required fields", () => {
    renderRegisterForm();
    expect(screen.getByText("Prénom *")).toBeInTheDocument();
    expect(screen.getByText("Nom *")).toBeInTheDocument();
    expect(screen.getByText("Numéro de téléphone *")).toBeInTheDocument();
    expect(screen.getByText("Mot de passe *")).toBeInTheDocument();
    expect(screen.getByText("Confirmer le mot de passe *")).toBeInTheDocument();
    expect(screen.getByText("Créer mon compte")).toBeInTheDocument();
  });

  it("shows password mismatch error", async () => {
    const user = userEvent.setup();
    const { container } = renderRegisterForm();
    const [password, confirmation] = passwordFields(container);

    await user.type(screen.getByLabelText(/Prénom \*/), "Jean");
    await user.type(screen.getByLabelText(/Nom \*/), "Dupont");
    await user.type(screen.getByLabelText(/Numéro de téléphone \*/), "+22507000000");
    await user.type(password, "secret123");
    await user.type(confirmation, "different");
    await user.click(screen.getByText("Créer mon compte"));

    expect(screen.getByText("Les deux mots de passe ne correspondent pas.")).toBeInTheDocument();
  });

  it("calls register on submit with matching passwords", async () => {
    const user = userEvent.setup();
    const register = vi.fn().mockResolvedValue({
      verification_required: true,
      verification_channel: "SMS",
      user: { id: "1", phone: "+22507000000" },
    } as RegistrationResult);
    const { container } = renderRegisterForm({ register });
    const [password, confirmation] = passwordFields(container);

    await user.type(screen.getByLabelText(/Prénom \*/), "Jean");
    await user.type(screen.getByLabelText(/Nom \*/), "Dupont");
    await user.type(screen.getByLabelText(/Numéro de téléphone \*/), "+22507000000");
    await user.type(password, "secret123");
    await user.type(confirmation, "secret123");
    await user.click(screen.getByText("Créer mon compte"));

    expect(register).toHaveBeenCalledWith(
      expect.objectContaining({
        phone: "+22507000000",
        first_name: "Jean",
        last_name: "Dupont",
        password: "secret123",
      }),
    );
  });

  it("shows verification form when registration requires verification", async () => {
    const user = userEvent.setup();
    const register = vi.fn().mockResolvedValue({
      verification_required: true,
      verification_channel: "EMAIL",
      user: { id: "1", phone: "+22507000000" },
      masked_destination: "j***@example.com",
    } as RegistrationResult);
    const { container } = renderRegisterForm({ register });
    const [password, confirmation] = passwordFields(container);

    await user.type(screen.getByLabelText(/Prénom \*/), "Jean");
    await user.type(screen.getByLabelText(/Nom \*/), "Dupont");
    await user.type(screen.getByLabelText(/Numéro de téléphone \*/), "+22507000000");
    await user.type(password, "secret123");
    await user.type(confirmation, "secret123");
    await user.click(screen.getByText("Créer mon compte"));

    expect(await screen.findByText(/Vérifiez votre email/)).toBeInTheDocument();
  });

  it("redirects authenticated users", () => {
    renderRegisterForm({
      user: { id: "1", phone: "+22507000000", first_name: "Jean", last_name: "Dupont",
        full_name: "Jean Dupont", email: "", phone_verified_at: null, email_verified_at: null,
        has_verified_contact: false, has_owner_access: true, has_tenant_access: false,
        created_at: "2025-01-01T00:00:00Z" },
      loading: false,
    });
    expect(mockRouter.replace).toHaveBeenCalledWith("/tableau-de-bord");
  });

  it("shows error message on registration failure", async () => {
    const user = userEvent.setup();
    const register = vi.fn().mockRejectedValue(new Error("Ce téléphone est déjà utilisé."));
    const { container } = renderRegisterForm({ register });
    const [password, confirmation] = passwordFields(container);

    await user.type(screen.getByLabelText(/Prénom \*/), "Jean");
    await user.type(screen.getByLabelText(/Nom \*/), "Dupont");
    await user.type(screen.getByLabelText(/Numéro de téléphone \*/), "+22507000000");
    await user.type(password, "secret123");
    await user.type(confirmation, "secret123");
    await user.click(screen.getByText("Créer mon compte"));

    expect(await screen.findByText("Ce téléphone est déjà utilisé.")).toBeInTheDocument();
  });

  it("toggles password visibility", async () => {
    const user = userEvent.setup();
    const { container } = renderRegisterForm();
    const passwordInputs = passwordFields(container);
    expect(passwordInputs[0]).toHaveAttribute("type", "password");
    await user.click(screen.getByLabelText("Afficher les mots de passe"));
    expect(passwordInputs[0]).toHaveAttribute("type", "text");
    expect(passwordInputs[1]).toHaveAttribute("type", "text");
  });

  it("has link to login", () => {
    renderRegisterForm();
    expect(screen.getByText("Se connecter")).toHaveAttribute("href", "/connexion");
  });
});
