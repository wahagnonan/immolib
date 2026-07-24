import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HouseWorkspace } from "./house-workspace";

vi.mock("@/lib/api-client", () => ({
  listHouses: vi.fn(),
  createHouse: vi.fn(),
}));

import { listHouses, createHouse } from "@/lib/api-client";
import type { House } from "@/types/domain";

const mockHouses: House[] = [
  {
    id: "1", name: "Villa des Lauriers", address: "Rue 12", commune: "Cocody",
    city: "Abidjan", landmark: "Près du marché", status: "OCCUPIED", status_label: "Occupée",
    ownerships: [{ id: "o1", user: { id: "u1", phone: "+22507000000", full_name: "Jean" },
      role: "PRIMARY", role_label: "Principal", access_level: "ACTIVE", access_level_label: "Actif",
      ownership_percentage: null }],
    created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z",
  },
  {
    id: "2", name: "Résidence les Fleurs", address: "Avenue 5", commune: "Plateau",
    city: "Abidjan", landmark: "", status: "VACANT", status_label: "Vacante",
    ownerships: [], created_at: "2025-01-02T00:00:00Z", updated_at: "2025-01-02T00:00:00Z",
  },
  {
    id: "3", name: "Studio Indisponible", address: "Rue 8", commune: "Marcory",
    city: "Abidjan", landmark: "", status: "UNAVAILABLE", status_label: "Indisponible",
    ownerships: [], created_at: "2025-01-03T00:00:00Z", updated_at: "2025-01-03T00:00:00Z",
  },
];

describe("HouseWorkspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listHouses).mockResolvedValue(mockHouses);
  });

  it("renders loading state initially", () => {
    vi.mocked(listHouses).mockImplementation(() => new Promise(() => {}));
    render(<HouseWorkspace />);
    expect(screen.getByText("Chargement des maisons…")).toBeInTheDocument();
  });

  it("renders houses after loading", async () => {
    render(<HouseWorkspace />);
    expect(await screen.findByText("Villa des Lauriers")).toBeInTheDocument();
    expect(screen.getByText("Résidence les Fleurs")).toBeInTheDocument();
  });

  it("displays summary cards with counts", async () => {
    render(<HouseWorkspace />);
    await screen.findByText("Villa des Lauriers");
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("filters houses by search query", async () => {
    const user = userEvent.setup();
    render(<HouseWorkspace />);
    await screen.findByText("Villa des Lauriers");

    await user.type(screen.getByPlaceholderText("Nom, commune, ville…"), "Fleurs");
    expect(screen.getByText("Résidence les Fleurs")).toBeInTheDocument();
    expect(screen.queryByText("Villa des Lauriers")).not.toBeInTheDocument();
  });

  it("filters houses by status", async () => {
    const user = userEvent.setup();
    render(<HouseWorkspace />);
    await screen.findByText("Villa des Lauriers");

    await user.selectOptions(screen.getByRole("combobox"), "VACANT");
    expect(screen.getByText("Résidence les Fleurs")).toBeInTheDocument();
    expect(screen.queryByText("Villa des Lauriers")).not.toBeInTheDocument();
  });

  it("shows empty message when no houses match filter", async () => {
    const user = userEvent.setup();
    render(<HouseWorkspace />);
    await screen.findByText("Villa des Lauriers");

    await user.type(screen.getByPlaceholderText("Nom, commune, ville…"), "Inexistant");
    expect(screen.getByText("Aucune maison trouvée")).toBeInTheDocument();
  });

  it("opens creation form on button click", async () => {
    const user = userEvent.setup();
    render(<HouseWorkspace />);
    await screen.findByText("Villa des Lauriers");

    await user.click(screen.getByText("Nouvelle maison"));
    expect(screen.getByText("Créer une maison")).toBeInTheDocument();
  });

  it("closes creation form on cancel", async () => {
    const user = userEvent.setup();
    render(<HouseWorkspace />);
    await screen.findByText("Villa des Lauriers");

    await user.click(screen.getByText("Nouvelle maison"));
    await user.click(screen.getByText("Annuler"));
    expect(screen.queryByText("Créer une maison")).not.toBeInTheDocument();
  });

  it("creates a new house via form", async () => {
    const user = userEvent.setup();
    const newHouse: House = {
      id: "4", name: "Nouvelle Villa", address: "Rue 99", commune: "Yopougon",
      city: "Abidjan", landmark: "", status: "VACANT", status_label: "Vacante",
      ownerships: [], created_at: "2025-01-04T00:00:00Z", updated_at: "2025-01-04T00:00:00Z",
    };
    vi.mocked(createHouse).mockResolvedValue(newHouse);

    render(<HouseWorkspace />);
    await screen.findByText("Villa des Lauriers");

    await user.click(screen.getByText("Nouvelle maison"));
    await user.type(screen.getByLabelText("Nom de la maison *"), "Nouvelle Villa");
    await user.type(screen.getByLabelText("Ville *"), "Abidjan");
    await user.type(screen.getByLabelText("Adresse *"), "Rue 99");
    await user.click(screen.getByText("Créer la maison"));

    expect(await screen.findByText("Nouvelle Villa")).toBeInTheDocument();
  });

  it("shows error when creation fails", async () => {
    const user = userEvent.setup();
    vi.mocked(createHouse).mockRejectedValue(new Error("Erreur lors de la création."));

    render(<HouseWorkspace />);
    await screen.findByText("Villa des Lauriers");

    await user.click(screen.getByText("Nouvelle maison"));
    await user.type(screen.getByLabelText("Nom de la maison *"), "Erreur");
    await user.type(screen.getByLabelText("Ville *"), "Abidjan");
    await user.type(screen.getByLabelText("Adresse *"), "Rue 1");
    await user.click(screen.getByText("Créer la maison"));

    expect(await screen.findByText("Erreur lors de la création.")).toBeInTheDocument();
  });

  it("shows success feedback after creation", async () => {
    const user = userEvent.setup();
    const newHouse: House = {
      id: "5", name: "Succès Villa", address: "Rue 10", commune: "Cocody",
      city: "Abidjan", landmark: "", status: "VACANT", status_label: "Vacante",
      ownerships: [], created_at: "2025-01-05T00:00:00Z", updated_at: "2025-01-05T00:00:00Z",
    };
    vi.mocked(createHouse).mockResolvedValue(newHouse);

    render(<HouseWorkspace />);
    await screen.findByText("Villa des Lauriers");

    await user.click(screen.getByText("Nouvelle maison"));
    await user.type(screen.getByLabelText("Nom de la maison *"), "Succès Villa");
    await user.type(screen.getByLabelText("Ville *"), "Abidjan");
    await user.type(screen.getByLabelText("Adresse *"), "Rue 10");
    await user.click(screen.getByText("Créer la maison"));

    expect(await screen.findByText("Maison ajoutée avec succès.")).toBeInTheDocument();
  });
});