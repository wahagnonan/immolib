import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Modal } from "./modal";

describe("Modal", () => {
  it("renders nothing when closed", () => {
    const { container } = render(
      <Modal open={false} title="Test" onClose={vi.fn()}>
        <p>Contenu</p>
      </Modal>,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders content when open", () => {
    render(
      <Modal open={true} title="Titre de la modale" onClose={vi.fn()}>
        <p>Contenu de la modale</p>
      </Modal>,
    );
    expect(screen.getByText("Titre de la modale")).toBeInTheDocument();
    expect(screen.getByText("Contenu de la modale")).toBeInTheDocument();
  });

  it("renders kicker and description when provided", () => {
    render(
      <Modal
        open={true}
        title="Avec détails"
        kicker="Section"
        description="Description détaillée"
        onClose={vi.fn()}
      >
        <p>Contenu</p>
      </Modal>,
    );
    expect(screen.getByText("Section")).toBeInTheDocument();
    expect(screen.getByText("Description détaillée")).toBeInTheDocument();
  });

  it("calls onClose when Escape is pressed", () => {
    const onClose = vi.fn();
    render(
      <Modal open={true} title="Fermable" onClose={onClose}>
        <p>Contenu</p>
      </Modal>,
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when clicking the close button", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <Modal open={true} title="Fermable" onClose={onClose}>
        <p>Contenu</p>
      </Modal>,
    );
    await user.click(screen.getByLabelText("Fermer"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when clicking the backdrop", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <Modal open={true} title="Fermable" onClose={onClose}>
        <p>Contenu</p>
      </Modal>,
    );
    await user.click(screen.getByRole("dialog"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("locks body overflow when open", () => {
    render(
      <Modal open={true} title="Test" onClose={vi.fn()}>
        <p>Contenu</p>
      </Modal>,
    );
    expect(document.body.style.overflow).toBe("hidden");
  });

  it("restores body overflow on unmount", () => {
    const { unmount } = render(
      <Modal open={true} title="Test" onClose={vi.fn()}>
        <p>Contenu</p>
      </Modal>,
    );
    unmount();
    expect(document.body.style.overflow).toBe("");
  });

  it("supports size variants", () => {
    const { rerender } = render(
      <Modal open={true} title="Taille md" onClose={vi.fn()} size="md">
        <p>Contenu</p>
      </Modal>,
    );
    expect(screen.getByText("Taille md")).toBeInTheDocument();

    rerender(
      <Modal open={true} title="Taille xl" onClose={vi.fn()} size="xl">
        <p>Contenu</p>
      </Modal>,
    );
    expect(screen.getByText("Taille xl")).toBeInTheDocument();
  });
});