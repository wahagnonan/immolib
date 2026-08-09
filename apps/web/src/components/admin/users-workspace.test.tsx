import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AdminUsersWorkspace } from "./users-workspace";

vi.mock("@/lib/admin-api-client", () => ({
  listAdminUsers: vi.fn(),
  getAdminUser: vi.fn(),
  updateAdminUserStatus: vi.fn(),
}));

import {
  getAdminUser,
  listAdminUsers,
  updateAdminUserStatus,
} from "@/lib/admin-api-client";
import type { AdminUserDetail, AdminUserSummary } from "@/types/admin";
import type { PaginatedPage } from "@/types/domain";

const users: AdminUserSummary[] = [
  {
    id: "u1",
    role: "USER",
    full_name: "Awa Kouassi",
    phone: "+22507000000",
    email: "awa@example.com",
    is_active: true,
    date_joined: "2025-01-01T00:00:00Z",
    last_login: "2025-01-10T00:00:00Z",
    created_at: "2025-01-01T00:00:00Z",
    houses_count: 2,
    tenants_count: 1,
    plan_slug: "pro",
    plan_name: "Pro",
    subscription_status: "ACTIVE",
  },
  {
    id: "u2",
    role: "USER",
    full_name: "",
    phone: "+22501000000",
    email: "",
    is_active: false,
    date_joined: "2025-02-01T00:00:00Z",
    last_login: null,
    created_at: "2025-02-01T00:00:00Z",
    houses_count: 0,
    tenants_count: 0,
    plan_slug: null,
    plan_name: null,
    subscription_status: null,
  },
];

function page(results: AdminUserSummary[]): PaginatedPage<AdminUserSummary> {
  return { count: results.length, next: null, previous: null, results };
}

const detail: AdminUserDetail = {
  ...users[0],
  first_name: "Awa",
  last_name: "Kouassi",
  phone_verified_at: "2025-01-02T00:00:00Z",
  email_verified_at: null,
};

describe("AdminUsersWorkspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listAdminUsers).mockResolvedValue(page(users));
    vi.mocked(getAdminUser).mockResolvedValue(detail);
    vi.mocked(updateAdminUserStatus).mockResolvedValue(users[0]);
  });

  it("renders the list of users after loading", async () => {
    render(<AdminUsersWorkspace />);
    expect(screen.getByText("Chargement des utilisateurs…")).toBeInTheDocument();
    expect(await screen.findByText("Awa Kouassi")).toBeInTheDocument();
    expect(screen.getByText("+22501000000")).toBeInTheDocument();
    expect(screen.getAllByText("Pro").length).toBeGreaterThanOrEqual(1);
  });

  it("shows the empty state when no users match", async () => {
    vi.mocked(listAdminUsers).mockResolvedValue(page([]));
    render(<AdminUsersWorkspace />);
    expect(
      await screen.findByText("Aucun utilisateur ne correspond à ces filtres."),
    ).toBeInTheDocument();
  });

  it("refetches when the search input changes", async () => {
    const user = userEvent.setup();
    render(<AdminUsersWorkspace />);
    await screen.findByText("Awa Kouassi");

    await user.type(screen.getByPlaceholderText("Nom, email ou téléphone…"), "awa");
    await screen.findAllByText("Awa Kouassi");
    const calls = vi.mocked(listAdminUsers).mock.calls;
    expect(calls[calls.length - 1][0]).toMatchObject({ search: "awa", page: 1 });
  });

  it("filters by role", async () => {
    const user = userEvent.setup();
    render(<AdminUsersWorkspace />);
    await screen.findByText("Awa Kouassi");

    await user.selectOptions(screen.getByLabelText("Filtrer par rôle"), "ADMIN");
    await screen.findAllByText("Awa Kouassi");
    const calls = vi.mocked(listAdminUsers).mock.calls;
    expect(calls[calls.length - 1][0]).toMatchObject({ role: "ADMIN" });
  });

  it("opens the user detail modal", async () => {
    const user = userEvent.setup();
    render(<AdminUsersWorkspace />);
    await screen.findByText("Awa Kouassi");

    await user.click(
      screen.getByRole("button", { name: "Consulter Awa Kouassi" }),
    );
    expect(await screen.findByText("Fiche utilisateur")).toBeInTheDocument();
    expect(screen.getAllByText("awa@example.com").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("+22507000000")).toBeInTheDocument();
  });

  it("suspends a user after confirmation", async () => {
    const user = userEvent.setup();
    render(<AdminUsersWorkspace />);
    await screen.findByText("Awa Kouassi");

    await user.click(screen.getByRole("button", { name: "Suspendre Awa Kouassi" }));
    expect(
      await screen.findByText("Suspendre l'utilisateur"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Suspendre" }));

    expect(updateAdminUserStatus).toHaveBeenCalledWith("u1", false);
    await screen.findByText("Awa Kouassi");
  });

  it("reactivates a suspended user after confirmation", async () => {
    const user = userEvent.setup();
    render(<AdminUsersWorkspace />);
    await screen.findByText("+22501000000");

    await user.click(
      screen.getByRole("button", { name: "Réactiver +22501000000" }),
    );
    expect(
      await screen.findByText("Réactiver l'utilisateur"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Réactiver" }));

    expect(updateAdminUserStatus).toHaveBeenCalledWith("u2", true);
    await screen.findByText("+22501000000");
  });
});
