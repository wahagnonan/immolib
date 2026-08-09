import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AdminTenantsWorkspace } from "./tenants-workspace";

vi.mock("@/lib/admin-api-client", () => ({
  listAdminTenants: vi.fn(),
}));

import { listAdminTenants } from "@/lib/admin-api-client";
import type { AdminTenant } from "@/types/admin";
import type { PaginatedPage } from "@/types/domain";

const tenants: AdminTenant[] = [
  {
    id: "t1",
    full_name: "Jean Dupont",
    phone: "+22507000000",
    email: "jean@example.com",
    status: "ACTIVE",
    property_id: "h1",
    property_name: "Villa Lauriers",
    linked_user_id: "u1",
    linked_user_phone: "+22507000000",
    created_at: "2025-01-01T00:00:00Z",
  },
  {
    id: "t2",
    full_name: "Marie Koffi",
    phone: "+22501000000",
    email: "",
    status: "UNREGISTERED",
    property_id: "h2",
    property_name: "Immeuble Cocody",
    linked_user_id: null,
    linked_user_phone: null,
    created_at: "2025-02-01T00:00:00Z",
  },
];

function page(results: AdminTenant[]): PaginatedPage<AdminTenant> {
  return { count: results.length, next: null, previous: null, results };
}

describe("AdminTenantsWorkspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listAdminTenants).mockResolvedValue(page(tenants));
  });

  it("renders the list of tenants after loading", async () => {
    render(<AdminTenantsWorkspace />);
    expect(screen.getByText("Chargement des locataires…")).toBeInTheDocument();
    expect(await screen.findByText("Jean Dupont")).toBeInTheDocument();
    expect(screen.getByText("Villa Lauriers")).toBeInTheDocument();
    expect(screen.getByText("Marie Koffi")).toBeInTheDocument();
  });

  it("shows the empty state when no tenants match", async () => {
    vi.mocked(listAdminTenants).mockResolvedValue(page([]));
    render(<AdminTenantsWorkspace />);
    expect(
      await screen.findByText("Aucun locataire ne correspond à ces filtres."),
    ).toBeInTheDocument();
  });

  it("filters by status", async () => {
    const user = userEvent.setup();
    render(<AdminTenantsWorkspace />);
    await screen.findByText("Jean Dupont");

    await user.selectOptions(screen.getByLabelText("Filtrer par statut"), "ACTIVE");
    await screen.findAllByText("Jean Dupont");
    const calls = vi.mocked(listAdminTenants).mock.calls;
    expect(calls[calls.length - 1][0]).toMatchObject({ status: "ACTIVE" });
  });
});
