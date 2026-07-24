import { render, screen } from "@testing-library/react";
import { Feedback } from "./feedback";

describe("Feedback", () => {
  it("renders nothing when message is null", () => {
    const { container } = render(<Feedback message={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders success message with check icon", () => {
    render(<Feedback message="Opération réussie" tone="success" />);
    expect(screen.getByText("Opération réussie")).toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders error message with alert role", () => {
    render(<Feedback message="Erreur détectée" tone="error" />);
    expect(screen.getByText("Erreur détectée")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("defaults to success tone", () => {
    render(<Feedback message="Message par défaut" />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders empty string message", () => {
    render(<Feedback message="" tone="error" />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});