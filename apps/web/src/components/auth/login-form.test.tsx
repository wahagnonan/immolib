import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginForm } from "./login-form";
import { AuthContext } from "./auth-provider";
import type { CurrentUser } from "@/types/auth";

const mockRouter = { replace: vi.fn(), refresh: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/connexion",
}));

const baseUser: CurrentUser = {
  id: "1",
  phone: "+22507000000",
  email: "",
  first_name: "Jean",
  last_name: "Dupont",
  full_name: "Jean Dupont",
  phone_verified_at: null,
  email_verified_at: null,
  has_verified_contact: false,
  has_owner_access: false,
  has_tenant_access: false,
  created_at: "2025-01-01T00:00:00Z",
};

function renderLoginForm(contextValues?: Partial<typeof defaultContext>) {
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
      <LoginForm />
    </AuthContext.Provider>,
  );
}

describe("LoginForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders phone and password fields", () => {
    renderLoginForm();
    expect(screen.getByPlaceholderText("+225 07 00 00 00 00")).toBeInTheDocument();
    expect(screen.getByText("Mot de passe")).toBeInTheDocument();
    expect(screen.getByText("Se connecter")).toBeInTheDocument();
  });

  it("displays session error from context", () => {
    renderLoginForm({ sessionError: "Session expirée." });
    expect(screen.getByText("Session expirée.")).toBeInTheDocument();
  });

  it("toggles password visibility", async () => {
    const user = userEvent.setup();
    renderLoginForm();
    const passwordInput = screen.getByLabelText(/Mot de passe/);
    expect(passwordInput).toHaveAttribute("type", "password");
    await user.click(screen.getByLabelText("Afficher le mot de passe"));
    expect(passwordInput).toHaveAttribute("type", "text");
    await user.click(screen.getByLabelText("Masquer le mot de passe"));
    expect(passwordInput).toHaveAttribute("type", "password");
  });

  it("calls login on submit", async () => {
    const user = userEvent.setup();
    const login = vi.fn().mockResolvedValue({ ...baseUser, has_owner_access: true });
    renderLoginForm({ login });

    await user.type(screen.getByPlaceholderText("+225 07 00 00 00 00"), "+22507000000");
    await user.type(screen.getByLabelText(/Mot de passe/), "secret123");
    await user.click(screen.getByText("Se connecter"));

    expect(login).toHaveBeenCalledWith({
      phone: "+22507000000",
      password: "secret123",
    });
  });

  it("shows error message on login failure", async () => {
    const user = userEvent.setup();
    const login = vi.fn().mockRejectedValue(new Error("Téléphone ou mot de passe incorrect."));
    renderLoginForm({ login });

    await user.type(screen.getByPlaceholderText("+225 07 00 00 00 00"), "+22507000000");
    await user.type(screen.getByLabelText(/Mot de passe/), "wrong");
    await user.click(screen.getByText("Se connecter"));

    expect(await screen.findByText("Téléphone ou mot de passe incorrect.")).toBeInTheDocument();
  });

  it("redirects authenticated users without owner access to tenant space", () => {
    renderLoginForm({
      user: { ...baseUser, has_tenant_access: true, has_owner_access: false },
      loading: false,
    });
    expect(mockRouter.replace).toHaveBeenCalledWith("/espace-locataire");
  });

  it("redirects authenticated owners to dashboard", () => {
    renderLoginForm({
      user: { ...baseUser, has_owner_access: true },
      loading: false,
    });
    expect(mockRouter.replace).toHaveBeenCalledWith("/tableau-de-bord");
  });

  it("disables form while saving", async () => {
    const user = userEvent.setup();
    const login = vi.fn().mockImplementation(() => new Promise(() => {}));
    renderLoginForm({ login });

    await user.type(screen.getByPlaceholderText("+225 07 00 00 00 00"), "+22507000000");
    await user.type(screen.getByLabelText(/Mot de passe/), "secret123");
    await user.click(screen.getByText("Se connecter"));

    expect(screen.getByText("Connexion…")).toBeInTheDocument();
    expect(screen.getByText("Connexion…")).toBeDisabled();
  });

  it("has link to password reset", () => {
    renderLoginForm();
    expect(screen.getByText("Mot de passe oublié ?")).toHaveAttribute("href", "/mot-de-passe-oublie");
  });

  it("has link to registration", () => {
    renderLoginForm();
    expect(screen.getByText("Créer mon compte")).toHaveAttribute("href", "/inscription");
  });
});
