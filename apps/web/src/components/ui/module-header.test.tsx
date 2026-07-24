import { render, screen } from "@testing-library/react";
import { ModuleHeader } from "./module-header";

describe("ModuleHeader", () => {
  it("renders eyebrow, title and description", () => {
    render(
      <ModuleHeader
        eyebrow="Section"
        title="Titre de la page"
        description="Description de la section"
      />,
    );
    expect(screen.getByText("Section")).toBeInTheDocument();
    expect(screen.getByText("Titre de la page")).toBeInTheDocument();
    expect(screen.getByText("Description de la section")).toBeInTheDocument();
  });

  it("renders action element when provided", () => {
    render(
      <ModuleHeader
        eyebrow="Test"
        title="Avec action"
        description="Description"
        action={<button type="button">Action</button>}
      />,
    );
    expect(screen.getByText("Action")).toBeInTheDocument();
  });

  it("renders without action", () => {
    const { container } = render(
      <ModuleHeader
        eyebrow="Test"
        title="Sans action"
        description="Description"
      />,
    );
    expect(container.querySelector("section > div")).toBeInTheDocument();
  });
});