import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MaintenanceWorkspace } from "./maintenance-workspace";

vi.mock("@/lib/api-client", () => ({
  listMaintenanceIncidents: vi.fn(),
  listLeases: vi.fn(),
  listHouses: vi.fn(),
  createMaintenanceIncident: vi.fn(),
  setMaintenanceIncidentStatus: vi.fn(),
  commentOnMaintenanceIncident: vi.fn(),
}));

import {
  listMaintenanceIncidents, listLeases, listHouses,
  createMaintenanceIncident, setMaintenanceIncidentStatus,
} from "@/lib/api-client";
import type { MaintenanceIncident, Lease, House } from "@/types/domain";

const mockIncidents: MaintenanceIncident[] = [
  {
    id: "i1", house_id: "h1", house_name: "Villa Lauriers", house_address: "Rue 12",
    lease_id: "l1", tenant_id: "t1", tenant_name: "Jean Dupont",
    title: "Fuite d'eau", description: "Fuite sous l'évier", category: "PLUMBING",
    category_label: "Plomberie", priority: "URGENT", priority_label: "Urgente",
    status: "REPORTED", status_label: "Signalé", occurred_at: null, resolved_at: null,
    closed_at: null, events: [], created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
  },
  {
    id: "i2", house_id: "h1", house_name: "Villa Lauriers", house_address: "Rue 12",
    lease_id: "l1", tenant_id: "t1", tenant_name: "Jean Dupont",
    title: "Prise défectueuse", description: "Prise qui ne fonctionne pas",
    category: "ELECTRICITY", category_label: "Électricité", priority: "NORMAL",
    priority_label: "Normale", status: "RESOLVED", status_label: "Résolu",
    occurred_at: null, resolved_at: "2025-01-10T00:00:00Z", closed_at: null,
    events: [{
      id: "e1", event_type: "REPORTED", event_label: "Signalé",
      actor_role: "TENANT", actor_role_label: "Locataire", actor_name: "Jean Dupont",
      from_status: "", from_status_label: "", to_status: "REPORTED",
      to_status_label: "Signalé", message: "", created_at: "2025-01-05T00:00:00Z",
    }],
    created_at: "2025-01-05T00:00:00Z", updated_at: "2025-01-10T00:00:00Z",
  },
];

const mockLeases: Lease[] = [
  {
    id: "l1", house_id: "h1",
    tenant: { id: "t1", house_id: "h1", full_name: "Jean Dupont", phone: "+22507000000",
      email: "", status: "ACTIVE", status_label: "Actif", has_account: true,
      created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z" },
    status: "ACTIVE", status_label: "Actif", start_date: "2025-01-01", end_date: null,
    monthly_rent: "200000", monthly_charges: "15000", due_day: 5,
    security_deposit: "200000", rent_advance: "0", currency: "XOF",
    accepts_mobile_money: true, accepts_cash: true,
    activated_at: "2025-01-01T00:00:00Z", ended_at: null,
    created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z",
  },
];

const mockHouses: House[] = [
  {
    id: "h1", name: "Villa Lauriers", address: "Rue 12", commune: "Cocody",
    city: "Abidjan", landmark: "", status: "OCCUPIED", status_label: "Occupée",
    ownerships: [], created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z",
  },
];

describe("MaintenanceWorkspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listMaintenanceIncidents).mockResolvedValue(mockIncidents);
    vi.mocked(listLeases).mockResolvedValue(mockLeases);
    vi.mocked(listHouses).mockResolvedValue(mockHouses);
  });

  it("renders loading state initially", () => {
    vi.mocked(listMaintenanceIncidents).mockImplementation(() => new Promise(() => {}));
    render(<MaintenanceWorkspace />);
    expect(screen.getByText("Chargement des incidents…")).toBeInTheDocument();
  });

  it("renders incidents after loading", async () => {
    render(<MaintenanceWorkspace />);
    const matches = await screen.findAllByText("Fuite d'eau");
    expect(matches.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Prise défectueuse")).toBeInTheDocument();
  });

  it("displays metric cards with counts", async () => {
    render(<MaintenanceWorkspace />);
    await screen.findAllByText("Fuite d'eau");
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("selects first incident by default", async () => {
    render(<MaintenanceWorkspace />);
    expect(await screen.findByText("Plomberie")).toBeInTheDocument();
  });

  it("switches selected incident on click", async () => {
    const user = userEvent.setup();
    render(<MaintenanceWorkspace />);
    await screen.findByText("Plomberie");

    await user.click(screen.getByText("Prise défectueuse"));
    expect(screen.getByText("Électricité")).toBeInTheDocument();
  });

  it("opens create incident modal on button click", async () => {
    const user = userEvent.setup();
    render(<MaintenanceWorkspace />);
    await screen.findAllByText("Fuite d'eau");

    await user.click(screen.getByText("Signaler un incident"));
    expect(screen.getByText("Enregistrer un incident")).toBeInTheDocument();
  });

  it("creates a new incident via form", async () => {
    const user = userEvent.setup();
    const newIncident: MaintenanceIncident = {
      id: "i3", house_id: "h1", house_name: "Villa Lauriers", house_address: "Rue 12",
      lease_id: "l1", tenant_id: "t1", tenant_name: "Jean Dupont",
      title: "Nouvel incident", description: "Description", category: "OTHER",
      category_label: "Autre", priority: "NORMAL", priority_label: "Normale",
      status: "REPORTED", status_label: "Signalé", occurred_at: null, resolved_at: null,
      closed_at: null, events: [], created_at: "2025-01-15T00:00:00Z",
      updated_at: "2025-01-15T00:00:00Z",
    };
    vi.mocked(createMaintenanceIncident).mockResolvedValue(newIncident);

    render(<MaintenanceWorkspace />);
    await screen.findAllByText("Fuite d'eau");

    await user.click(screen.getByText("Signaler un incident"));
    await screen.findByText("Enregistrer un incident");

    await user.selectOptions(screen.getByLabelText("Bail concerné *"), "l1");
    await user.selectOptions(screen.getByLabelText("Catégorie *"), "OTHER");
    await user.type(screen.getByLabelText("Titre *"), "Nouvel incident");
    await user.type(screen.getByLabelText("Description *"), "Description");
    await user.click(screen.getByText("Enregistrer"));

    expect(await screen.findByText("Incident enregistré et ajouté au suivi.")).toBeInTheDocument();
  });

  it("shows status transition buttons for REPORTED incident", async () => {
    render(<MaintenanceWorkspace />);
    await screen.findAllByText("Fuite d'eau");

    expect(screen.getByText("Prendre en compte")).toBeInTheDocument();
    expect(screen.getByText("Annuler")).toBeInTheDocument();
  });

  it("updates incident status on transition click", async () => {
    const user = userEvent.setup();
    const updated: MaintenanceIncident = {
      ...mockIncidents[0], status: "ACKNOWLEDGED", status_label: "Pris en compte",
    };
    vi.mocked(setMaintenanceIncidentStatus).mockResolvedValue(updated);

    render(<MaintenanceWorkspace />);
    await screen.findAllByText("Fuite d'eau");

    await user.click(screen.getByText("Prendre en compte"));
    expect(await screen.findByRole("status")).toHaveTextContent("mis à jour");
  });

  it("shows empty state when no incidents", async () => {
    vi.mocked(listMaintenanceIncidents).mockResolvedValue([]);
    render(<MaintenanceWorkspace />);
    expect(await screen.findByText("Aucun incident signalé.")).toBeInTheDocument();
  });
});