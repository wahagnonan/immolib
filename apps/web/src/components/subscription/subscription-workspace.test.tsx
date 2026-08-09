import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  cancelSubscription,
  getSubscription,
  listSubscriptionPlans,
  refreshSubscriptionTransaction,
  upgradeSubscription,
} from "@/lib/api-client";
import type {
  SubscriptionDetail,
  SubscriptionPlan,
} from "@/types/domain";
import { SubscriptionWorkspace } from "./subscription-workspace";

vi.mock("@/lib/api-client", () => ({
  getSubscription: vi.fn(),
  listSubscriptionPlans: vi.fn(),
  upgradeSubscription: vi.fn(),
  cancelSubscription: vi.fn(),
  refreshSubscriptionTransaction: vi.fn(),
}));

const plans: SubscriptionPlan[] = [
  {
    id: "plan-free",
    slug: "free",
    name: "Gratuit",
    description: "Pour tester ImmoLib sur une première location.",
    price_monthly: 0,
    currency: "XOF",
    max_houses: 1,
    features: ["tenant_management", "lease_management", "payment_tracking"],
    is_active: true,
  },
  {
    id: "plan-essential",
    slug: "essential",
    name: "Essentiel",
    description: "Pour automatiser le suivi courant d'un petit patrimoine.",
    price_monthly: 2000,
    currency: "XOF",
    max_houses: 5,
    features: ["payment_reminders", "co_owners", "basic_statistics"],
    is_active: true,
  },
  {
    id: "plan-pro",
    slug: "pro",
    name: "Pro",
    description: "Pour un bailleur qui pilote plusieurs locations.",
    price_monthly: 4000,
    currency: "XOF",
    max_houses: 15,
    features: ["automated_notifications", "data_export"],
    is_active: true,
  },
];

function freeDetail(): SubscriptionDetail {
  return {
    plan: plans[0],
    status: "ACTIVE",
    status_label: "Actif",
    started_at: "2026-01-01T00:00:00Z",
    expires_at: null,
    house_count: 1,
    max_houses: 1,
    remaining_houses: 0,
    features: plans[0].features,
    pending_transaction: null,
  };
}

function essentialDetail(): SubscriptionDetail {
  return {
    ...freeDetail(),
    plan: plans[1],
    max_houses: 5,
    remaining_houses: 4,
    features: plans[1].features,
  };
}

function pendingDetail(): SubscriptionDetail {
  return {
    ...essentialDetail(),
    pending_transaction: {
      id: "tx-pending",
      plan_slug: "essential",
      plan_name: "Essentiel",
      amount: 2000,
      currency: "XOF",
      status: "PENDING",
      status_label: "En attente",
      provider: "PAYDUNYA",
      provider_reference: "token-abc",
      completed_at: null,
      created_at: "2026-01-01T00:00:00Z",
    },
  };
}

describe("SubscriptionWorkspace", () => {
  let currentDetail: SubscriptionDetail;

  beforeEach(() => {
    vi.clearAllMocks();
    currentDetail = freeDetail();
    vi.mocked(getSubscription).mockImplementation(async () => currentDetail);
    vi.mocked(listSubscriptionPlans).mockResolvedValue(plans);
  });

  it("affiche le plan actuel et les trois formules", async () => {
    render(<SubscriptionWorkspace />);

    expect(await screen.findByText("Plan actuel")).toBeInTheDocument();
    expect(screen.getAllByText("Gratuit").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Essentiel")).toBeInTheDocument();
    expect(screen.getByText("Pro")).toBeInTheDocument();
    expect(screen.getByText("1 maison incluse")).toBeInTheDocument();
    expect(
      screen.getByText("Quota atteint : passez au plan supérieur pour ajouter des maisons."),
    ).toBeInTheDocument();
    expect(screen.getByText("Passer à Essentiel")).toBeInTheDocument();
  });

  it("souscrit à un plan et confirme l'activation immédiate", async () => {
    const user = userEvent.setup();
    vi.mocked(upgradeSubscription).mockResolvedValue({
      transaction: {
        id: "tx-1",
        plan_slug: "essential",
        plan_name: "Essentiel",
        amount: 2000,
        currency: "XOF",
        status: "SUCCESSFUL",
        status_label: "Réussi",
        provider: "MANUAL",
        provider_reference: null,
        completed_at: null,
        created_at: "2026-01-01T00:00:00Z",
      },
      redirect_url: null,
      activated: true,
    });

    render(<SubscriptionWorkspace />);
    await screen.findByText("Plan actuel");
    currentDetail = essentialDetail();

    await user.click(screen.getByText("Passer à Essentiel"));

    expect(upgradeSubscription).toHaveBeenCalledWith("essential");
    expect(
      await screen.findByText(/Bienvenue sur le plan Essentiel/),
    ).toBeInTheDocument();
    expect(await screen.findByText("5 maisons incluses")).toBeInTheDocument();
  });

  it("redirige vers PayDunya quand un redirect_url est renvoyé", async () => {
    const user = userEvent.setup();
    const assignMock = vi.fn();
    Object.defineProperty(window, "location", {
      value: { ...window.location, assign: assignMock },
      writable: true,
    });
    vi.mocked(upgradeSubscription).mockResolvedValue({
      transaction: {
        id: "tx-1",
        plan_slug: "essential",
        plan_name: "Essentiel",
        amount: 2000,
        currency: "XOF",
        status: "PENDING",
        status_label: "En attente",
        provider: "PAYDUNYA",
        provider_reference: "token-abc",
        completed_at: null,
        created_at: "2026-01-01T00:00:00Z",
      },
      redirect_url: "https://paydunya.example/checkout/token-abc",
      activated: false,
    });

    render(<SubscriptionWorkspace />);
    await screen.findByText("Plan actuel");
    await user.click(screen.getByText("Passer à Essentiel"));

    await waitFor(() =>
      expect(assignMock).toHaveBeenCalledWith(
        "https://paydunya.example/checkout/token-abc",
      ),
    );
  });

  it("affiche une erreur quand la souscription échoue", async () => {
    const user = userEvent.setup();
    vi.mocked(upgradeSubscription).mockRejectedValue(
      new Error("Le plan Pro n'existe pas."),
    );

    render(<SubscriptionWorkspace />);
    await screen.findByText("Plan actuel");
    await user.click(screen.getByText("Passer à Pro"));

    expect(await screen.findByText("Le plan Pro n'existe pas.")).toBeInTheDocument();
  });

  it("permet de vérifier un paiement en attente", async () => {
    const user = userEvent.setup();
    currentDetail = pendingDetail();
    vi.mocked(refreshSubscriptionTransaction).mockResolvedValue({
      ...pendingDetail().pending_transaction!,
      status: "SUCCESSFUL",
      status_label: "Réussi",
    });

    render(<SubscriptionWorkspace />);

    expect(
      await screen.findByText("Paiement en attente : Essentiel"),
    ).toBeInTheDocument();
    currentDetail = freeDetail();
    await user.click(screen.getByText("Vérifier le paiement"));

    expect(refreshSubscriptionTransaction).toHaveBeenCalledWith("tx-pending");
    expect(
      await screen.findByText("Paiement confirmé. Votre abonnement est actif."),
    ).toBeInTheDocument();
  });

  it("annule l'abonnement après confirmation", async () => {
    const user = userEvent.setup();
    currentDetail = essentialDetail();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(cancelSubscription).mockResolvedValue({
      status: "CANCELLED",
      status_label: "Annulé",
    });

    render(<SubscriptionWorkspace />);
    await screen.findByText("Annuler l'abonnement");
    currentDetail = freeDetail();
    await user.click(screen.getByText("Annuler l'abonnement"));

    expect(cancelSubscription).toHaveBeenCalled();
    expect(
      await screen.findByText(
        "Abonnement annulé. Vous êtes revenu au plan Gratuit.",
      ),
    ).toBeInTheDocument();
  });
});
