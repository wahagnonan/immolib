import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AdminSubscriptionsWorkspace } from "./subscriptions-workspace";

vi.mock("@/lib/admin-api-client", () => ({
  listAdminSubscriptions: vi.fn(),
  adminSubscriptionAction: vi.fn(),
}));

import {
  adminSubscriptionAction,
  listAdminSubscriptions,
} from "@/lib/admin-api-client";
import type { AdminSubscription } from "@/types/admin";
import type { PaginatedPage } from "@/types/domain";

const subscriptions: AdminSubscription[] = [
  {
    id: "s1",
    user_id: "u1",
    user_full_name: "Awa Kouassi",
    user_phone: "+22507000000",
    user_email: "awa@example.com",
    plan_slug: "pro",
    plan_name: "Pro",
    price_monthly: 5000,
    currency: "XOF",
    status: "ACTIVE",
    started_at: "2025-01-01T00:00:00Z",
    expires_at: "2025-02-01T00:00:00Z",
    houses_count: 2,
    max_houses: 50,
    created_at: "2025-01-01T00:00:00Z",
  },
  {
    id: "s2",
    user_id: "u2",
    user_full_name: "",
    user_phone: "+22501000000",
    user_email: "",
    plan_slug: "free",
    plan_name: "Gratuit",
    price_monthly: 0,
    currency: "XOF",
    status: "EXPIRED",
    started_at: null,
    expires_at: null,
    houses_count: 0,
    max_houses: 1,
    created_at: "2025-02-01T00:00:00Z",
  },
];

function page(results: AdminSubscription[]): PaginatedPage<AdminSubscription> {
  return { count: results.length, next: null, previous: null, results };
}

describe("AdminSubscriptionsWorkspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listAdminSubscriptions).mockResolvedValue(page(subscriptions));
    vi.mocked(adminSubscriptionAction).mockResolvedValue(subscriptions[0]);
  });

  it("renders the list of subscriptions after loading", async () => {
    render(<AdminSubscriptionsWorkspace />);
    expect(screen.getByText("Chargement des abonnements…")).toBeInTheDocument();
    expect(await screen.findByText("Awa Kouassi")).toBeInTheDocument();
    expect(screen.getAllByText("Pro").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("2/50")).toBeInTheDocument();
  });

  it("changes the plan of a subscription", async () => {
    const user = userEvent.setup();
    render(<AdminSubscriptionsWorkspace />);
    await screen.findByText("Awa Kouassi");

    await user.click(
      screen.getByRole("button", { name: "Gérer l'abonnement de Awa Kouassi" }),
    );
    expect(
      await screen.findByText("Gérer l'abonnement de Awa Kouassi"),
    ).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Plan"), "essential");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(adminSubscriptionAction).toHaveBeenCalledWith("s1", {
      action: "change_plan",
      plan_slug: "essential",
    });
    expect(await screen.findByText("Action enregistrée avec succès.")).toBeInTheDocument();
  });

  it("extends a subscription with a number of days", async () => {
    const user = userEvent.setup();
    render(<AdminSubscriptionsWorkspace />);
    await screen.findByText("Awa Kouassi");

    await user.click(
      screen.getByRole("button", { name: "Gérer l'abonnement de Awa Kouassi" }),
    );
    await user.selectOptions(screen.getByLabelText("Action"), "extend");
    await user.clear(screen.getByLabelText("Durée (jours)"));
    await user.type(screen.getByLabelText("Durée (jours)"), "60");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(adminSubscriptionAction).toHaveBeenCalledWith("s1", {
      action: "extend",
      days: 60,
    });
    expect(await screen.findByText("Action enregistrée avec succès.")).toBeInTheDocument();
  });

  it("activates a subscription manually", async () => {
    const user = userEvent.setup();
    render(<AdminSubscriptionsWorkspace />);
    await screen.findByText("Awa Kouassi");

    await user.click(
      screen.getByRole("button", { name: "Gérer l'abonnement de Awa Kouassi" }),
    );
    await user.selectOptions(screen.getByLabelText("Action"), "activate");
    await user.selectOptions(screen.getByLabelText("Plan"), "essential");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(adminSubscriptionAction).toHaveBeenCalledWith("s1", {
      action: "activate",
      plan_slug: "essential",
      days: 30,
    });
    expect(await screen.findByText("Action enregistrée avec succès.")).toBeInTheDocument();
  });

  it("cancels a subscription", async () => {
    const user = userEvent.setup();
    render(<AdminSubscriptionsWorkspace />);
    await screen.findByText("Awa Kouassi");

    await user.click(
      screen.getByRole("button", { name: "Gérer l'abonnement de Awa Kouassi" }),
    );
    await user.selectOptions(screen.getByLabelText("Action"), "cancel");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(adminSubscriptionAction).toHaveBeenCalledWith("s1", { action: "cancel" });
    expect(await screen.findByText("Action enregistrée avec succès.")).toBeInTheDocument();
  });

  it("shows an error when the action fails", async () => {
    vi.mocked(adminSubscriptionAction).mockRejectedValue(
      new Error("Plan invalide."),
    );
    const user = userEvent.setup();
    render(<AdminSubscriptionsWorkspace />);
    await screen.findByText("Awa Kouassi");

    await user.click(
      screen.getByRole("button", { name: "Gérer l'abonnement de Awa Kouassi" }),
    );
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(await screen.findByText("Plan invalide.")).toBeInTheDocument();
  });
});
